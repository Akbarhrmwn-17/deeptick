# ⚡ deeptick

> High-performance quantitative market intelligence, multi-factor momentum screening, and algorithmic execution workstation.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![UI Framework](https://img.shields.io/badge/framework-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🧭 Overview

**deeptick** is an advanced quantitative intelligence terminal built for active market participants. It integrates real-time macro regime classification, multi-timeframe technical momentum tracking, order flow anchor zones, and algorithmic forecasting into a single unified workspace.

---

## ✨ Core Modules

- **🌐 Macro Regime & Market Pulse**  
  Real-time market index regime classification (Risk-On / Selective / Risk-Off), trend structure, moving average spreads, and breadth dynamics.

- **⚡ Momentum & Scalping Terminal**  
  Algorithmic anchor entry points, smart money accumulation scoring, tight stop-loss buffers, and dynamic risk/reward target matrix.

- **🔬 Deep Research & Multi-Factor Forecast**  
  Comprehensive multi-factor analytics: technical indicator matrix, stochastic oscillators, ATR-based volatility projections, and valuation metrics.

- **🚦 Signal Engine & Quantitative Scoring**  
  Multi-indicator algorithmic scoring engine with real-time consensus filters.

- **💼 Portfolio & Risk Ledger**  
  Real-time position monitoring, automated P&L calculation, risk allocation charts, and trade journaling.

- **⚡ Real-Time Tape & Flow Monitor**  
  High-frequency transaction stream simulation, order book pressure, and tape-reading dynamics.

---

## 🚀 Quick Start

### 1. Requirements

Ensure you have **Python 3.10+** installed.

```bash
git clone https://github.com/Akbarhrmwn-17/deeptick.git
cd deeptick
```

### 2. Install Dependencies

```bash
python3 -m pip install -r requirements.txt --user --break-system-packages
```

### 3. Launch Workstation

```bash
bash run.sh
```

Or run directly via Streamlit:

```bash
streamlit run app.py
```

Open your browser at **`http://localhost:8501`**

---

## 🛠️ Tech Architecture

| Layer | Technology |
|---|---|
| **Core UI** | Streamlit (Custom Dark Theme Engine) |
| **Data Engine** | Yahoo Finance Financial API |
| **Analytics** | Pandas, NumPy, pandas-ta |
| **Visualization** | Plotly Interactive Visuals |
| **Storage Engine** | Local SQLite Database (`stock.db`) |
| **Scheduler** | APScheduler Background Worker |
| **Alerts** | Low-latency Desktop Notification Daemon |

---

## 📁 Repository Structure

```
deeptick/
├── app.py              # Application entry point & master dashboard
├── config.py           # Engine & parameter configuration
├── run.sh              # Local workstation launcher
├── requirements.txt    # Production dependencies
│
├── analysis/           # Quantitative algorithms & technical engines
│   ├── ihsg.py         # Macro regime & index breadth engine
│   ├── scalping.py     # High-probability scalp & anchor order engine
│   ├── forecast.py     # DeMark, ATR & multi-scenario predictive engine
│   ├── signals.py      # Algorithmic scoring & signal generator
│   └── technical.py    # Multi-timeframe indicator formulas
│
├── data/               # High-throughput data fetching & ingestion
│   ├── scanner.py      # Market-wide quantitative scanner
│   ├── running_trade.py# Real-time tape flow simulator
│   └── fetcher.py      # Historical time-series fetcher
│
├── database/           # Persistence layer (local SQLite models & schema)
│
├── notifications/      # Alert dispatcher & trigger monitor
│
└── pages/              # Modular workstation pages (01 to 08)
```

---

## 📜 Disclaimer

> *This software is designed for quantitative research, financial analytics, and educational purposes only. It does not constitute investment or financial advice.*
