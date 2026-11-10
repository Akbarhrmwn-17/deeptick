"""notifications/notifier.py — Desktop notification menggunakan plyer"""

from database.models import get_unnotified_signals, mark_signal_notified
from config import SIGNAL_COLORS


def _get_signal_emoji(signal_type: str) -> str:
    emojis = {
        "STRONG_BUY":  "🟢🟢",
        "BUY":         "🟢",
        "HOLD":        "🟡",
        "SELL":        "🔴",
        "STRONG_SELL": "🔴🔴",
    }
    return emojis.get(signal_type, "ℹ️")


def send_desktop_notification(title: str, message: str, timeout: int = 8):
    """Kirim notifikasi desktop. Diam-diam gagal jika plyer tidak tersedia."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Saham Monitor 🇮🇩",
            timeout=timeout,
        )
    except ImportError:
        print(f"[Notif] {title}: {message}")
    except Exception as e:
        print(f"[Notif] Desktop notification failed: {e}")
        print(f"[Notif] {title}: {message}")


def notify_signals():
    """
    Ambil semua sinyal yang belum dinotifikasi dan kirim desktop notification.
    Tandai sebagai sudah dinotifikasi setelah dikirim.
    """
    unnotified = get_unnotified_signals()
    if not unnotified:
        return

    for signal in unnotified:
        ticker = signal["ticker"]
        sig_type = signal["signal_type"]
        emoji = _get_signal_emoji(sig_type)

        title = f"{emoji} Saham Monitor — {ticker}"
        reason_preview = signal.get("reason", "")
        if reason_preview:
            # Ambil baris pertama alasan
            reason_preview = reason_preview.split("\n")[0].replace("•", "").strip()

        message = f"Sinyal: {sig_type}\n{reason_preview}"

        send_desktop_notification(title, message)
        mark_signal_notified(signal["id"])

    print(f"[Notif] {len(unnotified)} sinyal dikirim.")


def notify_price_alert(ticker: str, rule_type: str, current_price: float, target: float):
    """Notifikasi untuk custom price alert."""
    emoji = "⚠️"
    if rule_type == "PRICE_BELOW":
        msg = f"Harga {ticker} ({current_price:,.0f}) sudah di bawah target {target:,.0f}"
    elif rule_type == "PRICE_ABOVE":
        msg = f"Harga {ticker} ({current_price:,.0f}) sudah di atas target {target:,.0f}"
    else:
        msg = f"Alert {rule_type} triggered untuk {ticker}"

    send_desktop_notification(f"{emoji} Price Alert — {ticker}", msg)
