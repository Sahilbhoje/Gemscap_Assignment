import asyncio
import json
import threading
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import websockets


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Tick:
    symbol: str
    ts: datetime
    price: float
    size: float


def normalize_trade(msg: dict) -> Optional[Tick]:
    try:
        symbol = msg["s"].lower()
        # Binance futures trade message has event time 'E' and trade time 'T'
        t = msg.get("T") or msg.get("E")
        ts = datetime.fromtimestamp(t / 1000.0, tz=timezone.utc)
        price = float(msg["p"])  # price
        qty = float(msg["q"])  # quantity
        return Tick(symbol=symbol, ts=ts, price=price, size=qty)
    except Exception:
        return None


class MarketDataManager:
    def __init__(self, max_ticks_per_symbol: int = 200_000):
        self._ticks: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_ticks_per_symbol))
        self._lock = threading.RLock()
        self._symbols: List[str] = []
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, symbols: List[str]):
        symbols = [s.lower() for s in symbols]
        with self._lock:
            self._symbols = symbols
        if self._thread and self._thread.is_alive():
            # Restart subscriptions
            self._schedule(lambda: self._restart(symbols))
            return
        # Start background loop
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._schedule(lambda: self._restart(symbols))

    def stop(self):
        self._schedule(self._cancel_all)

    def get_ticks_df(self, symbol: str, since_seconds: Optional[int] = None) -> pd.DataFrame:
        symbol = symbol.lower()
        with self._lock:
            arr = list(self._ticks[symbol])
        if not arr:
            return pd.DataFrame(columns=["ts", "price", "size"]).set_index("ts")
        df = pd.DataFrame([{ "ts": t.ts, "price": t.price, "size": t.size } for t in arr])
        df = df.set_index("ts").sort_index()
        if since_seconds:
            cutoff = datetime.now(timezone.utc) - pd.Timedelta(seconds=since_seconds)
            df = df[df.index >= cutoff]
        return df

    def resample_ohlcv(self, symbol: str, rule: str) -> pd.DataFrame:
        df = self.get_ticks_df(symbol)
        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"]) 
        ohlc = df["price"].resample(rule).ohlc()
        vol = df["size"].resample(rule).sum().rename("volume")
        out = pd.concat([ohlc, vol], axis=1).dropna(how="all")
        return out

    # Internal async machinery
    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _schedule(self, coro_factory):
        if not self._loop:
            return
        def runner():
            return coro_factory()
        self._loop.call_soon_threadsafe(runner)

    async def _connect_symbol(self, symbol: str):
        url = f"wss://fstream.binance.com/ws/{symbol}@trade"
        backoff = 1
        while True:
            try:
                async with websockets.connect(url, ping_interval=15, ping_timeout=30) as ws:
                    backoff = 1
                    while True:
                        raw = await ws.recv()
                        try:
                            msg = json.loads(raw)
                            if msg.get("e") == "trade":
                                t = normalize_trade(msg)
                                if t:
                                    with self._lock:
                                        self._ticks[t.symbol].append(t)
                        except Exception:
                            continue
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def _cancel_all(self):
        for s, task in list(self._ws_tasks.items()):
            task.cancel()
        self._ws_tasks.clear()

    def _restart(self, symbols: List[str]):
        self._cancel_all()
        for sym in symbols:
            task = self._loop.create_task(self._connect_symbol(sym))
            self._ws_tasks[sym] = task
