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

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';ENV_FILE=Path('/opt/trading/.env.binance')
RISK_FILE=STATE/'risk_decisions.json';GUARD_FILE=STATE/'execution_guard.json';CONFIRM_FILE=STATE/'trade_confirmation.json';PREFLIGHT_FILE=STATE/'live_preflight.json';INCIDENT_FILE=STATE/'execution_incident.json';OUT_FILE=STATE/'live_executor_state.json'
BASE='https://fapi.binance.com';MAX_CONCURRENT_POSITIONS=5;MAX_ENTRY_DRIFT_R=.35

def now():return datetime.now(timezone.utc)
def load_json(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def save_json(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def incident(reason,details=None):
    obj={'active':True,'created_at':now().isoformat(),'reason':reason,'details':details or {},'policy':'FAIL_CLOSED_NO_NEW_ENTRIES_UNTIL_RECONCILED'};save_json(INCIDENT_FILE,obj);return obj
def load_env():
    out={}
    if not ENV_FILE.exists():return out
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        k,v=line.split('=',1);out[k.strip()]=v.strip().strip('"').strip("'")
    return out
ENV=load_env();API_KEY=ENV.get('BINANCE_API_KEY','');API_SECRET=ENV.get('BINANCE_API_SECRET','');LIVE_TRADING=ENV.get('BINANCE_LIVE_TRADING','false').lower()=='true';LIVE_ARMED=ENV.get('BINANCE_LIVE_ARMED','false').lower()=='true'

def public_get(path,params=None):
    url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
    req=urllib.request.Request(url,headers={'User-Agent':'AUTO-FUTURES-V8-FAIL-CLOSED'})
    with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode())
def signed(method,path,params=None):
    p=dict(params or {});p['timestamp']=int(public_get('/fapi/v1/time')['serverTime']);p['recvWindow']=10000
    q=urllib.parse.urlencode(p);sig=hmac.new(API_SECRET.encode(),q.encode(),hashlib.sha256).hexdigest();payload=q+'&signature='+sig;url=BASE+path;data=None
    if method=='GET':url+='?'+payload
    else:data=payload.encode()
    req=urllib.request.Request(url,data=data,method=method,headers={'X-MBX-APIKEY':API_KEY,'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors='replace');raise RuntimeError(f'BINANCE_HTTP_{e.code}: {body}')
    except Exception as e:raise RuntimeError('BINANCE_TRANSPORT_UNKNOWN:'+repr(e))
def symbol_info(symbol):
    for x in public_get('/fapi/v1/exchangeInfo').get('symbols',[]):
        if x.get('symbol')==symbol:return x
    raise RuntimeError('SYMBOL_NOT_FOUND')
def flt(info,name):
    for x in info.get('filters',[]):
        if x.get('filterType')==name:return x
    return {}
def floor_step(value,step):
    v,s=Decimal(str(value)),Decimal(str(step));return float((v/s).to_integral_value(rounding=ROUND_DOWN)*s) if s else float(v)
def round_tick(value,tick):
    v,t=Decimal(str(value)),Decimal(str(tick));return float((v/t).to_integral_value(rounding=ROUND_HALF_UP)*t) if t else float(v)
def mark_price(symbol):return float(public_get('/fapi/v1/premiumIndex',{'symbol':symbol})['markPrice'])
def confirmation_gate():
    if load_json(INCIDENT_FILE,{}).get('active'):return None,'EXECUTION_INCIDENT_LOCK_ACTIVE'
    c=load_json(CONFIRM_FILE,{})
    if c.get('status')!='CONFIRMED':return None,'NO_TELEGRAM_CONFIRMATION'
    try:confirmed_at=datetime.fromisoformat(c['confirmed_at'].replace('Z','+00:00'))
    except Exception:return None,'CONFIRMATION_TIME_INVALID'
    if (now()-confirmed_at).total_seconds()>int(c.get('expires_in_seconds',30)):
        c['status']='EXPIRED';save_json(CONFIRM_FILE,c);return None,'CONFIRMATION_EXPIRED'
    risk=load_json(RISK_FILE,{'decisions':{}});guard=load_json(GUARD_FILE,{'decisions':{}});pre=load_json(PREFLIGHT_FILE,{})
    symbol=c.get('symbol');d=risk.get('decisions',{}).get(symbol,{});g=guard.get('decisions',{}).get(symbol,{});pf=(pre.get('decisions') or {}).get(symbol,{})
    if not pre.get('account_ok') or not pf.get('eligible'):return None,'LIVE_PREFLIGHT_REJECTED'
    if not d.get('approved') or not g.get('executable'):return None,'CURRENT_GUARD_REJECTED'
    if c.get('fingerprint')!=g.get('fingerprint'):return None,'FINGERPRINT_CHANGED'
    if str(d.get('action')).upper()!=str(c.get('action')).upper():return None,'DIRECTION_CHANGED'
    return {'confirmation':c,'decision':d,'guard':g},'PASS'
def require_one_way():
    if bool(signed('GET','/fapi/v1/positionSide/dual',{}).get('dualSidePosition')):raise RuntimeError('HEDGE_MODE_BLOCKED_USE_ONE_WAY')
def live_open_positions():
    return [x for x in signed('GET','/fapi/v2/positionRisk',{}) if abs(float(x.get('positionAmt',0) or 0))>0]
def enforce_live_slot(symbol):
    rows=live_open_positions();symbols={str(x.get('symbol')) for x in rows}
    if symbol in symbols:raise RuntimeError('POSITION_ALREADY_OPEN_LIVE')
    if len(rows)>=MAX_CONCURRENT_POSITIONS:raise RuntimeError('MAX_5_LIVE_POSITIONS')
    return len(rows),MAX_CONCURRENT_POSITIONS-len(rows)
def ensure_isolated(symbol):
    try:signed('POST','/fapi/v1/marginType',{'symbol':symbol,'marginType':'ISOLATED'})
    except RuntimeError as exc:
        if '-4046' not in str(exc) and 'No need to change margin type' not in str(exc):raise
def build_plan(symbol,d):
    account=signed('GET','/fapi/v2/account',{});available=float(account.get('availableBalance',0) or 0)
    if available<=0:raise RuntimeError('NO_AVAILABLE_BALANCE')
    info=symbol_info(symbol)
    if info.get('status')!='TRADING':raise RuntimeError('SYMBOL_NOT_TRADING')
    px=mark_price(symbol);entry=float(d['entry']);stop=float(d['stop_loss']);distance=abs(entry-stop)
    if distance<=0:raise RuntimeError('INVALID_STOP_DISTANCE')
    if abs(px-entry)/distance>MAX_ENTRY_DRIFT_R:raise RuntimeError('ENTRY_TOO_STALE_FOR_LIVE')
    action=str(d.get('action')).upper();tp1=float(d['tp1']);tp2=float(d['tp2']);tp3=float(d['tp3'])
    if action=='LONG' and not (stop<px<tp3):raise RuntimeError('LONG_PROTECTION_WRONG_SIDE')
    if action=='SHORT' and not (stop>px>tp3):raise RuntimeError('SHORT_PROTECTION_WRONG_SIDE')
    risk_pct=float(d.get('risk_pct',.5));leverage=int(d.get('max_leverage',3));lot=flt(info,'MARKET_LOT_SIZE') or flt(info,'LOT_SIZE');pf=flt(info,'PRICE_FILTER');mn=flt(info,'MIN_NOTIONAL')
    step=float(lot.get('stepSize',0) or 0);min_qty=float(lot.get('minQty',0) or 0);max_qty=float(lot.get('maxQty',1e99) or 1e99);tick=float(pf.get('tickSize',0) or 0);min_notional=float(mn.get('notional',0) or 0)
    qty=floor_step(min(available*risk_pct/100/distance,available*leverage/px),step)
    if qty<min_qty:raise RuntimeError(f'QTY_BELOW_MIN_{qty}_{min_qty}')
    if qty>max_qty:raise RuntimeError('QTY_ABOVE_MAX')
    if min_notional and qty*px<min_notional:raise RuntimeError('NOTIONAL_BELOW_MIN')
    side='BUY' if action=='LONG' else 'SELL';close_side='SELL' if side=='BUY' else 'BUY';m=d.get('management') or {}
    q1=floor_step(qty*float(m.get('tp1_close_pct',30))/100,step);q2=floor_step(qty*float(m.get('tp2_close_pct',30))/100,step)
    if q1<min_qty or (min_notional and q1*px<min_notional):q1=0
    if q2<min_qty or (min_notional and q2*px<min_notional):q2=0
    return {'symbol':symbol,'side':side,'close_side':close_side,'qty':qty,'q1':q1,'q2':q2,'leverage':leverage,'stop':round_tick(stop,tick),'tp1':round_tick(tp1,tick),'tp2':round_tick(tp2,tick),'tp3':round_tick(tp3,tick),'strategy':d.get('strategy'),'risk_pct':risk_pct,'margin_mode':'ISOLATED','mark_before_entry':px,'min_qty':min_qty,'min_notional':min_notional}
def client_id(prefix,seed):return (prefix+hashlib.sha256(seed.encode()).hexdigest()[:24])[:36]
def query_order(symbol,cid):
    try:return signed('GET','/fapi/v1/order',{'symbol':symbol,'origClientOrderId':cid})
    except Exception:return None
def post_market_idempotent(symbol,side,qty,cid,reduce_only=False):
    params={'symbol':symbol,'side':side,'type':'MARKET','quantity':qty,'newOrderRespType':'RESULT','newClientOrderId':cid}
    if reduce_only:params['reduceOnly']='true'
    try:return signed('POST','/fapi/v1/order',params)
    except Exception as exc:
        recovered=query_order(symbol,cid)
        if recovered:return recovered
        incident('ORDER_STATUS_UNKNOWN',{'symbol':symbol,'clientOrderId':cid,'error':str(exc)[:300]})
        raise RuntimeError('ORDER_STATUS_UNKNOWN_INCIDENT_LOCKED')
def emergency_close(plan,filled_qty,seed):
    if filled_qty<=0:return None
    return post_market_idempotent(plan['symbol'],plan['close_side'],filled_qty,client_id('AFV8X',seed),True)
def place_algo(plan,order_type,stop_price,quantity=None,close_all=False):
    params={'algoType':'CONDITIONAL','symbol':plan['symbol'],'side':plan['close_side'],'type':order_type,'stopPrice':stop_price,'workingType':'MARK_PRICE','priceProtect':'true'}
    if close_all:params['closePosition']='true'
    elif quantity and quantity>0:params['quantity']=quantity;params['reduceOnly']='true'
    return signed('POST','/fapi/v1/algoOrder',params)
def verify_live_position(symbol):
    rows=signed('GET','/fapi/v2/positionRisk',{'symbol':symbol});rows=rows if isinstance(rows,list) else [rows]
    active=[x for x in rows if abs(float(x.get('positionAmt',0) or 0))>0]
    return active[0] if active else None
def execute(plan,seed):
    enforce_live_slot(plan['symbol']);ensure_isolated(plan['symbol']);signed('POST','/fapi/v1/leverage',{'symbol':plan['symbol'],'leverage':plan['leverage']})
    cid=client_id('AFV8E',seed);entry=post_market_idempotent(plan['symbol'],plan['side'],plan['qty'],cid,False);pos=verify_live_position(plan['symbol'])
    if not pos:
        incident('ENTRY_RESPONSE_BUT_NO_POSITION',{'symbol':plan['symbol'],'entry':entry});raise RuntimeError('ENTRY_POSITION_RECONCILIATION_FAILED')
    filled=abs(float(pos.get('positionAmt',0) or entry.get('executedQty') or plan['qty']));protection={}
    try:
        protection['stop']=place_algo(plan,'STOP_MARKET',plan['stop'],close_all=True)
        protection['tp3']=place_algo(plan,'TAKE_PROFIT_MARKET',plan['tp3'],close_all=True)
        if plan['q1']>0:protection['tp1']=place_algo(plan,'TAKE_PROFIT_MARKET',plan['tp1'],quantity=plan['q1'])
        if plan['q2']>0:protection['tp2']=place_algo(plan,'TAKE_PROFIT_MARKET',plan['tp2'],quantity=plan['q2'])
        if not protection.get('stop') or not protection.get('tp3'):raise RuntimeError('MANDATORY_PROTECTION_RESPONSE_EMPTY')
    except Exception as exc:
        close_result=None
        try:close_result=emergency_close(plan,filled,seed)
        finally:incident('PROTECTION_FAILURE_POSITION_EMERGENCY_CLOSED',{'symbol':plan['symbol'],'error':str(exc)[:500],'close_result':close_result})
        raise RuntimeError('PROTECTION_FAILED_INCIDENT_LOCKED')
    return {'entry':entry,'entry_client_order_id':cid,'protection':protection,'filled_qty':filled,'reconciled_position':pos}
def print_output(output):
    print(json.dumps(output,indent=2,ensure_ascii=False))
    if not output.get('executed'):print('LIVE EXECUTION LOCKED');print('NO REAL ORDER WAS SENT')
def main():
    if not API_KEY or not API_SECRET:raise SystemExit('BINANCE API credentials missing')
    gate,reason=confirmation_gate();output={'generated_at':now().isoformat(),'live_trading':LIVE_TRADING,'live_armed':LIVE_ARMED,'status':reason,'executed':False,'policy':{'max_concurrent_positions':5,'margin_mode':'ISOLATED_ONLY','slot_refills_after_position_close':True,'idempotent_entry':True,'unknown_status_fail_closed':True,'protective_failure_incident_lock':True}}
    if not gate:save_json(OUT_FILE,output);print_output(output);return
    symbol=gate['confirmation']['symbol'];plan=build_plan(symbol,gate['decision']);output['plan']=plan
    if not (LIVE_TRADING and LIVE_ARMED):output['status']='CONFIRMED_DRY_RUN_LIVE_LOCKED';save_json(OUT_FILE,output);print_output(output);return
    require_one_way();open_count,slots_left=enforce_live_slot(symbol);output['live_open_positions_before']=open_count;output['live_slots_left_before']=slots_left
    seed=str(gate['confirmation'].get('fingerprint') or gate['confirmation'].get('id') or symbol+now().isoformat());result=execute(plan,seed);output.update({'status':'EXECUTED_PROTECTED_ISOLATED_RECONCILED','executed':True,'result':result})
    c=gate['confirmation'];c['status']='CONSUMED';c['consumed_at']=now().isoformat();save_json(CONFIRM_FILE,c);save_json(OUT_FILE,output);print_output(output)
if __name__=='__main__':main()
