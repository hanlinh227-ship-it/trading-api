import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';RISK=STATE/'risk_decisions.json';GUARD=STATE/'execution_guard.json';PREFLIGHT=STATE/'live_preflight.json';RELIABILITY=STATE/'reliability_review.json';OUT=STATE/'pending_trades.json'
TTL_BY_STRATEGY={'BREAKOUT':60,'MOMENTUM':75,'TREND_PULLBACK':120,'MEAN_REVERSION':120};MAX_OPEN_POSITIONS=5

def now():return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def make_id(symbol,action,fingerprint):return hashlib.sha256(f'{symbol}|{action}|{fingerprint}'.encode()).hexdigest()[:18]
def main():
    risk=load(RISK,{'decisions':{}});guard=load(GUARD,{'decisions':{}});pre=load(PREFLIGHT,{});rel=load(RELIABILITY,{});old=load(OUT,{'items':[]});t=now()
    account_ok=bool(pre.get('account_ok'));live_open=pre.get('live_open_positions');open_positions=int(live_open if isinstance(live_open,int) else 0);slots=max(0,MAX_OPEN_POSITIONS-open_positions);reliability_block=bool(rel.get('must_block_live')) and str(rel.get('severity','')).upper() in {'HIGH','CRITICAL'}
    if not account_ok or reliability_block:
        items=[]
        for item in old.get('items',[]):
            if item.get('status') in {'PENDING','CONFIRMING'}:item['status']='EXPIRED_PREFLIGHT_BLOCK' if not reliability_block else 'EXPIRED_RELIABILITY_BLOCK';item['resolved_at']=t.isoformat()
            items.append(item)
        payload={'generated_at':t.isoformat(),'capacity':{'open_positions':open_positions,'max_open_positions':MAX_OPEN_POSITIONS,'available_slots':slots,'telegram_new_trade_notifications':False},'policy':{'confirmation_required':True,'live_preflight_required':True,'reliability_council_required':True,'fail_closed':True},'preflight_errors':pre.get('fatal_errors',[]) or ([] if account_ok else ['PREFLIGHT_NOT_READY']),'reliability_block':reliability_block,'reliability_severity':rel.get('severity'),'items':items[-100:]};save(OUT,payload);print('APPROVAL QUEUE: 0 pending |','RELIABILITY BLOCK' if reliability_block else 'LIVE PREFLIGHT BLOCK');return
    if slots<=0:
        items=[]
        for item in old.get('items',[]):
            if item.get('status') in {'PENDING','CONFIRMING'}:item['status']='EXPIRED_FULL_CAPACITY';item['resolved_at']=t.isoformat()
            items.append(item)
        save(OUT,{'generated_at':t.isoformat(),'capacity':{'open_positions':open_positions,'max_open_positions':MAX_OPEN_POSITIONS,'available_slots':0,'telegram_new_trade_notifications':False},'policy':{'confirmation_required':True,'suppress_new_signals_when_full':True},'items':items[-100:]});print('APPROVAL QUEUE: 0 pending | CAPACITY FULL 5/5');return
    old_by_id={x.get('id'):x for x in old.get('items',[]) if x.get('id')};items=[]
    for symbol,decision in risk.get('decisions',{}).items():
        if len([x for x in items if x.get('status')=='PENDING'])>=slots:break
        gd=guard.get('decisions',{}).get(symbol,{});pf=(pre.get('decisions') or {}).get(symbol,{})
        if not decision.get('approved') or not gd.get('executable') or not pf.get('eligible'):continue
        action=str(decision.get('action','WAIT')).upper()
        if action not in {'LONG','SHORT'}:continue
        fp=gd.get('fingerprint') or ''
        if not fp:continue
        strategy=str(decision.get('strategy','NO_EDGE')).upper();ttl=TTL_BY_STRATEGY.get(strategy,90);trade_id=make_id(symbol,action,fp);previous=old_by_id.get(trade_id,{});created=previous.get('created_at') or t.isoformat();created_dt=datetime.fromisoformat(created.replace('Z','+00:00'));expires=created_dt+timedelta(seconds=ttl);status=previous.get('status','PENDING')
        if status=='PENDING' and t>=expires:status='EXPIRED'
        items.append({'id':trade_id,'symbol':symbol,'action':action,'strategy':strategy,'entry':decision.get('entry'),'stop_loss':decision.get('stop_loss'),'tp1':decision.get('tp1'),'tp2':decision.get('tp2'),'tp3':decision.get('tp3'),'risk_pct':pf.get('live_risk_pct',pre.get('live_risk_pct')),'ai_confidence':decision.get('ai_confidence'),'signal_intelligence_score':decision.get('signal_intelligence_score'),'estimated_qty':pf.get('estimated_qty'),'estimated_notional':pf.get('estimated_notional'),'fingerprint':fp,'created_at':created,'expires_at':expires.isoformat(),'ttl_seconds':ttl,'status':status,'telegram_message_id':previous.get('telegram_message_id')})
    current_ids={x['id'] for x in items}
    for item in old.get('items',[]):
        if item.get('id') in current_ids:continue
        if item.get('status') in {'PENDING','CONFIRMING'}:item['status']='EXPIRED'
        items.append(item)
    payload={'generated_at':t.isoformat(),'capacity':{'open_positions':open_positions,'max_open_positions':MAX_OPEN_POSITIONS,'available_slots':slots,'telegram_new_trade_notifications':True},'policy':{'confirmation_required':True,'live_preflight_required':True,'reliability_council_required':True,'signal_quality_guard_required':True,'live_sizing_source':'BINANCE_AVAILABLE_BALANCE','fail_closed':True,'missed_signal_action':'EXPIRE_NO_TRADE','revalidate_on_confirm':True,'one_time_confirmation':True,'suppress_new_signals_when_full':True},'items':items[-100:]};save(OUT,payload)
    pending=[x for x in items if x.get('status')=='PENDING'];print('APPROVAL QUEUE:',len(pending),'pending | LIVE SLOTS',slots)
    for x in pending:print(x['id'],x['symbol'],x['action'],x['strategy'],'TTL',x['ttl_seconds'],'QTY',x.get('estimated_qty'),'RISK%',x.get('risk_pct'))
if __name__=='__main__':main()
