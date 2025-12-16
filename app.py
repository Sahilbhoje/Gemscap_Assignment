import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import List

import numpy as np
import pandas as pd
from dash import Dash, Input, Output, State, dcc, html
import plotly.graph_objects as go

from market_data import MarketDataManager
from analytics import build_pair_analytics
from alerts import AlertManager, AlertRule
from storage import Storage


DATA_DIR = Path("./data").resolve()
DB_PATH = DATA_DIR / "market.db"

mdm = MarketDataManager(max_ticks_per_symbol=300_000)
alerts = AlertManager()
storage = Storage(DB_PATH)


DEFAULT_SYMBOLS = ["btcusdt", "ethusdt"]
TIMEFRAMES = {"1s": "1s", "1m": "1min", "5m": "5min"}

THEME = {
    "bg": "#0b1220",
    "card": "#0f172a",
    "border": "#1f2a3d",
    "text": "#e7edf7",
    "muted": "#94a3b8",
    "accent": "#38bdf8",
    "accent2": "#a855f7",
}


def card_style(extra=None):
    base = {
        "background": THEME["card"],
        "border": f"1px solid {THEME['border']}",
        "borderRadius": "14px",
        "padding": "14px",
        "boxShadow": "0 10px 30px rgba(0,0,0,0.35)",
    }
    if extra:
        base.update(extra)
    return base


app = Dash(__name__)
server = app.server

