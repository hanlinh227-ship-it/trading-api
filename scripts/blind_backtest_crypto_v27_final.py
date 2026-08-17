#!/usr/bin/env python3
import json, os, statistics, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core
import blind_backtest_crypto_v22 as v22
import blind_backtest_crypto_v24 as v24

# FINAL locked random blind test.
# Random cutoff was selected before outcomes were inspected, after confirming no 2026-04-* cutoff existed in repo search.
LABEL = 'BLIND_RANDOM_APR09'
CUTOFF = '2026-04-09T12:00:00Z'
OBSERVE_MS = 15 * 60_000
FLOW_WINDOW_MS = 5 * 60_000


def summarize(rows):
    resolved = [r for r in rows if r.get('outcome', {}).get('result') in ('TP', 'SL')]
    wins = [r for r in resolved if r['outcome']['result'] == 'TP']
    losses = [r for r in resolved if r['outcome']['result'] == 'SL']
    total_r = sum(r['plannedRR'] if r['outcome']['result'] == 'TP' else -1 for r in resolved)

    d6 = [r for r in rows if r.get('direction6hCorrect') is not None]
    d24 = [r for r in rows if r.get('direction24hCorrect') is not None]
    c6 = sum(1 for r in d6 if r['direction6hCorrect'])
    c24 = sum(1 for r in d24 if r['direction24hCorrect'])

    return {
        'universe': len(v6.COINS),
        'tested': len(rows),
        'resolved': len(resolved),
        'wins': len(wins),
        'losses': len(losses),
        'unresolved': len(rows) - len(resolved),
        'winRateResolved': round(100 * len(wins) / len(resolved), 2) if resolved else None,
        'avgPlannedRR': round(sum(r['plannedRR'] for r in resolved) / len(resolved), 3) if resolved else None,
        'expectancyR': round(total_r / len(resolved), 3) if resolved else None,
        'direction6hCorrect': c6,
        'direction6hTotal': len(d6),
        'direction6hAccuracy': round(100 * c6 / len(d6), 2) if d6 else None,
        'direction24hCorrect': c24,
        'direction24hTotal': len(d24),
        'direction24hAccuracy': round(100 * c24 / len(d24), 2) if d24 else None,
    }


def directional_correct(side, entry, post, horizon_ms):
    if not post or not entry:
        return None
    end = post[0]['ts'] + horizon_ms
    usable = [x for x in post if x['ts'] < end]
    if not usable:
        return None
    close = usable[-1]['close']
    signed = (close - entry) if side == 'BUY' else (entry - close)
    return signed > 0


