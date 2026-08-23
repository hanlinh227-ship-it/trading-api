#!/usr/bin/env python3
# V11 MTF sharded runner: FAST / FINAL modes with deterministic sharding.
# FAST uses chronological DEV/VALIDATION only.  FINAL uses frozen profiles and untouched holdout.
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
import v11_mtf_data_cache as dcache
import v11_backtest_mtf as engine

VERSION = 'V11-MTF-RUN-R1'
DEFAULT_CACHE_DIR = ROOT / 'data/v11_mtf_cache'
DEFAULT_OUT_DIR = ROOT / 'data/v11_mtf_out'
DEFAULT_PROFILES = ROOT / 'data/v11_mtf_profiles.json'

def parse_dt_arg(s):
    d = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['fast', 'final'], default=os.environ.get('V11_MODE', 'fast'))
    ap.add_argument('--cache-dir', default=os.environ.get('V11_CACHE_DIR', str(DEFAULT_CACHE_DIR)))
    ap.add_argument('--out-dir', default=os.environ.get('V11_OUT_DIR', str(DEFAULT_OUT_DIR)))
    ap.add_argument('--shard-index', type=int, default=int(os.environ.get('V11_SHARD_INDEX', '0')))
    ap.add_argument('--shard-count', type=int, default=int(os.environ.get('V11_SHARD_COUNT', '1')))
    ap.add_argument('--history-days', type=int, default=int(os.environ.get('V11_HISTORY_DAYS', '400')))
    ap.add_argument('--history-start')
    ap.add_argument('--history-end')
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--profiles', default=str(DEFAULT_PROFILES))
    return ap.parse_args()

def catalog_symbols():
    cats = dcache.load_catalog()
    return [(s, m) for m in ('forex', 'crypto', 'metal', 'index') for s in cats[m]]

def shard_items(items, index, count):
    if count < 1:
        count = 1
    if index < 0 or index >= count:
        return []
    return [it for i, it in enumerate(items) if i % count == index]

def ensure_cache(items, cache_dir, start_ts, end_ts):
    for symbol, market in items:
        entry, _, key = dcache.load_cache(cache_dir, symbol, market, start_ts, end_ts)
        if entry:
            print('CACHE_HIT', market, symbol, len(entry['rows']), entry['source'], flush=True)
            continue
        try:
            rows, source, exact, instrument, spec = dcache.fetch_raw(symbol, market, start_ts, end_ts)
            dcache.save_cache(cache_dir, key, symbol, market, spec, rows, source, exact, start_ts, end_ts)
            print('FETCH_CACHE', market, symbol, len(rows), source, flush=True)
        except Exception as e:
            print('FETCH_FAIL', market, symbol, str(e)[:160], flush=True)

def run_shard(items, mode, cache_dir, out_dir, profiles_path, start_ts, end_ts, shard_index, shard_count):
    cache_dir = Path(cache_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles_all = {}
    if mode == 'final':
        try:
            profiles_all = json.loads(Path(profiles_path).read_text(encoding='utf-8')).get('symbols', {})
        except Exception:
            profiles_all = {}
    results = {}
    for pos, (symbol, market) in enumerate(items, 1):
        entry, _, _ = dcache.load_cache(cache_dir, symbol, market, start_ts, end_ts)
        if not entry:
            results[symbol] = {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['DATA_UNAVAILABLE'], 'mode': mode}
            print('RESULT', symbol, 'FAIL', None, ['DATA_UNAVAILABLE'], flush=True)
            print('SHARD_PROGRESS', pos, len(items), flush=True)
            continue
        rows = entry['rows']
        if mode == 'fast':
            result = engine.run_fast(symbol, market, rows, cache_dir)
        else:
            profile = profiles_all.get(symbol)
            if not profile:
                result = {'symbol': symbol, 'market': market, 'pass': False, 'reasons': ['NO_PROFILE'], 'mode': mode}
            else:
                result = engine.run_final(symbol, market, rows, cache_dir, profile)
        results[symbol] = result
        metric = (result.get('validation') or result.get('oos') or {}).get('winRate')
        print('RESULT', symbol, 'PASS' if result.get('pass') else 'FAIL', metric, result.get('reasons'), flush=True)
        print('SHARD_PROGRESS', pos, len(items), flush=True)
    shard_obj = {'version': VERSION, 'mode': mode, 'shardIndex': shard_index, 'shardCount': shard_count, 'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'symbols': results}
    (out_dir / f'v11_mtf_shard_{shard_index}.json').write_text(json.dumps(shard_obj, ensure_ascii=False, indent=2), encoding='utf-8')
    if mode == 'fast':
        profs = {'version': engine.VERSION, 'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'symbols': {s: r.get('profile') for s, r in results.items() if r.get('profile')}}
        (out_dir / f'v11_mtf_profiles_shard_{shard_index}.json').write_text(json.dumps(profs, indent=2), encoding='utf-8')
    return shard_obj

def merge_shards(out_dir, merged_path, profiles_path):
    files = sorted(out_dir.glob('v11_mtf_shard_*.json'))
    symbols = {}
    modes = []
    for f in files:
        obj = json.loads(f.read_text(encoding='utf-8'))
        symbols.update(obj.get('symbols', {}))
        modes.append(obj.get('mode'))
    merged = {'version': VERSION, 'mergedShards': len(files), 'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'modes': sorted(set(modes)), 'symbols': symbols}
    Path(merged_path).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    profile_files = sorted(out_dir.glob('v11_mtf_profiles_shard_*.json'))
    if profile_files:
        profs = {'version': engine.VERSION, 'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'symbols': {}}
        for pf in profile_files:
            profs['symbols'].update(json.loads(pf.read_text(encoding='utf-8')).get('symbols', {}))
        Path(profiles_path).write_text(json.dumps(profs, indent=2), encoding='utf-8')
    print('MERGED', len(symbols), flush=True)

def main():
    args = parse_args()
    if args.merge:
        merge_shards(Path(args.out_dir), ROOT / 'data/v11_mtf_merged.json', args.profiles)
        return 0
    if args.shard_index < 0 or args.shard_count < 1 or args.shard_index >= args.shard_count:
        print('SHARD_BAD', args.shard_index, args.shard_count, flush=True)
        return 2
    end_dt = parse_dt_arg(args.history_end) if args.history_end else datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_dt = parse_dt_arg(args.history_start) if args.history_start else end_dt - timedelta(days=args.history_days)
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    items = shard_items(sorted(catalog_symbols(), key=lambda x: x[0]), args.shard_index, args.shard_count)
    if not items:
        print('SHARD_EMPTY', args.shard_index, args.shard_count, flush=True)
        return 0
    print('SHARD_START', args.shard_index, args.shard_count, len(items), flush=True)
    ensure_cache(items, args.cache_dir, start_ts, end_ts)
    run_shard(items, args.mode, args.cache_dir, args.out_dir, args.profiles, start_ts, end_ts, args.shard_index, args.shard_count)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