app.layout = html.Div([
    html.Div([
        html.Div([
            html.H2("Real-time Pairs Analytics", style={"margin": "0", "color": THEME["text"]}),
            html.P("Live hedge ratios, spreads, z-scores, and correlations with alerting.", style={"margin": "4px 0 0", "color": THEME["muted"]}),
        ]),
        html.Div("LIVE", style={"background": THEME["accent"], "color": THEME["bg"], "padding": "6px 10px", "borderRadius": "999px", "fontWeight": 700}),
    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"}),

    html.Div([
        html.Div([
            html.Label("Symbols (Y / X)", style={"color": THEME["muted"], "fontWeight": 600}),
            dcc.Input(id="sym-y", type="text", value=DEFAULT_SYMBOLS[0], style={"width": "140px", "background": THEME["card"], "color": THEME["text"], "border": f"1px solid {THEME['border']}", "borderRadius": "8px", "padding": "8px"}),
            dcc.Input(id="sym-x", type="text", value=DEFAULT_SYMBOLS[1], style={"width": "140px", "background": THEME["card"], "color": THEME["text"], "border": f"1px solid {THEME['border']}", "borderRadius": "8px", "padding": "8px"}),
        ], style={"display": "flex", "gap": "10px", "alignItems": "flex-end"}),

        html.Div([
            html.Label("Timeframe", style={"color": THEME["muted"], "fontWeight": 600}),
            dcc.Dropdown(
                id="timeframe",
                options=[{"label": k, "value": v} for k, v in TIMEFRAMES.items()],
                value="1s",
                clearable=False,
                style={"width": "140px"},
            ),
            html.Label("Rolling Window", style={"color": THEME["muted"], "fontWeight": 600}),
            dcc.Input(id="window", type="number", value=100, style={"width": "120px", "background": THEME["card"], "color": THEME["text"], "border": f"1px solid {THEME['border']}", "borderRadius": "8px", "padding": "8px"}),
            html.Label("Z-Alert Threshold", style={"color": THEME["muted"], "fontWeight": 600}),
            dcc.Input(id="zthr", type="number", value=2, style={"width": "120px", "background": THEME["card"], "color": THEME["text"], "border": f"1px solid {THEME['border']}", "borderRadius": "8px", "padding": "8px"}),
            html.Button("Apply", id="apply", style={"background": THEME["accent"], "color": THEME["bg"], "border": "none", "borderRadius": "10px", "padding": "10px 14px", "fontWeight": 700}),
            html.Button("Start", id="start", style={"background": THEME["accent2"], "color": THEME["bg"], "border": "none", "borderRadius": "10px", "padding": "10px 14px", "fontWeight": 700}),
            html.Button("Stop", id="stop", style={"background": "#ef4444", "color": THEME["text"], "border": "none", "borderRadius": "10px", "padding": "10px 14px", "fontWeight": 700}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(120px, max-content))", "gap": "10px", "alignItems": "end"}),

        html.Div([
            dcc.Upload(id="upload-ohlc", children=html.Button("Upload OHLC CSV", style={"background": THEME["card"], "color": THEME["text"], "border": f"1px solid {THEME['border']}", "borderRadius": "10px", "padding": "10px 14px", "fontWeight": 600})),
            html.Button("Download Processed CSV", id="download_btn", style={"background": THEME["card"], "color": THEME["text"], "border": f"1px solid {THEME['border']}", "borderRadius": "10px", "padding": "10px 14px", "fontWeight": 600}),
            dcc.Download(id="download_data"),
        ], style={"marginTop": "10px", "display": "flex", "gap": "10px", "flexWrap": "wrap"}),
        html.Div(id="upload_status", style={"marginTop": "4px", "color": THEME["muted"]}),
    ], style=card_style({"marginBottom": "12px", "display": "flex", "flexDirection": "column", "gap": "10px"})),

    dcc.Interval(id="tick-interval", interval=500, n_intervals=0),

    html.Div(id="stats", style={"marginBottom": "12px"}),

    html.Div([
        dcc.Graph(id="price_y_chart", style={"height": "320px"}),
        dcc.Graph(id="price_x_chart", style={"height": "320px"}),
        dcc.Graph(id="spread_chart", style={"height": "300px"}),
        dcc.Graph(id="zscore_chart", style={"height": "300px"}),
        dcc.Graph(id="corr_chart", style={"height": "280px"}),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(380px, 1fr))", "gap": "12px"}),

    html.Div(style={"height": "12px"}),  # spacer

    html.Div([
        html.Div([
            html.H4("Alerts", style={"color": THEME["text"], "margin": "0 0 6px"}),
            html.Pre(id="alerts_box", style={"height": "180px", "overflow": "auto", "background": THEME["card"], "color": THEME["text"], "padding": "10px", "border": f"1px solid {THEME['border']}", "borderRadius": "10px"}),
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "12px"}),
], style={
    "minHeight": "100vh",
    "background": "radial-gradient(circle at 20% 20%, rgba(56,189,248,0.12), transparent 30%), "
                  "radial-gradient(circle at 80% 0%, rgba(168,85,247,0.12), transparent 32%), "
                  f"{THEME['bg']}",
    "padding": "16px",
    "fontFamily": "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
    "color": THEME["text"],
})


def start_stream(symbols: List[str]):
    mdm.start(symbols)


@app.callback(
    Output("stats", "children"),
    Output("price_y_chart", "figure"),
    Output("price_x_chart", "figure"),
    Output("spread_chart", "figure"),
    Output("zscore_chart", "figure"),
    Output("corr_chart", "figure"),
    Output("alerts_box", "children"),
    Input("tick-interval", "n_intervals"),
    State("sym-y", "value"),
    State("sym-x", "value"),
    State("timeframe", "value"),
    State("window", "value"),
    State("zthr", "value"),
)
def update_live(_, sy, sx, tf_rule, window, zthr):
    sy = (sy or "").lower().strip()
    sx = (sx or "").lower().strip()
    window = int(window or 100)
    zthr = float(zthr or 2)

    # Pull latest data
    ohlc_y = mdm.resample_ohlcv(sy, tf_rule)
    ohlc_x = mdm.resample_ohlcv(sx, tf_rule)

    # Persist snapshots (lightweight)
    storage.upsert_ohlcv(ohlc_y.tail(5), sy, tf_rule)
    storage.upsert_ohlcv(ohlc_x.tail(5), sx, tf_rule)

    # Analytics
    def themed_fig(title: str, height: int = 320):
        fig = go.Figure()
        fig.update_layout(
            title=title,
            template="plotly_dark",
            paper_bgcolor=THEME["card"],
            plot_bgcolor=THEME["card"],
            font_color=THEME["text"],
            margin=dict(l=40, r=20, t=60, b=40),
            height=height,
            xaxis=dict(gridcolor=THEME["border"]),
            yaxis=dict(gridcolor=THEME["border"]),
        )
        return fig

    price_y_fig = themed_fig(f"{sy.upper()} Price", height=300)
    price_x_fig = themed_fig(f"{sx.upper()} Price", height=300)
    spread_fig = themed_fig("Spread", height=280)
    zscore_fig = themed_fig("Z-Score", height=280)
    corr_fig = themed_fig("Rolling Correlation", height=260)

    stats_cards = html.Div(
        card_style({"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))", "gap": "10px"})
    )
    latest_alerts = ""
    last_updated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not ohlc_y.empty and not ohlc_x.empty:
        # Align on index
        df = pd.concat({sy: ohlc_y["close"], sx: ohlc_x["close"]}, axis=1).dropna()
        if df.shape[0] > 10:
            pa = build_pair_analytics(df[sy], df[sx], window=window, add_intercept=True)

            # Charts
            # Y symbol price
            y_min, y_max = df[sy].min(), df[sy].max()
            pad_y = max((y_max - y_min) * 0.02, (y_max + y_min) * 0.0002)
            price_y_fig.add_trace(go.Scatter(x=df.index, y=df[sy], name=f"{sy.upper()} Close", line=dict(color=THEME["accent"])))
            price_y_fig.update_layout(
                title=f"{sy.upper()} Price ({tf_rule})",
                xaxis_title="Time",
                yaxis_title="Price",
                yaxis=dict(range=[y_min - pad_y, y_max + pad_y])
            )
            
            # X symbol price
            x_min, x_max = df[sx].min(), df[sx].max()
            pad_x = max((x_max - x_min) * 0.02, (x_max + x_min) * 0.0002)
            price_x_fig.add_trace(go.Scatter(x=df.index, y=df[sx], name=f"{sx.upper()} Close", line=dict(color=THEME["accent2"])))
            price_x_fig.update_layout(
                title=f"{sx.upper()} Price ({tf_rule})",
                xaxis_title="Time",
                yaxis_title="Price",
                yaxis=dict(range=[x_min - pad_x, x_max + pad_x])
            )

            spread, z = df[sy] - (pa.beta * df[sx] + pa.intercept), None
            m = spread.rolling(window, min_periods=max(10, window // 5)).mean()
            sd = spread.rolling(window, min_periods=max(10, window // 5)).std(ddof=0)
            z = (spread - m) / sd
            # Spread
            s_min, s_max = spread.min(), spread.max()
            pad_s = max((s_max - s_min) * 0.1, 0.05)
            spread_fig.add_trace(go.Scatter(x=spread.index, y=spread, name="Spread", line=dict(color=THEME["accent"])))
            spread_fig.update_layout(title="Spread", xaxis_title="Time", yaxis=dict(range=[s_min - pad_s, s_max + pad_s]))
            
            # Z-Score
            z_min, z_max = z.min(), z.max()
            pad_z = max((z_max - z_min) * 0.1, 0.5)
            zscore_fig.add_trace(go.Scatter(x=z.index, y=z, name="Z-Score", line=dict(color="#f97316")))
            zscore_fig.add_hline(y=zthr, line=dict(color="red", dash="dot"))
            zscore_fig.add_hline(y=-zthr, line=dict(color="red", dash="dot"))
            zscore_fig.update_layout(title="Z-Score", xaxis_title="Time", yaxis=dict(range=[z_min - pad_z, z_max + pad_z]))

            corr = df[sy].rolling(window).corr(df[sx])
            corr_fig.add_trace(go.Scatter(x=corr.index, y=corr, name="Rolling Corr", line=dict(color=THEME["accent2"])))
            corr_fig.update_layout(title=f"Rolling Correlation (window={window})")

            def fmt(x, digits=3):
                if x is None or (isinstance(x, float) and np.isnan(x)):
                    return "–"
                return f"{x:.{digits}f}"

            stats_cards = html.Div([
                html.Div([
                    html.Div("Z-Score", style={"color": THEME["muted"], "fontWeight": 600}),
                    html.Div(fmt(pa.zscore_last, 2), style={"fontSize": "26px", "fontWeight": 800, "color": "#f97316"}),
                    html.Div(f"Thresh ±{zthr}", style={"color": THEME["muted"], "fontSize": "12px"}),
                ], style=card_style()),
                html.Div([
                    html.Div("Hedge Beta", style={"color": THEME["muted"], "fontWeight": 600}),
                    html.Div(fmt(pa.beta, 3), style={"fontSize": "24px", "fontWeight": 800, "color": THEME["accent"]}),
                    html.Div(f"Intercept {fmt(pa.intercept,3)}", style={"color": THEME["muted"], "fontSize": "12px"}),
                ], style=card_style()),
                html.Div([
                    html.Div("ADF p-value", style={"color": THEME["muted"], "fontWeight": 600}),
                    html.Div(pa.adf_pvalue if pa.adf_pvalue is not None else "–", style={"fontSize": "24px", "fontWeight": 800, "color": THEME["text"]}),
                    html.Div("Stationarity test", style={"color": THEME["muted"], "fontSize": "12px"}),
                ], style=card_style()),
                html.Div([
                    html.Div("Rolling Corr", style={"color": THEME["muted"], "fontWeight": 600}),
                    html.Div(fmt(pa.corr_last, 3), style={"fontSize": "24px", "fontWeight": 800, "color": THEME["accent2"]}),
                    html.Div(f"Window {window}", style={"color": THEME["muted"], "fontSize": "12px"}),
                ], style=card_style()),
                html.Div([
                    html.Div("Last Updated", style={"color": THEME["muted"], "fontWeight": 600}),
                    html.Div(last_updated, style={"fontSize": "16px", "fontWeight": 700, "color": THEME["text"]}),
                    html.Div(f"TF {tf_rule}", style={"color": THEME["muted"], "fontSize": "12px"}),
                ], style=card_style()),
            ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))", "gap": "10px"})

            # Alerts
            alerts.clear_rules()
            alerts.add_rule(AlertRule(symbol_y=sy, symbol_x=sx, threshold=zthr, direction="both"))
            alerts.evaluate(sy, sx, pa.zscore_last)
            latest_alerts = "\n".join([f"[{a.ts.isoformat()}] {a.message}" for a in alerts.events][-20:])

    return stats_cards, price_y_fig, price_x_fig, spread_fig, zscore_fig, corr_fig, latest_alerts


@app.callback(
    Output("tick-interval", "disabled"),
    Input("start", "n_clicks"),
    Input("stop", "n_clicks"),
    State("sym-y", "value"),
    State("sym-x", "value"),
    prevent_initial_call=True,
)
def start_stop(start_clicks, stop_clicks, sy, sx):
    ctx = dash_ctx_triggered()
    if ctx == "start":
        sy = (sy or "").lower().strip()
        sx = (sx or "").lower().strip()
        threading.Thread(target=start_stream, args=([sy, sx],), daemon=True).start()
        return False
    elif ctx == "stop":
        mdm.stop()
        return True
    return False


def dash_ctx_triggered():
    # helper to get which button triggered
    from dash import callback_context
    if not callback_context.triggered:
        return None
    return callback_context.triggered[0]["prop_id"].split(".")[0]


@app.callback(
    Output("download_data", "data"),
    Input("download_btn", "n_clicks"),
    State("sym-y", "value"),
    State("sym-x", "value"),
    State("timeframe", "value"),
    prevent_initial_call=True,
)
def download_csv(_, sy, sx, tf_rule):
    sy = (sy or "").lower().strip()
    sx = (sx or "").lower().strip()
    oy = mdm.resample_ohlcv(sy, tf_rule)
    ox = mdm.resample_ohlcv(sx, tf_rule)
    df = pd.concat({f"{sy}_close": oy["close"], f"{sx}_close": ox["close"]}, axis=1)
    csv = df.to_csv()
    return dict(content=csv, filename=f"processed_{sy}_{sx}_{tf_rule}.csv")


@app.callback(
    Output("upload_status", "children"),
    Input("upload-ohlc", "contents"),
    State("upload-ohlc", "filename"),
    prevent_initial_call=True,
)
def upload_ohlc(contents, filename):
    # minimal handler to accept user OHLC CSV; integrate as needed later
    if not contents:
        return ""
    return f"Uploaded: {filename}"


if __name__ == "__main__":
    # Start default streams
    threading.Thread(target=start_stream, args=(DEFAULT_SYMBOLS,), daemon=True).start()
    # Bind on all interfaces for easier access (replace port if needed)
    app.run_server(host="0.0.0.0", port=8050, debug=False)
