import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state'
PENDING=STATE/'pending_trades.json';RISK=STATE/'risk_decisions.json';GUARD=STATE/'execution_guard.json';CONFIRM=STATE/'trade_confirmation.json';EXEC_STATE=STATE/'live_executor_state.json';BRIDGE_STATE=STATE/'hub_bridge_state.json'
BINANCE='https://fapi.binance.com';TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN','').strip();CHAT_ID=os.environ.get('TELEGRAM_CHAT_ID','').strip();TG=f'https://api.telegram.org/bot{TOKEN}'
BINANCE_KEY=os.environ.get('BINANCE_API_KEY','').strip();BINANCE_SECRET=os.environ.get('BINANCE_API_SECRET','').strip()

def now():return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def save(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def request_json(url,data=None,headers=None,method=None,timeout=30):
    req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
def tg(method,payload=None):return request_json(f'{TG}/{method}',data=urllib.parse.urlencode(payload or {}).encode(),method='POST',timeout=40)
def webhook_origin():
    info=tg('getWebhookInfo');url=str(((info.get('result') or {}).get('url') or '')).strip()
    if not url:raise RuntimeError('TELEGRAM_WEBHOOK_NOT_CONFIGURED_FOR_THIS_BOT')
    p=urllib.parse.urlparse(url)
    if p.scheme not in {'http','https'} or not p.netloc:raise RuntimeError('TELEGRAM_WEBHOOK_URL_INVALID')
    return f'{p.scheme}://{p.netloc}'
def sign(method,path,ts,raw=''):return hmac.new(TOKEN.encode(),f'{method}\n{path}\n{ts}\n{raw}'.encode(),hashlib.sha256).hexdigest()
def control_request(origin,method,path,payload=None,query=None):
    raw='' if payload is None else json.dumps(payload,separators=(',',':'),ensure_ascii=False);ts=str(int(time.time()))
    headers={'x-auto-futures-timestamp':ts,'x-auto-futures-signature':sign(method,path,ts,raw),'user-agent':'AUTO-FUTURES-V8-HUB-BRIDGE'}
    url=origin+path
    if query:url+='?'+urllib.parse.urlencode(query)
    data=raw.encode() if method=='POST' else None
    if method=='POST':headers['content-type']='application/json'
    return request_json(url,data=data,headers=headers,method=method,timeout=35)

def binance_public(path,params=None):
    url=BINANCE+path+('?' + urllib.parse.urlencode(params) if params else '')
    return request_json(url,headers={'User-Agent':'AUTO-FUTURES-V8-HUB-BRIDGE'},timeout=15)
def binance_signed(path,params=None):
    if not BINANCE_KEY or not BINANCE_SECRET:raise RuntimeError('BINANCE_CREDENTIALS_MISSING')
    p=dict(params or {});p['timestamp']=int(binance_public('/fapi/v1/time')['serverTime']);p['recvWindow']=10000
    q=urllib.parse.urlencode(p);sig=hmac.new(BINANCE_SECRET.encode(),q.encode(),hashlib.sha256).hexdigest()
    return request_json(BINANCE+path+'?'+q+'&signature='+sig,headers={'X-MBX-APIKEY':BINANCE_KEY,'User-Agent':'AUTO-FUTURES-V8-HUB-BRIDGE'},timeout=20)
def live_snapshot():
    try:
        rows=binance_signed('/fapi/v2/positionRisk');acct=binance_signed('/fapi/v2/account')
        positions=[]
        for x in rows:
            amt=float(x.get('positionAmt',0) or 0)
            if abs(amt)<=0:continue
            positions.append({'symbol':x.get('symbol'),'side':'LONG' if amt>0 else 'SHORT','positionAmt':abs(amt),'entryPrice':float(x.get('entryPrice',0) or 0),'markPrice':float(x.get('markPrice',0) or 0),'unrealizedPnl':float(x.get('unRealizedProfit',0) or 0),'leverage':int(float(x.get('leverage',0) or 0)),'marginMode':'ISOLATED' if str(x.get('isolated','false')).lower()=='true' else 'CROSS'})
        return {'mode':'LIVE_BINANCE','updated_at':now().isoformat(),'positions':positions,'open_count':len(positions),'max_open_positions':5,'wallet_balance':float(acct.get('totalWalletBalance',0) or 0),'available_balance':float(acct.get('availableBalance',0) or 0),'unrealized_pnl':sum(p['unrealizedPnl'] for p in positions),'error':None}
    except Exception as exc:return {'mode':'LIVE_BINANCE','updated_at':now().isoformat(),'positions':[],'open_count':None,'max_open_positions':5,'wallet_balance':None,'available_balance':None,'unrealized_pnl':None,'error':str(exc)[:300]}

def age_seconds(ts):
    try:return max(0.0,(now()-datetime.fromisoformat(str(ts).replace('Z','+00:00'))).total_seconds())
    except Exception:return 10**9

def ai_health():
    c=load(STATE/'ai_consensus.json',{})
    generated=c.get('generated_at');age=age_seconds(generated)
    lat=c.get('reviewer_latency_seconds') or {}
    rows={}
    for name,key in [('claude','claude_status'),('deepseek','deepseek_status'),('codex','codex_status')]:
        status=str(c.get(key) or 'UNKNOWN').upper()
        rows[name]={'status':status,'ok':status=='OK','latency_seconds':lat.get(name)}
    ok_count=sum(1 for x in rows.values() if x['ok'])
    fresh=age<=180
    if not fresh:overall='STALE'
    elif ok_count==3:overall='HEALTHY'
    elif ok_count>=1:overall='DEGRADED'
    else:overall='DOWN'
    return {'overall':overall,'ok_count':ok_count,'required':3,'fresh':fresh,'age_seconds':round(age,1) if age<10**8 else None,'generated_at':generated,'reviewers':rows,'budget':(c.get('policy') or {}).get('budget',{}),'token_mode':(c.get('policy') or {}).get('token_mode')}

def ai_status():
    h=ai_health();return f"{h['ok_count']}/3 OK" if h['fresh'] else 'STALE'
def report(origin):
    pending=load(PENDING,{'items':[]});live=live_snapshot();health=ai_health()
    payload={'reported_at':now().isoformat(),'runtime':{'ai_status':ai_status(),'ai_health':health,'scan_status':'ACTIVE','mode':'CONFIRM_PER_TRADE','position_source':'BINANCE_LIVE_ONLY','live_snapshot_error':live.get('error')},'pending':pending,'positions':{'mode':'LIVE_BINANCE','positions':live['positions'],'open_count':live['open_count'],'max_open_positions':5,'updated_at':live['updated_at']},'pnl':{'realized_pnl':None,'unrealized_pnl':live.get('unrealized_pnl'),'wallet_balance':live.get('wallet_balance'),'available_balance':live.get('available_balance'),'updated_at':live['updated_at']}}
    return control_request(origin,'POST','/binance/control/report',payload=payload)
def current_price(symbol):return float(binance_public('/fapi/v1/ticker/price',{'symbol':symbol})['price'])
def run_revalidation():
    env=os.environ.copy();commands=[['python3',str(ROOT/'paper_trader.py')],['python3',str(ROOT/'research/market_context_monitor.py')],['python3',str(ROOT/'ai/consensus.py')],['python3',str(ROOT/'risk/risk_engine.py')],['python3',str(ROOT/'execution/execution_guard.py')],['python3',str(ROOT/'execution/live_preflight.py')]]
    for cmd in commands:
        p=subprocess.run(cmd,cwd=str(ROOT.parent),env=env,capture_output=True,text=True,timeout=300)
        if p.returncode!=0:return False,(p.stderr or p.stdout)[-1500:]
    return True,'PASS'
def notify(text):
    if CHAT_ID:
        try:tg('sendMessage',{'chat_id':CHAT_ID,'text':text})
        except Exception:pass
def update_local_item(trade_id,status,reason=None):
    q=load(PENDING,{'items':[]})
    for x in q.get('items',[]):
        if x.get('id')==trade_id:
            x['status']=status;x['resolved_at']=now().isoformat()
            if reason:x['reason']=reason
            save(PENDING,q);return x
    return None
def process_confirm(event):
    trade_id=event.get('trade_id');q=load(PENDING,{'items':[]});item=next((x for x in q.get('items',[]) if x.get('id')==trade_id),None)
    if not item or item.get('status')!='PENDING':return 'LOCAL_SIGNAL_NOT_PENDING'
    try:
        expires=datetime.fromisoformat(item['expires_at'].replace('Z','+00:00'))
        if now()>=expires:update_local_item(trade_id,'EXPIRED','TTL_EXPIRED_BEFORE_CONFIRMATION');return 'TTL_EXPIRED'
    except Exception:return 'INVALID_LOCAL_EXPIRY'
    update_local_item(trade_id,'CONFIRMING');ok,detail=run_revalidation()
    if not ok:update_local_item(trade_id,'REVALIDATION_FAILED',detail);return 'REVALIDATION_FAILED'
    risk=load(RISK,{'decisions':{}});guard=load(GUARD,{'decisions':{}});pre=load(STATE/'live_preflight.json',{})
    d=risk.get('decisions',{}).get(item['symbol'],{});g=guard.get('decisions',{}).get(item['symbol'],{});pf=(pre.get('decisions') or {}).get(item['symbol'],{})
    if not d.get('approved') or not g.get('executable') or not pf.get('eligible'):update_local_item(trade_id,'NO_LONGER_VALID','CURRENT_GUARD_OR_PREFLIGHT_REJECTED');return 'CURRENT_GUARD_OR_PREFLIGHT_REJECTED'
    if str(d.get('action')).upper()!=str(item.get('action')).upper():update_local_item(trade_id,'SETUP_CHANGED','DIRECTION_CHANGED');return 'DIRECTION_CHANGED'
    if str(d.get('strategy')).upper()!=str(item.get('strategy')).upper():update_local_item(trade_id,'SETUP_CHANGED','STRATEGY_CHANGED');return 'STRATEGY_CHANGED'
    if g.get('fingerprint')!=item.get('fingerprint'):update_local_item(trade_id,'SETUP_CHANGED','FINGERPRINT_CHANGED');return 'FINGERPRINT_CHANGED'
    old_entry=float(item['entry']);old_stop=float(item['stop_loss']);r=abs(old_entry-old_stop);px=current_price(item['symbol'])
    if r<=0 or abs(px-old_entry)>0.35*r:update_local_item(trade_id,'PRICE_MOVED',f'CURRENT_PRICE={px}');return 'PRICE_MOVED'
    confirmation={'status':'CONFIRMED','confirmed_at':now().isoformat(),'expires_in_seconds':30,'source_trade_id':trade_id,'symbol':item['symbol'],'action':item['action'],'strategy':item['strategy'],'fingerprint':g.get('fingerprint'),'decision':d,'confirmed_by_telegram_user':str(event.get('telegram_user_id','')),'source':'CLOUDFLARE_EXISTING_HUB'}
    save(CONFIRM,confirmation);p=subprocess.run(['python3',str(ROOT/'execution/live_executor.py')],cwd=str(ROOT.parent),env=os.environ.copy(),capture_output=True,text=True,timeout=120)
    out=load(EXEC_STATE,{});status=out.get('status') or ('EXECUTOR_OK' if p.returncode==0 else 'EXECUTOR_FAILED');update_local_item(trade_id,'CONFIRMED' if not out.get('executed') else 'EXECUTED',status);notify(f"🟨 BINANCE {item['symbol']} {item['action']}\n{status}\nExecuted: {bool(out.get('executed'))}");return status
def process_event(event):
    decision=str(event.get('decision','')).upper();trade_id=event.get('trade_id')
    if decision=='REJECTED':update_local_item(trade_id,'REJECTED','REJECTED_ON_EXISTING_HUB');return 'REJECTED'
    if decision=='CONFIRMED':return process_confirm(event)
    return 'IGNORED'
def main():
    if not TOKEN:raise SystemExit('TELEGRAM_BOT_TOKEN missing')
    origin=None;last_report=0.0
    while True:
        try:
            if not origin:origin=webhook_origin();print('HUB_ORIGIN',origin,flush=True)
            if time.time()-last_report>=10:report(origin);last_report=time.time()
            st=load(BRIDGE_STATE,{'last_seq':0});after=int(st.get('last_seq',0) or 0);feed=control_request(origin,'GET','/binance/control/feed',query={'after':after})
            for event in feed.get('events',[]):
                seq=int(event.get('seq',0) or 0);result=process_event(event);print('CONTROL_EVENT',seq,event.get('trade_id'),result,flush=True);after=max(after,seq);save(BRIDGE_STATE,{'last_seq':after,'updated_at':now().isoformat()})
            time.sleep(3)
        except Exception as exc:print('hub_control_bridge error:',repr(exc),flush=True);origin=None;time.sleep(5)
if __name__=='__main__':main()
