"""pages/01_Dashboard.py — Grafik candlestick + indikator teknikal"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from database.models import get_watchlist, get_latest_price
from data.fetcher import fetch_price_history, get_price_df_from_db
from analysis.technical import add_indicators, get_technical_scorecard
from config import SIGNAL_COLORS

st.set_page_config(page_title="Dashboard — Saham Monitor", page_icon="📊", layout="wide")
st.title("📊 Dashboard")

# ── Sidebar Controls ─────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Pengaturan Grafik")
    watchlist = get_watchlist()

    if not watchlist:
        st.warning("Watchlist kosong. Tambah saham di Settings.")
        st.stop()

    tickers = [s["ticker"] for s in watchlist]
    selected_ticker = st.selectbox(
        "Pilih Saham",
        tickers,
        format_func=lambda t: f"{t} — {next((s['name'] for s in watchlist if s['ticker']==t), '')}",
    )

    period_map = {"1 Bulan": "1mo", "3 Bulan": "3mo", "6 Bulan": "6mo",
                  "1 Tahun": "1y", "2 Tahun": "2y"}
    selected_period_label = st.selectbox("Periode", list(period_map.keys()), index=3)
    selected_period = period_map[selected_period_label]

    show_ma20   = st.checkbox("MA20", value=True)
    show_ma50   = st.checkbox("MA50", value=True)
    show_ma200  = st.checkbox("MA200", value=False)
    show_bb     = st.checkbox("Bollinger Bands", value=True)

    if st.button("🔄 Refresh Data", use_container_width=True):
        with st.spinner(f"Mengambil data {selected_ticker}..."):
            fetch_price_history(selected_ticker, period=selected_period, save_to_db=True)
        st.success("Data diperbarui!")
        st.rerun()


# ── Load Data ─────────────────────────────────────────────
df_raw = get_price_df_from_db(selected_ticker, limit=500)

if df_raw.empty:
    st.info(f"Belum ada data untuk **{selected_ticker}**. Klik tombol **🔄 Refresh Data** di sidebar.")
    st.stop()

df = add_indicators(df_raw)


# ── Header Info ───────────────────────────────────────────
stock_info = next((s for s in watchlist if s["ticker"] == selected_ticker), {})
latest = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
price_change = latest["close"] - prev["close"]
pct_change = (price_change / prev["close"] * 100) if prev["close"] else 0

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("💰 Harga", f"Rp {latest['close']:,.0f}",
              f"{price_change:+.0f} ({pct_change:+.2f}%)")
with col2:
    rsi = latest.get("RSI")
    rsi_label = "Oversold 🟢" if rsi and rsi < 30 else ("Overbought 🔴" if rsi and rsi > 70 else "Netral 🟡")
    st.metric("RSI(14)", f"{rsi:.1f}" if rsi else "—", rsi_label)
with col3:
    ma20 = latest.get("MA20")
    st.metric("MA20", f"Rp {ma20:,.0f}" if ma20 else "—")
with col4:
    ma50 = latest.get("MA50")
    st.metric("MA50", f"Rp {ma50:,.0f}" if ma50 else "—")
with col5:
    vol = latest.get("volume", 0)
    st.metric("Volume", f"{vol/1e6:.1f}M" if vol > 1e6 else f"{vol:,.0f}")

st.divider()


# ── Main Chart ────────────────────────────────────────────
def build_chart(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=["Candlestick", "Volume", "RSI & MACD"],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="OHLC",
        increasing_line_color="#00C853",
        decreasing_line_color="#D50000",
    ), row=1, col=1)

    # Moving Averages
    if show_ma20 and "MA20" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["MA20"], name="MA20",
            line=dict(color="#1565C0", width=1.5)
        ), row=1, col=1)

    if show_ma50 and "MA50" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["MA50"], name="MA50",
            line=dict(color="#E65100", width=1.5)
        ), row=1, col=1)

    if show_ma200 and "MA200" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["MA200"], name="MA200",
            line=dict(color="#6A1B9A", width=1.5, dash="dash")
        ), row=1, col=1)

    # Bollinger Bands
    if show_bb and "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["BB_Upper"], name="BB Upper",
            line=dict(color="rgba(100,100,255,0.5)", width=1, dash="dot"),
            showlegend=True,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["BB_Lower"], name="BB Lower",
            line=dict(color="rgba(100,100,255,0.5)", width=1, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(100,100,255,0.05)",
            showlegend=False,
        ), row=1, col=1)

    # Volume
    colors = ["#00C853" if c >= o else "#D50000"
              for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["volume"],
        name="Volume", marker_color=colors, opacity=0.7,
    ), row=2, col=1)

    if "Vol_MA20" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["Vol_MA20"], name="Vol MA20",
            line=dict(color="orange", width=1.2),
        ), row=2, col=1)

    # RSI
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["RSI"], name="RSI",
            line=dict(color="#AB47BC", width=1.5),
        ), row=3, col=1)
        fig.add_hline(y=70, line=dict(color="red", dash="dash", width=1), row=3, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dash", width=1), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=700,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    fig.update_yaxes(title_text="Harga (Rp)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])

    return fig


fig = build_chart(df)
st.plotly_chart(fig, use_container_width=True)


# ── MACD Chart (terpisah) ─────────────────────────────────
if "MACD" in df.columns and df["MACD"].notna().any():
    with st.expander("📈 MACD Detail", expanded=False):
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(
            x=df["date"], y=df["MACD"], name="MACD",
            line=dict(color="#26C6DA", width=1.5)
        ))
        fig_macd.add_trace(go.Scatter(
            x=df["date"], y=df["MACD_Signal"], name="Signal",
            line=dict(color="#EF5350", width=1.5)
        ))
        fig_macd.add_trace(go.Bar(
            x=df["date"], y=df["MACD_Hist"], name="Histogram",
            marker_color=["#00C853" if v > 0 else "#D50000"
                          for v in df["MACD_Hist"].fillna(0)]
        ))
        fig_macd.update_layout(
            template="plotly_dark", height=250,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_macd, use_container_width=True)


# ── Technical Scorecard ───────────────────────────────────
st.subheader("🎯 Scorecard Teknikal")
scorecard = get_technical_scorecard(df_raw)

if scorecard:
    SIGNAL_ICON = {
        "BUY": "🟢 BUY", "STRONG_BUY": "🟢🟢 STRONG BUY",
        "SELL": "🔴 SELL", "STRONG_SELL": "🔴🔴 STRONG SELL",
        "HOLD": "🟡 HOLD", "WATCH": "👀 WATCH",
        "NORMAL": "✅ NORMAL", "UNKNOWN": "❓ —",
    }

    col_ind = ["MA Crossover", "RSI", "MACD", "Bollinger Bands", "Volume"]
    col_keys = ["ma", "rsi", "macd", "bb", "volume"]
    card_cols = st.columns(len(col_ind))

    for col, name, key in zip(card_cols, col_ind, col_keys):
        ind = scorecard.get(key, {})
        sig = ind.get("signal", "UNKNOWN")
        with col:
            st.markdown(f"**{name}**")
            st.markdown(SIGNAL_ICON.get(sig, sig))
            st.caption(ind.get("detail", ""))

st.markdown("---")

with st.expander("📚 Glosarium & Penjelasan Istilah Teknikal (Dashboard)", expanded=False):
    st.markdown("""
    Berikut panduan memahami singkatan dan indikator teknikal pada halaman ini:

    | Singkatan / Istilah | Kepanjangan | Penjelasan & Cara Membaca |
    | :--- | :--- | :--- |
    | **OHLC** | *Open, High, Low, Close* | 4 harga pembentuk candlestick: Harga Buka (*Open*), Tertinggi (*High*), Terendah (*Low*), dan Penutupan (*Close*). Lilin hijau = harga naik, lilin merah = harga turun. |
    | **MA20 / MA50 / MA200** | *Moving Average (20, 50, 200 hari)* | Garis rata-rata harga penutupan selama 20, 50, atau 200 hari bursa.<br>• **MA20**: Tren jangka pendek (~1 bulan).<br>• **MA50**: Tren jangka menengah (~2.5 bulan).<br>• **MA200**: Tren jangka panjang (~1 tahun / penentu tren mayor pasar). |
    | **Golden Cross** | *Bullish Crossover* | Garis MA pendek (MA20) memotong ke atas MA yang lebih panjang (MA50). Sinyal potensi awal fase tren naik (*uptrend*). |
    | **Death Cross** | *Bearish Crossover* | Garis MA pendek (MA20) memotong ke bawah MA yang lebih panjang (MA50). Sinyal potensi awal fase tren turun (*downtrend*). |
    | **RSI (14)** | *Relative Strength Index* | Indikator momentum rentang 0 - 100 untuk mengukur kejenuhan pasar:<br>• **RSI < 30 (Oversold)**: Jenuh jual / harga sudah turun terlalu dalam, potensi pantulan beli (*rebound*).<br>• **RSI > 70 (Overbought)**: Jenuh beli / harga naik terlalu cepat, rawan koreksi ambil untung (*profit taking*).<br>• **30 - 70**: Fase netral. |
    | **MACD** | *Moving Average Convergence Divergence* | Indikator momentum & arah tren:<br>• **Garis MACD**: Selisih EMA 12 hari & EMA 26 hari.<br>• **Signal Line**: Garis pemicu rata-rata (EMA 9).<br>• **Histogram**: Batang selisih MACD vs Signal. Batang hijau di atas nol = momentum menguat; batang merah di bawah nol = momentum melemah. |
    | **Bollinger Bands (BB)** | *Upper, Mid, Lower Band* | Pita pengukur volatilitas berbasis deviasi standar.<br>• **Upper Band**: Batas atas volatilitas normal (harga menyentuh ini rawan tertahan).<br>• **Mid Band**: Garis tengah (MA20).<br>• **Lower Band**: Batas bawah volatilitas normal (harga menyentuh ini sering memicu pantulan beli). |
    | **Vol MA20** | *Volume Moving Average (20 hari)* | Rata-rata volume lembar saham yang diperdagangkan selama 20 hari. Jika volume harian jauh di atas garis ini (misal > 1.5x - 2x), artinya terjadi aksi beli/jual besar (*volume spike* / akumulasi). |
    | **ATR (14)** | *Average True Range* | Mengukur rata-rata rentang gejolak (volatilitas) harga harian dalam rupiah. Biasa dipakai untuk menentukan jarak aman Stop Loss. |
    """)

st.caption(f"Data terakhir: {df.iloc[-1]['date'].strftime('%d %b %Y')}")

