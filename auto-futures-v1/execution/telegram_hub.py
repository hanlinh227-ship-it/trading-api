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
QUEUE = STATE / 'pending_trades.json'
RISK = STATE / 'risk_decisions.json'
GUARD = STATE / 'execution_guard.json'
CONFIRM = STATE / 'trade_confirmation.json'
OFFSET = STATE / 'telegram_offset.json'
BASE = 'https://api.telegram.org/bot{token}/{method}'
BINANCE = 'https://fapi.binance.com'

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
ALLOWED_USER = os.environ.get('TELEGRAM_ALLOWED_USER_ID', '').strip()


def utcnow():
    return datetime.now(timezone.utc)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def tg(method, data=None):
    body = urllib.parse.urlencode(data or {}).encode()
    req = urllib.request.Request(BASE.format(token=TOKEN, method=method), data=body)
    with urllib.request.urlopen(req, timeout=70) as r:
        return json.loads(r.read().decode())


def current_price(symbol):
    with urllib.request.urlopen(f'{BINANCE}/fapi/v1/ticker/price?symbol={symbol}', timeout=10) as r:
        return float(json.loads(r.read().decode())['price'])


def text_for(x):
    ttl = x.get('ttl_seconds', 90)
    return (
        f"⚡ SCALP READY\n"
        f"{x['symbol']} | {x['action']} | {x.get('strategy')}\n"
        f"Entry: {x.get('entry')}\nSL: {x.get('stop_loss')}\n"
        f"TP1: {x.get('tp1')}\nTP2: {x.get('tp2')}\nTP3: {x.get('tp3')}\n"
        f"AI confidence: {x.get('ai_confidence')}\n"
        f"⏱ Hết hạn sau {ttl}s. Nếu không bấm: tự EXPIRE, KHÔNG trade."
    )


def keyboard(trade_id):
    return json.dumps({'inline_keyboard': [[
        {'text': '✅ CONFIRM', 'callback_data': f'confirm:{trade_id}'},
        {'text': '❌ REJECT', 'callback_data': f'reject:{trade_id}'},
    ]]})


def send_pending():
    q = load(QUEUE, {'items': []})
    changed = False
    for x in q.get('items', []):
        if x.get('status') != 'PENDING' or x.get('telegram_message_id'):
            continue
        expires = datetime.fromisoformat(x['expires_at'].replace('Z', '+00:00'))
        if utcnow() >= expires:
            x['status'] = 'EXPIRED'; changed = True; continue
        result = tg('sendMessage', {
            'chat_id': CHAT_ID,
            'text': text_for(x),
            'reply_markup': keyboard(x['id']),
        })
        if result.get('ok'):
            x['telegram_message_id'] = result['result']['message_id']
            changed = True
    if changed:
        save(QUEUE, q)


def run_revalidation():
    env = os.environ.copy()
    commands = [
        ['python3', str(ROOT / 'paper_trader.py')],
        ['python3', str(ROOT / 'ai/consensus.py')],
        ['python3', str(ROOT / 'risk/risk_engine.py')],
        ['python3', str(ROOT / 'execution/execution_guard.py')],
    ]
    for cmd in commands:
        p = subprocess.run(cmd, cwd=str(ROOT.parent), env=env, capture_output=True, text=True, timeout=240)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout)[-1200:]
    return True, 'PASS'


def find_item(trade_id):
    q = load(QUEUE, {'items': []})
    for x in q.get('items', []):
        if x.get('id') == trade_id:
            return q, x
    return q, None


def answer(callback_id, text):
    try:
        tg('answerCallbackQuery', {'callback_query_id': callback_id, 'text': text, 'show_alert': 'false'})
    except Exception:
        pass


