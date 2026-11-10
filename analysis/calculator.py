"""analysis/calculator.py — Engine Money Management, Position Sizing & Fee Broker BEI

Standar Perhitungan Trader Institusional:
- Fixed Fractional Risk Model (Batasan risiko 1% - 2% modal per trade)
- Kalkulasi Fee Broker BEI (Beli: 0.15%, Jual: 0.25% include PPh & Levy)
- Harga Breakeven Point (BEP)
- Net Profit / Net Loss setelah seluruh biaya transaksi
- Generator Format Teks Siap Salin untuk WhatsApp / Telegram / Jurnal
"""

import math
from typing import Dict, Optional


def calculate_trade_position(
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    target_profit: float,
    fee_buy_pct: float = 0.15,
    fee_sell_pct: float = 0.25,
) -> Dict:
    """
    Hitung kalkulasi posisi trading saham BEI secara profesional.
    
    Parameters:
    - capital: Total modal trading yang dialokasikan (Rp)
    - risk_pct: Toleransi risiko per transaksi (umumnya 1% - 2%)
    - entry_price: Harga rencana beli (Rp)
    - stop_loss: Harga batas cut loss (Rp)
    - target_profit: Harga target take profit (Rp)
    - fee_buy_pct: Fee beli broker (default 0.15%)
    - fee_sell_pct: Fee jual broker (default 0.25% include PPh 0.1%)
    """
    if capital <= 0 or entry_price <= 0 or stop_loss <= 0 or target_profit <= 0:
        return {}

    fee_buy_rate = fee_buy_pct / 100.0
    fee_sell_rate = fee_sell_pct / 100.0

    # 1. Breakeven Price (BEP)
    # Revenue * (1 - fee_sell) = Cost * (1 + fee_buy)
    bep_price = entry_price * (1.0 + fee_buy_rate) / (1.0 - fee_sell_rate)
    bep_tick = math.ceil(bep_price)

    # 2. Toleransi Risiko Nominal
    max_risk_idr = capital * (risk_pct / 100.0)

    # 3. Risiko per lembar jika kena Stop Loss (Gross + Biaya Broker Beli & Jual)
    price_risk_per_share = abs(entry_price - stop_loss)
    fee_buy_per_share = entry_price * fee_buy_rate
    fee_sell_per_share_sl = stop_loss * fee_sell_rate
    total_risk_per_share = price_risk_per_share + fee_buy_per_share + fee_sell_per_share_sl
    total_risk_per_lot = total_risk_per_share * 100.0

    # 4. Ukuran Lot Ideal (Position Sizing)
    # Batas A: Berdasarkan batasan risiko modal (Fixed Fractional)
    lot_by_risk = math.floor(max_risk_idr / max(total_risk_per_lot, 0.001))
    
    # Batas B: Berdasarkan daya beli modal maksimum (100% Cash)
    cost_per_lot = (entry_price * 100.0) * (1.0 + fee_buy_rate)
    lot_by_capital = math.floor(capital / max(cost_per_lot, 0.001))

    # Lot final yang direkomendasikan
    recommended_lot = max(1, min(lot_by_risk, lot_by_capital))
    total_shares = recommended_lot * 100

    # 5. Nilai Modal Terpakai
    gross_buy_value = total_shares * entry_price
    total_fee_buy = gross_buy_value * fee_buy_rate
    net_buy_cost = gross_buy_value + total_fee_buy

    # 6. Simulasi Skenario Take Profit (Net of Fees)
    gross_tp_value = total_shares * target_profit
    fee_sell_tp = gross_tp_value * fee_sell_rate
    net_tp_proceeds = gross_tp_value - fee_sell_tp
    net_profit_idr = net_tp_proceeds - net_buy_cost
    net_profit_pct = (net_profit_idr / net_buy_cost) * 100.0

    # 7. Simulasi Skenario Stop Loss (Net of Fees)
    gross_sl_value = total_shares * stop_loss
    fee_sell_sl = gross_sl_value * fee_sell_rate
    net_sl_proceeds = gross_sl_value - fee_sell_sl
    net_loss_idr = net_buy_cost - net_sl_proceeds  # selalu positif
    net_loss_pct = (net_loss_idr / net_buy_cost) * 100.0

    # 8. Rasio Risk:Reward Bersih
    net_rr_ratio = net_profit_idr / max(net_loss_idr, 0.01)

    return {
        "capital": capital,
        "risk_pct": risk_pct,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_profit": target_profit,
        "bep_price": round(bep_price, 2),
        "bep_tick": bep_tick,
        "fee_buy_pct": fee_buy_pct,
        "fee_sell_pct": fee_sell_pct,
        "max_risk_idr": round(max_risk_idr, 0),
        "recommended_lot": recommended_lot,
        "total_shares": total_shares,
        "net_buy_cost": round(net_buy_cost, 0),
        "gross_buy_value": round(gross_buy_value, 0),
        "total_fee_buy": round(total_fee_buy, 0),
        "net_profit_idr": round(net_profit_idr, 0),
        "net_profit_pct": round(net_profit_pct, 2),
        "net_loss_idr": round(net_loss_idr, 0),
        "net_loss_pct": round(net_loss_pct, 2),
        "net_rr_ratio": round(net_rr_ratio, 2),
        "is_capital_capped": lot_by_capital < lot_by_risk,
    }


