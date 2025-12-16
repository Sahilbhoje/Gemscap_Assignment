# Quant Developer Evaluation Assignment — Real-time Pairs Analytics

This app ingests live Binance Futures ticks, resamples to OHLCV, computes core pairs analytics (OLS hedge ratio, spread, z-score, ADF p-value, rolling correlation), triggers simple z-score alerts, and visualizes everything in a live dashboard.

## Quick Start

1) Create venv and install deps

```powershell
python -m venv .venv
" .venv/Scripts/Activate.ps1"
pip install -r requirements.txt
```

2) Run the app

```powershell
python app.py
```

3) Open the dashboard
- Visit http://127.0.0.1:8050

## Features
- Live Binance trade ingestion (per-symbol) with auto-reconnect
- In-memory tick buffer + lightweight SQLite persistence (data/market.db)
- Resampling: 1s, 1m, 5m (selectable)
- Analytics: OLS hedge ratio (with intercept), spread, z-score, ADF p-value, rolling correlation
- Alerts: simple z-score threshold (two-sided)
- Data export: download processed close series as CSV
- OHLC CSV upload: basic handler (hook for integrating historicals)
- Charts: zoom, pan, hover via Plotly

## How It Works
- market_data.py: Background asyncio subscribers to wss://fstream.binance.com/ws/<symbol>@trade, buffering ticks and exposing pandas resampling
- analytics.py: OLS regression (statsmodels), spread & z-score, rolling correlation, ADF test
- alerts.py: in-memory rules and events for z-score alerts
- storage.py: SQLite tables for ticks/ohlcv; app writes periodic snapshots
- app.py: Dash UI, controls, charts, and periodic updates every 500ms

## Controls
- Symbols Y/X: two symbols (e.g., btcusdt, ethusdt)
- Timeframe: 1s/1m/5m
- Rolling Window: z-score and correlation window (default 100)
- Z-Alert Threshold: absolute z-score (default 2)
- Start/Stop: control live subscriptions
- Download Processed CSV: export aligned close series
- Upload OHLC CSV: placeholder to ingest historicals

## Notes & Assumptions
- Follows the provided HTML reference for stream shape (s, T/E, p, q)
- Keeps design modular: ingestion, analytics, storage, UI are decoupled modules
- Focus is on thoughtful design and correctness over micro-optimizations
- ADF is computed on demand in the analytics pipeline and summarized as latest p-value

## Extending
- Add Kalman Filter for dynamic beta in analytics.py
- Add robust regression options (Huber/Theil–Sen)
- Add a simple backtest loop using the z-score series
- Add cross-correlation heatmaps across many symbols
- Add richer alert rules with multiple conditions and delivery channels

## Architecture
See ARCHITECTURE.drawio (source). Open with draw.io (diagrams.net) and export PNG/SVG from the File menu.

## ChatGPT Usage Transparency
See CHATGPT_USAGE.md for prompts and assistance details.