def handle_callback(cq):
    user_id = str((cq.get('from') or {}).get('id', ''))
    if ALLOWED_USER and user_id != ALLOWED_USER:
        answer(cq['id'], 'Không có quyền xác nhận lệnh này.')
        return
    data = cq.get('data', '')
    if ':' not in data:
        return
    action, trade_id = data.split(':', 1)
    q, item = find_item(trade_id)
    if not item:
        answer(cq['id'], 'Signal không tồn tại.')
        return
    if item.get('status') != 'PENDING':
        answer(cq['id'], f"Signal đã {item.get('status')}.")
        return
    expires = datetime.fromisoformat(item['expires_at'].replace('Z', '+00:00'))
    if utcnow() >= expires:
        item['status'] = 'EXPIRED'; save(QUEUE, q)
        answer(cq['id'], 'Signal đã quá hạn. Không trade.')
        return
    if action == 'reject':
        item['status'] = 'REJECTED'; item['resolved_at'] = utcnow().isoformat(); save(QUEUE, q)
        answer(cq['id'], 'Đã bỏ lệnh.')
        return
    if action != 'confirm':
        return

    item['status'] = 'CONFIRMING'; save(QUEUE, q)
    ok, detail = run_revalidation()
    if not ok:
        item['status'] = 'REVALIDATION_FAILED'; item['reason'] = detail; save(QUEUE, q)
        answer(cq['id'], 'Revalidation lỗi. Không trade.')
        return

    risk = load(RISK, {'decisions': {}})
    guard = load(GUARD, {'decisions': {}})
    d = risk.get('decisions', {}).get(item['symbol'], {})
    g = guard.get('decisions', {}).get(item['symbol'], {})
    if not d.get('approved') or not g.get('executable'):
        item['status'] = 'NO_LONGER_VALID'; save(QUEUE, q)
        answer(cq['id'], 'Setup không còn hợp lệ. Không trade.')
        return
    if str(d.get('action')).upper() != item['action'] or str(d.get('strategy')).upper() != item['strategy']:
        item['status'] = 'SETUP_CHANGED'; save(QUEUE, q)
        answer(cq['id'], 'Direction/strategy đã đổi. Không trade.')
        return

    old_entry = float(item['entry']); old_stop = float(item['stop_loss']); old_r = abs(old_entry-old_stop)
    px = current_price(item['symbol'])
    if old_r <= 0 or abs(px-old_entry) > 0.35*old_r:
        item['status'] = 'PRICE_MOVED'; item['current_price'] = px; save(QUEUE, q)
        answer(cq['id'], 'Giá đã đi quá xa. Chờ signal mới.')
        return

    confirmation = {
        'status': 'CONFIRMED',
        'confirmed_at': utcnow().isoformat(),
        'expires_in_seconds': 30,
        'source_trade_id': trade_id,
        'symbol': item['symbol'],
        'action': item['action'],
        'strategy': item['strategy'],
        'fingerprint': g.get('fingerprint'),
        'decision': d,
        'confirmed_by_telegram_user': user_id,
    }
    save(CONFIRM, confirmation)
    item['status'] = 'CONFIRMED'; item['resolved_at'] = utcnow().isoformat(); save(QUEUE, q)

    p = subprocess.run(['python3', str(ROOT / 'execution/live_executor.py')], cwd=str(ROOT.parent), env=os.environ.copy(), capture_output=True, text=True, timeout=90)
    summary = (p.stdout or p.stderr)[-700:]
    tg('sendMessage', {'chat_id': CHAT_ID, 'text': f"CONFIRM {item['symbol']} {item['action']}\n{summary}"})
    answer(cq['id'], 'Đã xác nhận và chuyển sang executor.')


def poll_once():
    off = load(OFFSET, {'offset': 0}).get('offset', 0)
    data = tg('getUpdates', {'timeout': 50, 'offset': off, 'allowed_updates': json.dumps(['callback_query'])})
    if not data.get('ok'):
        return
    for u in data.get('result', []):
        off = max(off, int(u['update_id']) + 1)
        if u.get('callback_query'):
            handle_callback(u['callback_query'])
    save(OFFSET, {'offset': off})


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit('TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing')
    while True:
        try:
            send_pending()
            poll_once()
        except Exception as exc:
            print('telegram_hub error:', repr(exc), flush=True)
            time.sleep(3)


if __name__ == '__main__':
    main()