def calculate_holding_exit(
    net_lot: float,
    avg_price: float,
    current_price: float,
    target_profit: float,
    stop_loss: float,
    fee_buy_pct: float = 0.15,
    fee_sell_pct: float = 0.25,
) -> Dict:
    """
    Hitung kalkulasi posisi portofolio yang sedang dimiliki (Exit Plan).
    """
    if net_lot <= 0 or avg_price <= 0:
        return {}

    total_shares = int(net_lot * 100)
    fee_buy_rate = fee_buy_pct / 100.0
    fee_sell_rate = fee_sell_pct / 100.0

    # Total modal beli awal (termasuk fee beli)
    gross_cost = total_shares * avg_price
    buy_fee = gross_cost * fee_buy_rate
    total_cost = gross_cost + buy_fee

    # Nilai saat ini (Floating value & PnL)
    current_gross = total_shares * current_price
    current_sell_fee = current_gross * fee_sell_rate
    current_net = current_gross - current_sell_fee
    unrealized_pnl_idr = current_net - total_cost
    unrealized_pnl_pct = (unrealized_pnl_idr / total_cost) * 100.0

    # BEP (Breakeven Price)
    bep_price = avg_price * (1.0 + fee_buy_rate) / (1.0 - fee_sell_rate)
    bep_tick = math.ceil(bep_price)

    # Skenario Target Profit (TP)
    tp_gross = total_shares * target_profit
    tp_fee = tp_gross * fee_sell_rate
    tp_net = tp_gross - tp_fee
    tp_profit_idr = tp_net - total_cost
    tp_profit_pct = (tp_profit_idr / total_cost) * 100.0

    # Skenario Stop Loss (SL)
    sl_gross = total_shares * stop_loss
    sl_fee = sl_gross * fee_sell_rate
    sl_net = sl_gross - sl_fee
    sl_pnl_idr = sl_net - total_cost
    sl_pnl_pct = (sl_pnl_idr / total_cost) * 100.0

    return {
        "net_lot": net_lot,
        "total_shares": total_shares,
        "avg_price": avg_price,
        "current_price": current_price,
        "target_profit": target_profit,
        "stop_loss": stop_loss,
        "total_cost": round(total_cost, 0),
        "current_net": round(current_net, 0),
        "unrealized_pnl_idr": round(unrealized_pnl_idr, 0),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
        "bep_price": round(bep_price, 2),
        "bep_tick": bep_tick,
        "tp_profit_idr": round(tp_profit_idr, 0),
        "tp_profit_pct": round(tp_profit_pct, 2),
        "sl_pnl_idr": round(sl_pnl_idr, 0),
        "sl_pnl_pct": round(sl_pnl_pct, 2),
    }


def generate_whatsapp_trading_plan(
    ticker: str,
    company_name: str,
    current_price: float,
    entry_price: float,
    stop_loss: float,
    target_1: float,
    target_2: Optional[float] = None,
    pivot: Optional[float] = None,
    bias_label: str = "NETRAL",
    prob_up: Optional[int] = None,
    recommended_lot: Optional[int] = None,
    net_profit_idr: Optional[float] = None,
    net_loss_idr: Optional[float] = None,
    note: str = "",
) -> str:
    """Hasilkan format teks rapi dan ringkas siap kirim ke WhatsApp / Telegram."""
    lines = [
        f"🎯 *TRADING PLAN: {ticker}* ({company_name})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📍 *Harga Acuan* : Rp {current_price:,.0f}",
    ]
    if pivot:
        lines.append(f"🔑 *Level Penentu*: Rp {pivot:,.0f}")
    if bias_label:
        prob_str = f" ({prob_up}% Peluang Naik)" if prob_up is not None else ""
        lines.append(f"📊 *Bias Esok*    : {bias_label}{prob_str}")
    
    lines.append("────────────────────────────")
    lines.append(f"🟢 *Area Entry*   : Rp {entry_price:,.0f}")
    
    tp1_pct = ((target_1 - entry_price) / max(entry_price, 1.0)) * 100.0
    lines.append(f"🎯 *Target TP 1*  : Rp {target_1:,.0f} (+{tp1_pct:.1f}%)")
    
    if target_2:
        tp2_pct = ((target_2 - entry_price) / max(entry_price, 1.0)) * 100.0
        lines.append(f"🎯 *Target TP 2*  : Rp {target_2:,.0f} (+{tp2_pct:.1f}%)")
        
    sl_pct = ((entry_price - stop_loss) / max(entry_price, 1.0)) * 100.0
    lines.append(f"🛑 *Stop Loss*    : Rp {stop_loss:,.0f} (-{sl_pct:.1f}%) [DISIPLIN!]")
    
    if recommended_lot:
        lines.append("────────────────────────────")
        lines.append(f"📦 *Ukuran Posisi*: {recommended_lot:,} Lot")
        if net_profit_idr is not None and net_loss_idr is not None:
            lines.append(f"💰 *Potensi Net*  : +Rp {net_profit_idr:,.0f} vs -Rp {net_loss_idr:,.0f}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if note:
        lines.append(f"💡 *Catatan:* {note}")
    else:
        lines.append("💡 *SOP Pro:* Jual 50% di TP1, pasang Trailing Stop sisa lot. Cut loss wajib jika tembus SL.")

    return "\n".join(lines)
