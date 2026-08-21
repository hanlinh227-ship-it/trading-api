import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/opt/trading/trading-api/auto-futures-v1')
STATE = ROOT / 'state'
RISK = STATE / 'risk_decisions.json'
GUARD = STATE / 'execution_guard.json'
OUT = STATE / 'pending_trades.json'

TTL_BY_STRATEGY = {
    'BREAKOUT': 60,
    'MOMENTUM': 75,
    'TREND_PULLBACK': 120,
    'MEAN_REVERSION': 120,
}


def now():
    return datetime.now(timezone.utc)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def make_id(symbol, action, fingerprint):
    raw = f'{symbol}|{action}|{fingerprint}'.encode()
    return hashlib.sha256(raw).hexdigest()[:18]


def main():
    risk = load(RISK, {'decisions': {}})
    guard = load(GUARD, {'decisions': {}})
    old = load(OUT, {'items': []})
    old_by_id = {x.get('id'): x for x in old.get('items', []) if x.get('id')}
    t = now()
    items = []

    for symbol, decision in risk.get('decisions', {}).items():
        gd = guard.get('decisions', {}).get(symbol, {})
        if not decision.get('approved') or not gd.get('executable'):
            continue
        action = str(decision.get('action', 'WAIT')).upper()
        if action not in {'LONG', 'SHORT'}:
            continue
        fp = gd.get('fingerprint') or ''
        if not fp:
            continue
        strategy = str(decision.get('strategy', 'NO_EDGE')).upper()
        ttl = TTL_BY_STRATEGY.get(strategy, 90)
        trade_id = make_id(symbol, action, fp)
        previous = old_by_id.get(trade_id, {})
        created = previous.get('created_at') or t.isoformat()
        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
        expires = created_dt + timedelta(seconds=ttl)
        status = previous.get('status', 'PENDING')
        if status == 'PENDING' and t >= expires:
            status = 'EXPIRED'
        item = {
            'id': trade_id,
            'symbol': symbol,
            'action': action,
            'strategy': strategy,
            'entry': decision.get('entry'),
            'stop_loss': decision.get('stop_loss'),
            'tp1': decision.get('tp1'),
            'tp2': decision.get('tp2'),
            'tp3': decision.get('tp3'),
            'risk_pct': decision.get('risk_pct'),
            'ai_confidence': decision.get('ai_confidence'),
            'fingerprint': fp,
            'created_at': created,
            'expires_at': expires.isoformat(),
            'ttl_seconds': ttl,
            'status': status,
            'telegram_message_id': previous.get('telegram_message_id'),
        }
        items.append(item)

    # Preserve unresolved recent items so Telegram can mark them expired/rejected cleanly.
    current_ids = {x['id'] for x in items}
    for item in old.get('items', []):
        if item.get('id') in current_ids:
            continue
        if item.get('status') in {'PENDING', 'CONFIRMING'}:
            item['status'] = 'EXPIRED'
        items.append(item)

    payload = {
        'generated_at': t.isoformat(),
        'policy': {
            'confirmation_required': True,
            'missed_signal_action': 'EXPIRE_NO_TRADE',
            'revalidate_on_confirm': True,
            'one_time_confirmation': True,
        },
        'items': items[-100:],
    }
    save(OUT, payload)
    pending = [x for x in items if x.get('status') == 'PENDING']
    print('APPROVAL QUEUE:', len(pending), 'pending')
    for x in pending:
        print(x['id'], x['symbol'], x['action'], x['strategy'], 'TTL', x['ttl_seconds'])


if __name__ == '__main__':
    main()
