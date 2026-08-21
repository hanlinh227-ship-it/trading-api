import json
import os
import hmac
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path('/opt/trading/trading-api/auto-futures-v1')
STATE = ROOT / 'state'
ENV_FILE = Path('/opt/trading/.env.binance')
RISK_FILE = STATE / 'risk_decisions.json'
GUARD_FILE = STATE / 'execution_guard.json'
CONFIRM_FILE = STATE / 'trade_confirmation.json'
OUT_FILE = STATE / 'live_executor_state.json'
BASE = 'https://fapi.binance.com'


def now():
    return datetime.now(timezone.utc)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def load_env():
    out = {}
    if not ENV_FILE.exists():
        return out
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

ENV = load_env()
API_KEY = ENV.get('BINANCE_API_KEY', '')
API_SECRET = ENV.get('BINANCE_API_SECRET', '')
LIVE_TRADING = ENV.get('BINANCE_LIVE_TRADING', 'false').lower() == 'true'
LIVE_ARMED = ENV.get('BINANCE_LIVE_ARMED', 'false').lower() == 'true'


def public_get(path, params=None):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent':'AUTO-FUTURES-V6-CONFIRMED'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def signed(method, path, params=None):
    params = dict(params or {})
    params['timestamp'] = int(public_get('/fapi/v1/time')['serverTime'])
    params['recvWindow'] = 10000
    query = urllib.parse.urlencode(params)
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    payload = query + '&signature=' + sig
    url = BASE + path
    data = None
    if method == 'GET':
        url += '?' + payload
    else:
        data = payload.encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        'X-MBX-APIKEY': API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'BINANCE_HTTP_{e.code}: {e.read().decode(errors="replace")}')


def symbol_info(symbol):
    for x in public_get('/fapi/v1/exchangeInfo').get('symbols', []):
        if x.get('symbol') == symbol:
            return x
    raise RuntimeError('SYMBOL_NOT_FOUND')


def flt(info, name):
    for x in info.get('filters', []):
        if x.get('filterType') == name:
            return x
    return None


def floor_step(value, step):
    v, s = Decimal(str(value)), Decimal(str(step))
    return float((v/s).to_integral_value(rounding=ROUND_DOWN)*s) if s else float(v)


def round_tick(value, tick):
    v, t = Decimal(str(value)), Decimal(str(tick))
    return float((v/t).to_integral_value(rounding=ROUND_HALF_UP)*t) if t else float(v)


def confirmation_gate():
    c = load_json(CONFIRM_FILE, {})
    if c.get('status') != 'CONFIRMED':
        return None, 'NO_TELEGRAM_CONFIRMATION'
    try:
        confirmed_at = datetime.fromisoformat(c['confirmed_at'].replace('Z','+00:00'))
    except Exception:
        return None, 'CONFIRMATION_TIME_INVALID'
    ttl = int(c.get('expires_in_seconds', 30))
    if (now() - confirmed_at).total_seconds() > ttl:
        c['status'] = 'EXPIRED'; save_json(CONFIRM_FILE, c)
        return None, 'CONFIRMATION_EXPIRED'
    risk = load_json(RISK_FILE, {'decisions':{}})
    guard = load_json(GUARD_FILE, {'decisions':{}})
    symbol = c.get('symbol')
    d = risk.get('decisions', {}).get(symbol, {})
    g = guard.get('decisions', {}).get(symbol, {})
    if not d.get('approved') or not g.get('executable'):
        return None, 'CURRENT_GUARD_REJECTED'
    if c.get('fingerprint') != g.get('fingerprint'):
        return None, 'FINGERPRINT_CHANGED'
    if str(d.get('action')).upper() != str(c.get('action')).upper():
        return None, 'DIRECTION_CHANGED'
    return {'confirmation':c, 'decision':d, 'guard':g}, 'PASS'


def require_one_way():
    mode = signed('GET', '/fapi/v1/positionSide/dual', {})
    if bool(mode.get('dualSidePosition')):
        raise RuntimeError('HEDGE_MODE_BLOCKED_USE_ONE_WAY')