def main():
    cut = v6.iso_ms(CUTOFF)
    entry_t = cut + OBSERVE_MS
    flow_start = entry_t - FLOW_WINDOW_MS

    bs, bf, bm = v6.load_frames('BTC', cut)
    prepared = []
    errors = []

    for sym in v6.COINS:
        try:
            source, fr, su = (bs, bf, bm) if sym == 'BTC' else v6.load_frames(sym, cut)
            _, _, _, _, _, _, model = v6.choose(sym, su, fr, bf, bm)
            features = core.features(sym, fr, su, bf)
            prepared.append({
                'sym': sym,
                'source': source,
                'fr': fr,
                'su': su,
                'model': model,
                'features': features,
            })
        except Exception as e:
            errors.append({'symbol': sym + 'USDT', 'error': str(e)})

    price_breadth = sum(x['features']['r24'] > 0 for x in prepared) / len(prepared) if prepared else 0.5

    available_flows = []
    for r in prepared:
        try:
            flow = v22.tradeflow(r['sym'], flow_start, entry_t)
        except Exception as e:
            flow = {'available': False, 'n': 0, 'ofi': 0.0, 'lastPx': None, 'error': str(e)}
        r['flow'] = flow
        if flow.get('available'):
            available_flows.append(flow)

    flow_breadth = sum(f['ofi'] > 0 for f in available_flows) / len(available_flows) if available_flows else 0.5
    flow_median = statistics.median([f['ofi'] for f in available_flows]) if available_flows else 0.0
    market_regime = v24.classify_market(price_breadth, flow_breadth, flow_median)

    rows = []
    for r in prepared:
        sym = r['sym']
        flow = r['flow']
        macro = v22.macro_score(sym, r['features'], r['model'], price_breadth)
        all_future = v22.future(r['source'], sym, cut)
        obs = [x for x in all_future if x['ts'] < entry_t]
        post = [x for x in all_future if x['ts'] >= entry_t]

        before_flow = [x for x in all_future if x['ts'] < flow_start]
        micro_pre = before_flow[-1]['close'] if before_flow else (obs[0]['open'] if obs else r['fr']['M5'][-1]['close'])
        fallback_entry = obs[-1]['close'] if obs else r['fr']['M5'][-1]['close']
        entry = flow.get('lastPx') if flow.get('lastPx') is not None else fallback_entry

        micro, move = v22.micro_score(flow, micro_pre, r['su']['M15'].get('atr14'))
        side, score, rr = v24.decide(macro, micro, flow, move, r['model'], market_regime)
        sl, tp, risk = v22.levels(sym, side, entry, r['su'], r['fr'], rr)
        outcome = v22.evaluate(side, entry, sl, tp, post)

        d6 = directional_correct(side, entry, post, 6 * 3600_000)
        d24 = directional_correct(side, entry, post, 24 * 3600_000)

        rows.append({
            'symbol': sym + 'USDT',
            'cutoff': CUTOFF,
            'entryTimeMs': entry_t,
            'blind': True,
            'decision': side,
            'marketRegime': market_regime,
            'priceBreadth': round(price_breadth, 3),
            'flowBreadth': round(flow_breadth, 3),
            'flowMedian': round(flow_median, 3),
            'macroScore': round(macro, 3),
            'microScore': round(micro, 3),
            'score': round(score, 3),
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'risk': risk,
            'plannedRR': rr,
            'flow': flow,
            'microMoveATR': round(move, 3),
            'model': r['model'],
            'direction6hCorrect': d6,
            'direction24hCorrect': d24,
            'outcome': outcome,
        })

    payload = {
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'method': (
            'V27 final locked random blind test. Retains V24 directional/scoring architecture and V22 structural SL/RR logic, '
            'but delays MARKET entry until one complete 15-minute observation window has elapsed. The final 5 minutes of that '
            'completed M15 window supply OKX taker-flow confirmation, preserving the original microflow horizon while avoiding the '
            'first-5m entry timing that repeatedly suffered fast barrier failures. No WAIT/NO TRADE is allowed; every valid Breakout '
            'universe coin still receives BUY or SELL. Random April cutoff was fixed before outcomes were inspected.'
        ),
        'label': LABEL,
        'cutoff': CUTOFF,
        'entryTimeMs': entry_t,
        'marketRegime': market_regime,
        'priceBreadth': round(price_breadth, 3),
        'flowBreadth': round(flow_breadth, 3),
        'flowMedian': round(flow_median, 3),
        'flowCoverage': round(len(available_flows) / len(prepared), 3) if prepared else 0,
        'dataErrors': errors,
        'summary': summarize(rows),
        'tests': rows,
    }

    with open('data/blind_backtest_v27_final.json', 'w') as f:
        json.dump(payload, f, indent=2)

    compact = [
        {
            'symbol': r['symbol'],
            'side': r['decision'],
            'result': r['outcome']['result'],
            'rr': r['plannedRR'],
            'dir6h': r['direction6hCorrect'],
            'dir24h': r['direction24hCorrect'],
        }
        for r in rows
    ]
    print(json.dumps({
        'cutoff': CUTOFF,
        'entryTime': v6.ms_iso(entry_t),
        'marketRegime': market_regime,
        'priceBreadth': round(price_breadth, 3),
        'flowBreadth': round(flow_breadth, 3),
        'flowMedian': round(flow_median, 3),
        'flowCoverage': payload['flowCoverage'],
        'summary': payload['summary'],
        'dataErrors': errors,
        'coinResults': compact,
    }, indent=2))


if __name__ == '__main__':
    main()
