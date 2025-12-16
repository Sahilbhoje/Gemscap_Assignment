# ChatGPT Usage Transparency

- Used ChatGPT (GitHub Copilot, model GPT-5) to:
  - Plan the application architecture and module breakdown.
  - Draft the initial implementation for Binance WebSocket ingestion, resampling, analytics, and Dash UI.
  - Generate a minimal SQLite storage layer and alert system.
  - Create documentation scaffolding and a basic architecture diagram file.
- Iteratively refined code and fixed integration issues discovered while wiring Dash callbacks.
- All external APIs/libraries used are listed in requirements.txt.

## Prompts (summarized)
- Build a Python Dash app that streams Binance trade data, resamples to OHLCV, computes OLS hedge ratio, spread, z-score, ADF, and rolling correlation, with alerts and CSV export.
- Implement a background asyncio WebSocket manager for fstream.binance.com with per-symbol buffering and reconnection.
- Provide a concise README, runnable via python app.py, and an architecture diagram stub.
