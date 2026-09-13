from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DataAudit:
    ok: bool
    rows: int
    gaps: int
    duplicates: int
    invalid_ohlc: int
    invalid_volume: int
    first_ts: int | None
    last_ts: int | None
    coverage: float

    def to_dict(self) -> dict:
        return asdict(self)


def audit_bars(df: pd.DataFrame, interval_ms: int) -> DataAudit:
    if df.empty:
        return DataAudit(False, 0, 0, 0, 0, 0, None, None, 0.0)
    work = df.sort_values("open_time").copy()
    duplicates = int(work["open_time"].duplicated().sum())
    times = work["open_time"].drop_duplicates().astype("int64").to_numpy()
    diffs = np.diff(times)
    gaps = int(sum(max(0, int(d // interval_ms) - 1) for d in diffs if d > interval_ms))
    invalid_ohlc = int((
        (work["high"] < work[["open", "close"]].max(axis=1))
        | (work["low"] > work[["open", "close"]].min(axis=1))
        | (work["high"] < work["low"])
        | (work[["open", "high", "low", "close"]].min(axis=1) <= 0)
    ).sum())
    invalid_volume = int(((work["volume"] < 0) | (work["trade_count"] < 0)).sum())
    expected = int((times[-1] - times[0]) // interval_ms + 1) if len(times) else 0
    coverage = float(len(times) / expected) if expected else 0.0
    ok = gaps == 0 and duplicates == 0 and invalid_ohlc == 0 and invalid_volume == 0
    return DataAudit(ok, len(work), gaps, duplicates, invalid_ohlc, invalid_volume, int(times[0]), int(times[-1]), coverage)