def build_plan(symbol, d):
    account = signed('GET', '/fapi/v2/account', {})
    available = float(account.get('availableBalance', 0))
    if available <= 0:
        raise RuntimeError('NO_AVAILABLE_BALANCE')
    entry = float(d['entry']); stop = float(d['stop_loss'])
    distance = abs(entry-stop)
    if distance <= 0:
        raise RuntimeError('INVALID_STOP_DISTANCE')
    risk_pct = float(d.get('risk_pct', 0.5)); leverage = int(d.get('max_leverage', 3))
    qty = min(available*risk_pct/100/distance, available*leverage/entry)
    info = symbol_info(symbol)
    lot = flt(info, 'MARKET_LOT_SIZE') or flt(info, 'LOT_SIZE')
    price_filter = flt(info, 'PRICE_FILTER')
    step = float(lot['stepSize']); min_qty = float(lot['minQty']); tick = float(price_filter['tickSize'])
    qty = floor_step(qty, step)
    if qty < min_qty:
        raise RuntimeError(f'QTY_BELOW_MIN_{qty}_{min_qty}')
    side = 'BUY' if d['action']=='LONG' else 'SELL'
    close_side = 'SELL' if side=='BUY' else 'BUY'
    m = d.get('management') or {}
    q1 = floor_step(qty*float(m.get('tp1_close_pct',30))/100, step)
    q2 = floor_step(qty*float(m.get('tp2_close_pct',30))/100, step)
    return {
        'symbol':symbol,'side':side,'close_side':close_side,'qty':qty,'q1':q1,'q2':q2,
        'leverage':leverage,'stop':round_tick(float(d['stop_loss']),tick),
        'tp1':round_tick(float(d['tp1']),tick),'tp2':round_tick(float(d['tp2']),tick),
        'tp3':round_tick(float(d['tp3']),tick),'strategy':d.get('strategy'),'risk_pct':risk_pct,
    }


def emergency_close(plan, filled_qty):
    if filled_qty <= 0:
        return None
    return signed('POST', '/fapi/v1/order', {
        'symbol':plan['symbol'],'side':plan['close_side'],'type':'MARKET',
        'quantity':filled_qty,'reduceOnly':'true','newOrderRespType':'RESULT',
    })


def place_algo(plan, order_type, stop_price, quantity=None, close_all=False):
    params = {
        'algoType':'CONDITIONAL','symbol':plan['symbol'],'side':plan['close_side'],
        'type':order_type,'stopPrice':stop_price,'workingType':'MARK_PRICE','priceProtect':'true',
    }
    if close_all:
        params['closePosition'] = 'true'
    elif quantity and quantity > 0:
        params['quantity'] = quantity
        params['reduceOnly'] = 'true'
    return signed('POST', '/fapi/v1/algoOrder', params)


def execute(plan):
    signed('POST', '/fapi/v1/leverage', {'symbol':plan['symbol'],'leverage':plan['leverage']})
    entry = signed('POST', '/fapi/v1/order', {
        'symbol':plan['symbol'],'side':plan['side'],'type':'MARKET','quantity':plan['qty'],
        'newOrderRespType':'RESULT',
    })
    filled = float(entry.get('executedQty') or plan['qty'])
    protection = {}
    try:
        protection['stop'] = place_algo(plan, 'STOP_MARKET', plan['stop'], close_all=True)
        protection['tp3'] = place_algo(plan, 'TAKE_PROFIT_MARKET', plan['tp3'], close_all=True)
        if plan['q1'] > 0:
            protection['tp1'] = place_algo(plan, 'TAKE_PROFIT_MARKET', plan['tp1'], quantity=plan['q1'])
        if plan['q2'] > 0:
            protection['tp2'] = place_algo(plan, 'TAKE_PROFIT_MARKET', plan['tp2'], quantity=plan['q2'])
    except Exception as exc:
        close_result = emergency_close(plan, filled)
        raise RuntimeError(f'PROTECTION_FAILED_EMERGENCY_CLOSED: {exc}; close={close_result}')
    return {'entry':entry,'protection':protection,'filled_qty':filled}


def main():
    if not API_KEY or not API_SECRET:
        raise SystemExit('BINANCE API credentials missing')
    gate, reason = confirmation_gate()
    output = {'generated_at':now().isoformat(),'live_trading':LIVE_TRADING,'live_armed':LIVE_ARMED,'status':reason,'executed':False}
    if not gate:
        save_json(OUT_FILE, output); print(json.dumps(output, indent=2)); return
    symbol = gate['confirmation']['symbol']
    plan = build_plan(symbol, gate['decision'])
    output['plan'] = plan
    if not (LIVE_TRADING and LIVE_ARMED):
        output['status'] = 'CONFIRMED_DRY_RUN_LIVE_LOCKED'
        save_json(OUT_FILE, output); print(json.dumps(output, indent=2)); return
    require_one_way()
    result = execute(plan)
    output.update({'status':'EXECUTED_PROTECTED','executed':True,'result':result})
    c = gate['confirmation']; c['status']='CONSUMED'; c['consumed_at']=now().isoformat(); save_json(CONFIRM_FILE,c)
    save_json(OUT_FILE, output)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
