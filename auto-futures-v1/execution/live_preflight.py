import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';ENV_FILE=Path('/opt/trading/.env.binance')
RISK=STATE/'risk_decisions.json';OUT=STATE/'live_preflight.json';INCIDENT=STATE/'execution_incident.json';BASE='https://fapi.binance.com';MAX_POSITIONS=5;MAX_ENTRY_DRIFT_R=.35

def now():return datetime.now(timezone.utc).isoformat()
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def save(obj):OUT.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def env_load():
    out={}
    if not ENV_FILE.exists():return out
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        k,v=line.split('=',1);out[k.strip()]=v.strip().strip('"').strip("'")
    return out
ENV=env_load();KEY=ENV.get('BINANCE_API_KEY','');SECRET=ENV.get('BINANCE_API_SECRET','')

def risk_pct_for_balance(balance):
    if balance<100:return 1.0
    if balance<250:return .75
    if balance<1000:return .60
    if balance<5000:return .50
    return .35

def public(path,params=None):
    url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AUTO-FUTURES-V10-PREFLIGHT'}),timeout=15) as r:return json.loads(r.read().decode())
def signed(method,path,params=None):
    p=dict(params or {});p['timestamp']=int(public('/fapi/v1/time')['serverTime']);p['recvWindow']=10000;q=urllib.parse.urlencode(p);sig=hmac.new(SECRET.encode(),q.encode(),hashlib.sha256).hexdigest();payload=q+'&signature='+sig;url=BASE+path;data=None
    if method=='GET':url+='?'+payload
    else:data=payload.encode()
    req=urllib.request.Request(url,data=data,method=method,headers={'X-MBX-APIKEY':KEY,'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:raise RuntimeError(f'HTTP_{e.code}:{e.read().decode(errors="replace")}')
def flt(info,name):
    for x in info.get('filters',[]):
        if x.get('filterType')==name:return x
    return {}
def floor_step(v,s):
    v,s=Decimal(str(v)),Decimal(str(s));return float((v/s).to_integral_value(rounding=ROUND_DOWN)*s) if s else float(v)
def round_tick(v,t):
    v,t=Decimal(str(v)),Decimal(str(t));return float((v/t).to_integral_value(rounding=ROUND_HALF_UP)*t) if t else float(v)
def symbol_map():return {x.get('symbol'):x for x in public('/fapi/v1/exchangeInfo').get('symbols',[])}
def mark(symbol):return float(public('/fapi/v1/premiumIndex',{'symbol':symbol})['markPrice'])

def main():
    risk=load(RISK,{'decisions':{}});result={'generated_at':now(),'engine':'V10_FAIL_CLOSED_LIVE_PREFLIGHT','account_ok':False,'live_open_positions':None,'slots_left':0,'decisions':{},'fatal_errors':[]}
    incident=load(INCIDENT,{})
    if incident.get('active'):
        result['fatal_errors'].append('UNRESOLVED_EXECUTION_INCIDENT');result['incident']=incident;save(result);print(json.dumps(result));return
    if not KEY or not SECRET:
        result['fatal_errors'].append('BINANCE_CREDENTIALS_MISSING');save(result);print(json.dumps(result));return
    try:
        dual=signed('GET','/fapi/v1/positionSide/dual',{});acct=signed('GET','/fapi/v2/account',{});positions=signed('GET','/fapi/v2/positionRisk',{});open_orders=signed('GET','/fapi/v1/openOrders',{})
        if bool(dual.get('dualSidePosition')):result['fatal_errors'].append('HEDGE_MODE_UNSUPPORTED_USE_ONE_WAY')
        available=float(acct.get('availableBalance',0) or 0);risk_pct=risk_pct_for_balance(max(available,0))
        if available<=0:result['fatal_errors'].append('NO_AVAILABLE_BALANCE')
        live=[x for x in positions if abs(float(x.get('positionAmt',0) or 0))>0]
        result.update({'live_open_positions':len(live),'slots_left':max(0,MAX_POSITIONS-len(live)),'available_balance':available,'live_risk_pct':risk_pct,'open_order_count':len(open_orders),'live_sizing_source':'BINANCE_AVAILABLE_BALANCE'})
        if len(live)>MAX_POSITIONS:result['fatal_errors'].append('LIVE_POSITION_CAP_ALREADY_EXCEEDED')
        infos=symbol_map();open_symbols={x.get('symbol') for x in live}
        for symbol,d in risk.get('decisions',{}).items():
            reasons=[];eligible=bool(d.get('approved')) and str(d.get('action')).upper() in {'LONG','SHORT'}
            if not eligible:reasons.append('RISK_NOT_APPROVED')
            info=infos.get(symbol)
            if not info:reasons.append('SYMBOL_NOT_FOUND')
            elif info.get('status')!='TRADING':reasons.append('SYMBOL_NOT_TRADING')
            if symbol in open_symbols:reasons.append('POSITION_ALREADY_OPEN_LIVE')
            if len(live)>=MAX_POSITIONS:reasons.append('MAX_5_LIVE_POSITIONS')
            entry=d.get('entry');stop=d.get('stop_loss');tp1=d.get('tp1');tp2=d.get('tp2');tp3=d.get('tp3')
            if None in (entry,stop,tp1,tp2,tp3):reasons.append('MISSING_ENTRY_OR_PROTECTION')
            qty=0;notional=0;px=None
            if info and not reasons[:1]:
                try:
                    px=mark(symbol);entry=float(entry);stop=float(stop);risk_dist=abs(entry-stop)
                    if risk_dist<=0:reasons.append('INVALID_STOP_DISTANCE')
                    drift_r=abs(px-entry)/risk_dist if risk_dist>0 else 999
                    if drift_r>MAX_ENTRY_DRIFT_R:reasons.append('ENTRY_TOO_STALE_FOR_LIVE')
                    action=str(d.get('action')).upper()
                    if action=='LONG' and not (float(stop)<px<float(tp3)):reasons.append('LONG_PROTECTION_WRONG_SIDE')
                    if action=='SHORT' and not (float(stop)>px>float(tp3)):reasons.append('SHORT_PROTECTION_WRONG_SIDE')
                    lot=flt(info,'MARKET_LOT_SIZE') or flt(info,'LOT_SIZE');pf=flt(info,'PRICE_FILTER');mn=flt(info,'MIN_NOTIONAL') or flt(info,'NOTIONAL')
                    step=float(lot.get('stepSize',0) or 0);minq=float(lot.get('minQty',0) or 0);maxq=float(lot.get('maxQty',1e99) or 1e99);tick=float(pf.get('tickSize',0) or 0);min_notional=float(mn.get('notional') or mn.get('minNotional') or 0)
                    lev=int(d.get('max_leverage',3) or 3);qty=floor_step(min(available*risk_pct/100/risk_dist,available*lev/px),step) if risk_dist>0 else 0;notional=qty*px
                    if qty<minq:reasons.append('QTY_BELOW_MIN')
                    if qty>maxq:reasons.append('QTY_ABOVE_MAX')
                    if min_notional and notional<min_notional:reasons.append('NOTIONAL_BELOW_MIN')
                    for name,val in [('stop_loss',stop),('tp1',tp1),('tp2',tp2),('tp3',tp3)]:
                        rv=round_tick(float(val),tick)
                        if tick and abs(rv-float(val))>tick*.501:reasons.append(f'{name.upper()}_PRECISION_INVALID')
                    max_algo=int((flt(info,'MAX_NUM_ALGO_ORDERS') or {}).get('limit',100) or 100);algo_for_symbol=sum(1 for o in open_orders if o.get('symbol')==symbol and str(o.get('type','')).upper() in {'STOP','STOP_MARKET','TAKE_PROFIT','TAKE_PROFIT_MARKET','TRAILING_STOP_MARKET'})
                    if algo_for_symbol+4>max_algo:reasons.append('MAX_ALGO_ORDERS_WOULD_BE_EXCEEDED')
                except Exception as exc:reasons.append('PREFLIGHT_CALC_ERROR:'+type(exc).__name__)
            result['decisions'][symbol]={'eligible':not reasons,'reasons':reasons,'mark_price':px,'estimated_qty':qty,'estimated_notional':notional,'live_risk_pct':risk_pct,'margin_mode':'ISOLATED','max_positions':MAX_POSITIONS}
        result['account_ok']=not result['fatal_errors']
    except Exception as exc:result['fatal_errors'].append('ACCOUNT_PREFLIGHT_FAILED:'+str(exc)[:240])
    save(result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
