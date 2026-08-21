import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/trading/trading-api/auto-futures-v1')
STATE = ROOT / 'state'
POSITIONS = STATE / 'paper_positions.json'
CONSENSUS = STATE / 'ai_consensus.json'
OUT = STATE / 'position_management.json'
BASE = 'https://fapi.binance.com'


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def price(symbol):
    with urllib.request.urlopen(f'{BASE}/fapi/v1/ticker/price?symbol={symbol}', timeout=10) as r:
        return float(json.loads(r.read().decode())['price'])


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def main():
    state = load(POSITIONS, {'positions': []})
    consensus = load(CONSENSUS, {'symbols': {}})
    decisions = {}

    for p in state.get('positions', []):
        if p.get('status') != 'OPEN':
            continue
        symbol = p.get('symbol')
        side = str(p.get('side', '')).upper()
        entry = float(p.get('entry', 0) or 0)
        current_stop = float(p.get('stop_loss', 0) or 0)
        initial_risk = abs(float(p.get('initial_risk', 0) or 0))
        if not symbol or entry <= 0 or initial_risk <= 0:
            continue
        try:
            px = price(symbol)
        except Exception:
            continue

        ai = consensus.get('symbols', {}).get(symbol, {})
        reviews = ai.get('reviews', {}) or {}
        actions = [str((r or {}).get('action', 'WAIT')).upper() for r in reviews.values() if isinstance(r, dict)]
        confs = [float((r or {}).get('confidence', 0) or 0) for r in reviews.values() if isinstance(r, dict)]
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        same = actions.count(side)
        opposite = actions.count('SHORT' if side == 'LONG' else 'LONG')

        move_r = ((px - entry) / initial_risk) if side == 'LONG' else ((entry - px) / initial_risk)
        trail_factor = 0.90
        mode = 'HOLD_STRUCTURE'

        # 3-AI agreement can let winners breathe slightly; weakening consensus tightens risk.
        if same == 3 and avg_conf >= 70 and opposite == 0:
            trail_factor = 0.95
            mode = 'AI_STRONG_HOLD'
        elif opposite >= 1:
            trail_factor = 0.55
            mode = 'AI_DEFENSIVE_TIGHTEN'
        elif same < 2 or avg_conf < 55:
            trail_factor = 0.70
            mode = 'AI_CAUTION_TIGHTEN'

        proposed = current_stop
        if move_r >= 0.75:
            be_buffer = 0.05 * initial_risk
            be = entry + be_buffer if side == 'LONG' else entry - be_buffer
            proposed = max(proposed, be) if side == 'LONG' else min(proposed, be)
            mode += '+BE'

        if move_r >= 1.0:
            distance = initial_risk * trail_factor
            trailing = px - distance if side == 'LONG' else px + distance
            proposed = max(proposed, trailing) if side == 'LONG' else min(proposed, trailing)
            mode += '+TRAIL'

        # Hard invariant: management may NEVER widen the stop beyond the current stop.
        if side == 'LONG':
            proposed = max(current_stop, proposed)
            proposed = min(proposed, px - initial_risk * 0.05) if px > entry else proposed
        else:
            proposed = min(current_stop, proposed)
            proposed = max(proposed, px + initial_risk * 0.05) if px < entry else proposed

        decisions[symbol] = {
            'symbol': symbol,
            'side': side,
            'price': px,
            'entry': entry,
            'current_stop': current_stop,
            'proposed_stop': proposed,
            'move_r': round(move_r, 4),
            'ai_actions': actions,
            'ai_average_confidence': round(avg_conf, 2),
            'same_direction_ai': same,
            'opposition_ai': opposite,
            'mode': mode,
            'trail_factor_r': trail_factor,
            'may_widen_stop': False,
            'may_increase_risk': False,
        }

    payload = {
        'generated_at': now(),
        'engine': 'V6_BOUNDED_3AI_POSITION_GUARDIAN',
        'policy': {
            'review_every_pipeline': True,
            'never_widen_stop': True,
            'never_increase_post_entry_risk': True,
            'breakeven_from_r': 0.75,
            'trailing_from_r': 1.0,
        },
        'decisions': decisions,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    print('=' * 56)
    print('3-AI POSITION GUARDIAN')
    print('=' * 56)
    print('OPEN REVIEWED:', len(decisions))
    for s, d in decisions.items():
        print(s, '|', d['mode'], '| R', d['move_r'], '| SL', d['current_stop'], '->', round(d['proposed_stop'], 8), '| AI', '/'.join(d['ai_actions']))
    print('HARD RULE: NEVER WIDEN STOP / NEVER INCREASE RISK')


if __name__ == '__main__':
    main()
