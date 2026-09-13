from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class OrderCandidate:
    signal_index: int
    side: str
    entry: float
    stop: float
    max_fill_bars: int = 12
    max_hold_bars: int = 144
    quality: float = 0.0
    family: str = ""


@dataclass(frozen=True)
class TradeResult:
    signal_index: int
    fill_index: int
    exit_index: int
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    rr1_hit: bool
    rr2_hit: bool
    exit_reason: str
    gross_r: float
    net_r: float


def _cost_r(entry: float, stop: float, roundtrip_cost_bps: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    return (entry * roundtrip_cost_bps / 10_000.0) / risk


def simulate_trade(candidate: OrderCandidate, bars: pd.DataFrame, rr=(1.0, 2.0), roundtrip_cost_bps: float = 0.0) -> TradeResult | None:
    side = candidate.side.upper()
    risk = candidate.entry - candidate.stop if side == "LONG" else candidate.stop - candidate.entry
    if risk <= 0:
        return None
    tp1 = candidate.entry + rr[0] * risk if side == "LONG" else candidate.entry - rr[0] * risk
    tp2 = candidate.entry + rr[1] * risk if side == "LONG" else candidate.entry - rr[1] * risk
    end_fill = min(len(bars) - 1, candidate.signal_index + candidate.max_fill_bars)
    fill_index = None
    for i in range(candidate.signal_index + 1, end_fill + 1):
        row = bars.iloc[i]
        if float(row.low) <= candidate.entry <= float(row.high):
            fill_index = i
            break
    if fill_index is None:
        return None
    cost = _cost_r(candidate.entry, candidate.stop, roundtrip_cost_bps)
    rr1_hit = False
    end_hold = min(len(bars) - 1, fill_index + candidate.max_hold_bars)
    for i in range(fill_index, end_hold + 1):
        row = bars.iloc[i]
        high, low = float(row.high), float(row.low)
        stop_hit = low <= candidate.stop if side == "LONG" else high >= candidate.stop
        tp1_now = high >= tp1 if side == "LONG" else low <= tp1
        tp2_now = high >= tp2 if side == "LONG" else low <= tp2
        if i == fill_index and stop_hit:
            return TradeResult(candidate.signal_index, fill_index, i, side, candidate.entry, candidate.stop, tp1, tp2, rr1_hit, False, "FILL_STOP_AMBIGUOUS", -1.0, -1.0 - cost)
        if stop_hit and (tp1_now or tp2_now):
            return TradeResult(candidate.signal_index, fill_index, i, side, candidate.entry, candidate.stop, tp1, tp2, rr1_hit, False, "STOP_AMBIGUOUS", -1.0, -1.0 - cost)
        if stop_hit:
            return TradeResult(candidate.signal_index, fill_index, i, side, candidate.entry, candidate.stop, tp1, tp2, rr1_hit, False, "STOP", -1.0, -1.0 - cost)
        if tp1_now:
            rr1_hit = True
        if tp2_now:
            return TradeResult(candidate.signal_index, fill_index, i, side, candidate.entry, candidate.stop, tp1, tp2, True, True, "TP2", 2.0, 2.0 - cost)
    last_close = float(bars.iloc[end_hold].close)
    gross = (last_close - candidate.entry) / risk if side == "LONG" else (candidate.entry - last_close) / risk
    return TradeResult(candidate.signal_index, fill_index, end_hold, side, candidate.entry, candidate.stop, tp1, tp2, rr1_hit, False, "TIMEOUT", gross, gross - cost)
