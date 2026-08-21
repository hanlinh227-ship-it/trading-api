import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/trading/trading-api/auto-futures-v1')
STATE = ROOT / 'state'
PENDING = STATE / 'pending_trades.json'
POSITIONS = STATE / 'paper_positions.json'
DAILY = STATE / 'daily_risk.json'
RISK = STATE / 'risk_decisions.json'
GUARD = STATE / 'execution_guard.json'
CONFIRM = STATE / 'trade_confirmation.json'
EXEC_STATE = STATE / 'live_executor_state.json'
BRIDGE_STATE = STATE / 'hub_bridge_state.json'
BINANCE = 'https://fapi.binance.com'

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
TG = f'https://api.telegram.org/bot{TOKEN}'


def now():
    return datetime.now(timezone.utc)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def request_json(url, data=None, headers=None, method=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def tg(method, payload=None):
    raw = urllib.parse.urlencode(payload or {}).encode()
    return request_json(f'{TG}/{method}', data=raw, method='POST', timeout=40)


def webhook_origin():
    info = tg('getWebhookInfo')
    url = str(((info.get('result') or {}).get('url') or '')).strip()
    if not url:
        raise RuntimeError('TELEGRAM_WEBHOOK_NOT_CONFIGURED_FOR_THIS_BOT')
    p = urllib.parse.urlparse(url)
    if p.scheme not in {'http', 'https'} or not p.netloc:
        raise RuntimeError('TELEGRAM_WEBHOOK_URL_INVALID')
    return f'{p.scheme}://{p.netloc}'


def sign(method, path, ts, raw=''):
    msg = f'{method}\n{path}\n{ts}\n{raw}'.encode()
    return hmac.new(TOKEN.encode(), msg, hashlib.sha256).hexdigest()


def control_request(origin, method, path, payload=None, query=None):
    raw = '' if payload is None else json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    ts = str(int(time.time()))
    headers = {
        'x-auto-futures-timestamp': ts,
        'x-auto-futures-signature': sign(method, path, ts, raw),
        'user-agent': 'AUTO-FUTURES-V6-HUB-BRIDGE',
    }
    url = origin + path
    if query:
        url += '?' + urllib.parse.urlencode(query)
    data = raw.encode() if method == 'POST' else None
    if method == 'POST':
        headers['content-type'] = 'application/json'
    return request_json(url, data=data, headers=headers, method=method, timeout=35)


def ai_status():
    c = load(STATE / 'ai_consensus.json', {})
    bits = [c.get('claude_status'), c.get('deepseek_status'), c.get('codex_status')]
    ok = sum(1 for x in bits if str(x).upper() == 'OK')
    return f'{ok}/3 OK'


def pnl_payload():
    daily = load(DAILY, {})
    pos = load(POSITIONS, {'positions': []})
    closed = pos.get('closed', []) if isinstance(pos.get('closed'), list) else []
    return {
        'realized_pnl': daily.get('realized_pnl', daily.get('daily_pnl', 0)),
        'unrealized_pnl': daily.get('unrealized_pnl', 0),
        'closed_trades': len(closed),
        'updated_at': now().isoformat(),
    }


def report(origin):
    pending = load(PENDING, {'items': []})
    positions = load(POSITIONS, {'positions': []})
    payload = {
        'reported_at': now().isoformat(),
        'runtime': {
            'ai_status': ai_status(),
            'scan_status': 'ACTIVE',
            'mode': 'CONFIRM_PER_TRADE',
        },
        'pending': pending,
        'positions': positions,
        'pnl': pnl_payload(),
    }
    return control_request(origin, 'POST', '/binance/control/report', payload=payload)


def current_price(symbol):
    with urllib.request.urlopen(f'{BINANCE}/fapi/v1/ticker/price?symbol={symbol}', timeout=10) as r:
        return float(json.loads(r.read().decode())['price'])


def run_revalidation():
    env = os.environ.copy()
    commands = [
        ['python3', str(ROOT / 'paper_trader.py')],
        ['python3', str(ROOT / 'ai/consensus.py')],
        ['python3', str(ROOT / 'risk/risk_engine.py')],
        ['python3', str(ROOT / 'execution/execution_guard.py')],
    ]
    for cmd in commands:
        p = subprocess.run(cmd, cwd=str(ROOT.parent), env=env, capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout)[-1500:]
    return True, 'PASS'


def notify(text):
    if CHAT_ID:
        try:
            tg('sendMessage', {'chat_id': CHAT_ID, 'text': text})
        except Exception:
            pass


def update_local_item(trade_id, status, reason=None):
    q = load(PENDING, {'items': []})
    for x in q.get('items', []):
        if x.get('id') == trade_id:
            x['status'] = status
            x['resolved_at'] = now().isoformat()
            if reason:
                x['reason'] = reason
            save(PENDING, q)
            return x
    return None


def process_confirm(event):
    trade_id = event.get('trade_id')
    q = load(PENDING, {'items': []})
    item = next((x for x in q.get('items', []) if x.get('id') == trade_id), None)
    if not item or item.get('status') != 'PENDING':
        return 'LOCAL_SIGNAL_NOT_PENDING'
    try:
        expires = datetime.fromisoformat(item['expires_at'].replace('Z', '+00:00'))
        if now() >= expires:
            update_local_item(trade_id, 'EXPIRED', 'TTL_EXPIRED_BEFORE_CONFIRMATION')
            return 'TTL_EXPIRED'
    except Exception:
        return 'INVALID_LOCAL_EXPIRY'

    update_local_item(trade_id, 'CONFIRMING')
    ok, detail = run_revalidation()
    if not ok:
        update_local_item(trade_id, 'REVALIDATION_FAILED', detail)
        return 'REVALIDATION_FAILED'

    risk = load(RISK, {'decisions': {}})
    guard = load(GUARD, {'decisions': {}})
    d = risk.get('decisions', {}).get(item['symbol'], {})
    g = guard.get('decisions', {}).get(item['symbol'], {})
    if not d.get('approved') or not g.get('executable'):
        update_local_item(trade_id, 'NO_LONGER_VALID', 'CURRENT_GUARD_REJECTED')
        return 'CURRENT_GUARD_REJECTED'
    if str(d.get('action')).upper() != str(item.get('action')).upper():
        update_local_item(trade_id, 'SETUP_CHANGED', 'DIRECTION_CHANGED')
        return 'DIRECTION_CHANGED'
    if str(d.get('strategy')).upper() != str(item.get('strategy')).upper():
        update_local_item(trade_id, 'SETUP_CHANGED', 'STRATEGY_CHANGED')
        return 'STRATEGY_CHANGED'
    if g.get('fingerprint') != item.get('fingerprint'):
        update_local_item(trade_id, 'SETUP_CHANGED', 'FINGERPRINT_CHANGED')
        return 'FINGERPRINT_CHANGED'

    old_entry = float(item['entry'])
    old_stop = float(item['stop_loss'])
    r = abs(old_entry - old_stop)
    px = current_price(item['symbol'])
    if r <= 0 or abs(px - old_entry) > 0.35 * r:
        update_local_item(trade_id, 'PRICE_MOVED', f'CURRENT_PRICE={px}')
        return 'PRICE_MOVED'

    confirmation = {
        'status': 'CONFIRMED',
        'confirmed_at': now().isoformat(),
        'expires_in_seconds': 30,
        'source_trade_id': trade_id,
        'symbol': item['symbol'],
        'action': item['action'],
        'strategy': item['strategy'],
        'fingerprint': g.get('fingerprint'),
        'decision': d,
        'confirmed_by_telegram_user': str(event.get('telegram_user_id', '')),
        'source': 'CLOUDFLARE_EXISTING_HUB',
    }
    save(CONFIRM, confirmation)
    p = subprocess.run(
        ['python3', str(ROOT / 'execution/live_executor.py')],
        cwd=str(ROOT.parent), env=os.environ.copy(), capture_output=True, text=True, timeout=120
    )
    out = load(EXEC_STATE, {})
    status = out.get('status') or ('EXECUTOR_OK' if p.returncode == 0 else 'EXECUTOR_FAILED')
    update_local_item(trade_id, 'CONFIRMED' if not out.get('executed') else 'EXECUTED', status)
    notify(f"🟨 BINANCE {item['symbol']} {item['action']}\n{status}\nExecuted: {bool(out.get('executed'))}")
    return status


def process_event(event):
    decision = str(event.get('decision', '')).upper()
    trade_id = event.get('trade_id')
    if decision == 'REJECTED':
        update_local_item(trade_id, 'REJECTED', 'REJECTED_ON_EXISTING_HUB')
        return 'REJECTED'
    if decision == 'CONFIRMED':
        return process_confirm(event)
    return 'IGNORED'


def main():
    if not TOKEN:
        raise SystemExit('TELEGRAM_BOT_TOKEN missing')
    origin = None
    last_report = 0.0
    while True:
        try:
            if not origin:
                origin = webhook_origin()
                print('HUB_ORIGIN', origin, flush=True)
            if time.time() - last_report >= 10:
                report(origin)
                last_report = time.time()
            st = load(BRIDGE_STATE, {'last_seq': 0})
            after = int(st.get('last_seq', 0) or 0)
            feed = control_request(origin, 'GET', '/binance/control/feed', query={'after': after})
            for event in feed.get('events', []):
                seq = int(event.get('seq', 0) or 0)
                result = process_event(event)
                print('CONTROL_EVENT', seq, event.get('trade_id'), result, flush=True)
                after = max(after, seq)
                save(BRIDGE_STATE, {'last_seq': after, 'updated_at': now().isoformat()})
            time.sleep(3)
        except Exception as exc:
            print('hub_control_bridge error:', repr(exc), flush=True)
            origin = None
            time.sleep(5)


if __name__ == '__main__':
    main()
