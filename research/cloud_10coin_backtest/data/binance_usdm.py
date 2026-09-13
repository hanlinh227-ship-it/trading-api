from __future__ import annotations

import io
import time
import zipfile
from typing import Iterable

import pandas as pd
import requests

REST_BASE = "https://fapi.binance.com/fapi/v1/klines"
ARCHIVE_BASE = "https://data.binance.vision/data/futures/um"
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trade_count", "taker_buy_base", "taker_buy_quote", "ignore",
]
OUTPUT_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "quote_volume",
    "trade_count", "taker_buy_base", "taker_buy_quote",
]


def _normalise_timestamp(value: object) -> int:
    ts = int(float(value))
    if ts > 100_000_000_000_000:
        ts //= 1000
    return ts


def parse_kline(row: list) -> dict:
    if len(row) < 11:
        raise ValueError(f"expected >=11 kline fields, got {len(row)}")
    return {
        "open_time": _normalise_timestamp(row[0]),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
        "quote_volume": float(row[7]),
        "trade_count": int(float(row[8])),
        "taker_buy_base": float(row[9]),
        "taker_buy_quote": float(row[10]),
    }


def _frame_from_raw(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    raw = raw.iloc[:, :12].copy()
    first = str(raw.iloc[0, 0]).lower().strip()
    if first in {"open_time", "opentime"}:
        raw = raw.iloc[1:].reset_index(drop=True)
    raw.columns = KLINE_COLUMNS[: raw.shape[1]]
    out = pd.DataFrame()
    out["open_time"] = pd.to_numeric(raw["open_time"], errors="coerce").astype("Int64")
    large = out["open_time"] > 100_000_000_000_000
    out.loc[large, "open_time"] = out.loc[large, "open_time"] // 1000
    for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]:
        out[col] = pd.to_numeric(raw[col], errors="coerce")
    out["trade_count"] = pd.to_numeric(raw["trade_count"], errors="coerce").fillna(0).astype("int64")
    out = out.dropna(subset=["open_time", "open", "high", "low", "close"]).copy()
    out["open_time"] = out["open_time"].astype("int64")
    return out[OUTPUT_COLUMNS].sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)


def rows_to_frame(rows: Iterable[list]) -> pd.DataFrame:
    return pd.DataFrame([parse_kline(list(row)) for row in rows], columns=OUTPUT_COLUMNS)


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, session: requests.Session | None = None) -> pd.DataFrame:
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval {interval}")
    s = session or requests.Session()
    cur = int(start_ms)
    rows: list[list] = []
    step = INTERVAL_MS[interval]
    while cur <= end_ms:
        params = {"symbol": symbol, "interval": interval, "startTime": cur, "endTime": int(end_ms), "limit": 1500}
        last_error: Exception | None = None
        batch = None
        for attempt in range(5):
            try:
                r = s.get(REST_BASE, params=params, timeout=30)
                r.raise_for_status()
                batch = r.json()
                if not isinstance(batch, list):
                    raise RuntimeError(f"unexpected Binance response: {batch!r}")
                break
            except Exception as exc:  # pragma: no cover - network retry branch
                last_error = exc
                time.sleep(min(4.0, 0.25 * (2**attempt)))
        if batch is None:
            raise RuntimeError(f"Binance USD-M fetch failed: {last_error}")
        if not batch:
            break
        rows.extend(batch)
        nxt = _normalise_timestamp(batch[-1][0]) + step
        if nxt <= cur:
            raise RuntimeError("Binance pagination stalled")
        cur = nxt
        if len(batch) < 1500:
            break
        time.sleep(0.02)
    df = rows_to_frame(rows)
    return df[(df.open_time >= start_ms) & (df.open_time <= end_ms)].reset_index(drop=True)


def _read_zip_response(content: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise RuntimeError("Binance archive contained no CSV")
        raw = pd.read_csv(zf.open(names[0]), header=None)
    return _frame_from_raw(raw)


def download_archive_month(symbol: str, interval: str, month: str, session: requests.Session | None = None) -> pd.DataFrame | None:
    s = session or requests.Session()
    url = f"{ARCHIVE_BASE}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"
    r = s.get(url, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return _read_zip_response(r.content)


def download_archive_day(symbol: str, interval: str, day: str, session: requests.Session | None = None) -> pd.DataFrame | None:
    s = session or requests.Session()
    url = f"{ARCHIVE_BASE}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{day}.zip"
    r = s.get(url, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return _read_zip_response(r.content)
