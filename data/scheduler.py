"""data/scheduler.py — Auto-refresh data saat market buka (WIB)"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

from config import TZ, MARKET_OPEN_HOUR, MARKET_CLOSE_HOUR, FETCH_INTERVAL_MINUTES


_scheduler: BackgroundScheduler | None = None


def _is_market_open() -> bool:
    """Cek apakah pasar IDX sedang buka (Senin-Jumat, 09:00-16:00 WIB)."""
    now = datetime.now(TZ)
    if now.weekday() >= 5:   # Sabtu=5, Minggu=6
        return False
    return MARKET_OPEN_HOUR <= now.hour < MARKET_CLOSE_HOUR


def _fetch_job():
    """Job yang dijalankan scheduler."""
    if not _is_market_open():
        return
    print(f"[Scheduler] Auto-fetch triggered at {datetime.now(TZ).strftime('%H:%M WIB')}")
    try:
        from data.fetcher import update_all_watchlist
        update_all_watchlist(period="5d")   # Hanya 5 hari terakhir saat intraday
    except Exception as e:
        print(f"[Scheduler] Error: {e}")


def _signal_job():
    """Generate sinyal untuk semua saham di watchlist."""
    if not _is_market_open():
        return
    try:
        from database.models import get_watchlist
        from analysis.signals import generate_and_save_signals
        from notifications.notifier import notify_signals

        stocks = get_watchlist()
        for stock in stocks:
            generate_and_save_signals(stock["ticker"])

        notify_signals()
        print(f"[Scheduler] Signals updated at {datetime.now(TZ).strftime('%H:%M WIB')}")
    except Exception as e:
        print(f"[Scheduler] Signal job error: {e}")


def start_scheduler():
    """Start background scheduler. Dipanggil satu kali saat app startup."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone=TZ)

    # Fetch data setiap N menit (langsung jalankan saat startup jika jam bursa)
    _scheduler.add_job(
        _fetch_job,
        trigger="interval",
        minutes=FETCH_INTERVAL_MINUTES,
        next_run_time=datetime.now(TZ),
        id="fetch_job",
        replace_existing=True,
    )

    # Generate sinyal setiap N+5 menit (setelah fetch selesai)
    _scheduler.add_job(
        _signal_job,
        trigger="interval",
        minutes=FETCH_INTERVAL_MINUTES,
        start_date=datetime.now(TZ).replace(second=30),
        id="signal_job",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"[Scheduler] Started. Fetch interval: {FETCH_INTERVAL_MINUTES} menit.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped.")


def get_scheduler_status() -> dict:
    """Return status info scheduler."""
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S %Z") if next_run else "N/A",
        })
    return {"running": True, "jobs": jobs}
