#!/usr/bin/env python3
"""Quota-safe grouped historical fetcher for V76 research.

28 Forex pairs are split into four 7-symbol Twelve Data batch requests. Each
M5 request asks for 5000 points, so batch_size * outputsize = 35,000, safely
below the observed 100,000 guard. The four groups run in parallel and together
consume the same 28 symbol credits as one 28-symbol batch, but with much smaller
HTTP payloads per connection.

This module is research-only and is never imported by V75 live workflows.
"""
from __future__ import annotations

import concurrent.futures as cf
import time
from datetime import datetime, timezone

import research_v76_entry_forex as base

GROUP_SIZE = 7
M5_OUTPUTSIZE = 5000
D1_OUTPUTSIZE = 500


def _groups(items, n=GROUP_SIZE):
    return [items[i:i+n] for i in range(0, len(items), n)]


def _fetch_group(group, interval, outputsize, end_date=None):
    return base.extract_batch(base.batch_request(group, interval, outputsize, end_date))


def _parallel_batches(symbols, interval, outputsize, end_date=None):
    merged = {}
    groups = _groups(symbols)
    with cf.ThreadPoolExecutor(max_workers=len(groups)) as ex:
        jobs = [ex.submit(_fetch_group, g, interval, outputsize, end_date) for g in groups]
        for fut in cf.as_completed(jobs):
            part = fut.result()
            overlap = set(merged).intersection(part)
            if overlap:
                raise RuntimeError(f"duplicate batch keys: {sorted(overlap)}")
            merged.update(part)
    return merged


def fetch_history(chunks=6, pause=62):
    markets = [base.MARKET[s] for s in base.PAIRS]
    history = {s: [] for s in base.PAIRS}
    fetch_log = []
    end_date = None

    for n in range(chunks):
        t0 = time.perf_counter()
        batch = _parallel_batches(markets, "5min", M5_OUTPUTSIZE, end_date)
        oldest = []
        sizes = []
        for symbol in base.PAIRS:
            obj = base.get_obj(batch, symbol)
            if obj is None:
                raise RuntimeError(f"missing M5 {base.MARKET[symbol]}; keys={list(batch)[:12]}")
            rows = base.parse_values(obj, base.MARKET[symbol])
            if not rows:
                raise RuntimeError(f"empty M5 {symbol} chunk {n+1}")
            history[symbol].extend(rows)
            sizes.append(len(rows))
            oldest.append(rows[0][0])
        fetch_log.append({
            "kind": "M5", "chunk": n+1, "endDate": end_date,
            "rowsMin": min(sizes), "rowsMax": max(sizes),
            "groupSize": GROUP_SIZE, "outputsize": M5_OUTPUTSIZE,
            "elapsedSeconds": round(time.perf_counter()-t0, 3),
        })
        end_date = base.iso(datetime.fromtimestamp(min(oldest)-300, tz=timezone.utc))
        # Protect the 55-credit minute. Each full 28-pair M5 chunk consumes 28
        # symbol credits; the next 28-credit chunk must be in the next window.
        time.sleep(pause)

    t0 = time.perf_counter()
    daily_batch = _parallel_batches(markets, "1day", D1_OUTPUTSIZE, None)
    daily = {}
    for symbol in base.PAIRS:
        obj = base.get_obj(daily_batch, symbol)
        if obj is None:
            raise RuntimeError(f"missing D1 {base.MARKET[symbol]}")
        daily[symbol] = base.parse_values(obj, base.MARKET[symbol])
        dedup = {row[0]: row for row in history[symbol]}
        history[symbol] = [dedup[k] for k in sorted(dedup)]
    fetch_log.append({
        "kind": "D1", "rowsMin": min(len(daily[s]) for s in base.PAIRS),
        "rowsMax": max(len(daily[s]) for s in base.PAIRS),
        "groupSize": GROUP_SIZE, "outputsize": D1_OUTPUTSIZE,
        "elapsedSeconds": round(time.perf_counter()-t0, 3),
    })
    return history, daily, fetch_log


def self_test():
    assert len(base.PAIRS) == 28
    assert len(_groups([base.MARKET[s] for s in base.PAIRS])) == 4
    assert GROUP_SIZE * M5_OUTPUTSIZE == 35000
    print({"groups": 4, "groupSize": GROUP_SIZE, "m5Outputsize": M5_OUTPUTSIZE, "batchPageProduct": GROUP_SIZE*M5_OUTPUTSIZE, "selfTest": "PASS"})


if __name__ == "__main__":
    self_test()
