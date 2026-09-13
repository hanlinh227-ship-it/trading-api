from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import requests

from data.audit import audit_bars
from data.binance_usdm import INTERVAL_MS, download_archive_day, download_archive_month, fetch_klines


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_cached(csv_path: Path, manifest_path: Path) -> pd.DataFrame | None:
    if not csv_path.exists() or not manifest_path.exists():
        return None
    try:
        meta = json.loads(manifest_path.read_text())
        if meta.get("sha256") != _sha256(csv_path):
            return None
        return pd.read_csv(csv_path)
    except Exception:
        return None


def _store_cached(df: pd.DataFrame, csv_path: Path, manifest_path: Path, meta: dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, compression="gzip")
    payload = {**meta, "sha256": _sha256(csv_path)}
    manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2))


def load_history(symbol: str, interval: str, start: str, end: str, cache_dir: Path) -> tuple[pd.DataFrame, dict]:
    step = INTERVAL_MS[interval]
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    month_starts = pd.date_range(start=start_ts.replace(day=1).normalize(), end=end_ts, freq="MS", tz="UTC")
    session = requests.Session()
    frames: list[pd.DataFrame] = []
    source_counts = {"monthly_archive": 0, "daily_archive": 0, "rest": 0}
    for month_start in month_starts:
        next_month = month_start + pd.offsets.MonthBegin(1)
        window_start = max(start_ts, month_start)
        window_end = min(end_ts, next_month - pd.Timedelta(milliseconds=1))
        key = f"{symbol}-{interval}-{window_start.strftime('%Y%m%d')}-{window_end.strftime('%Y%m%d')}"
        csv_path = cache_dir / symbol / f"{key}.csv.gz"
        manifest_path = cache_dir / symbol / f"{key}.json"
        cached = _load_cached(csv_path, manifest_path)
        if cached is not None:
            frames.append(cached)
            continue
        full_month = window_start == month_start and window_end >= next_month - pd.Timedelta(days=1)
        frame = None
        source = None
        if full_month:
            frame = download_archive_month(symbol, interval, month_start.strftime("%Y-%m"), session=session)
            if frame is not None:
                source = "monthly_archive"
        if frame is None:
            daily_frames = []
            day = window_start.normalize()
            daily_ok = True
            while day <= window_end.normalize():
                daily = download_archive_day(symbol, interval, day.strftime("%Y-%m-%d"), session=session)
                if daily is None:
                    daily_ok = False
                    break
                daily_frames.append(daily)
                day += pd.Timedelta(days=1)
            if daily_ok and daily_frames:
                frame = pd.concat(daily_frames, ignore_index=True)
                source = "daily_archive"
        if frame is None:
            frame = fetch_klines(symbol, interval, int(window_start.timestamp() * 1000), int(window_end.timestamp() * 1000), session=session)
            source = "rest"
        lo = int(window_start.timestamp() * 1000)
        hi = int(window_end.timestamp() * 1000)
        frame = frame[(frame.open_time >= lo) & (frame.open_time <= hi)].copy().reset_index(drop=True)
        audit = audit_bars(frame, step)
        _store_cached(frame, csv_path, manifest_path, {"symbol": symbol, "interval": interval, "source": source, **audit.to_dict()})
        source_counts[source] += 1
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True).sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    audit = audit_bars(out, step)
    return out, {"audit": audit.to_dict(), "sources": source_counts}
