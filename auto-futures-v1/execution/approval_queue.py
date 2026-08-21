import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';RISK=STATE/'risk_decisions.json';GUARD=STATE/'execution_guard.json';OUT=STATE/'pending_trades.json'
TTL_BY_STRATEGY={'BREAKOUT':60,'MOMENTUM':75,'TREND_PULLBACK':120,'MEAN_REVERSION':120};MAX_OPEN_POSITIONS=5

def now():return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def make_id(symbol,action,fingerprint):return hashlib.sha256(f'{symbol}|{action}|{fingerprint}'.encode()).hexdigest()[:18]
def main():
    risk=load(RISK,{'decisions':{}});guard=load(GUARD,{'decisions':{}});old=load(OUT,{'items':[]});t=now();open_positions=int(risk.get('open_positions',0) or 0);slots=max(0,MAX_OPEN_POSITIONS-open_positions)
    # If all five slots are occupied, expire unresolved approvals and publish no PENDING item.
    if slots<=0:
        items=[]
        for item in old.get('items',[]):
            if item.get('status') in {'PENDING','CONFIRMING'}:
                item['status']='EXPIRED_FULL_CAPACITY';item['resolved_at']=t.isoformat()
            items.append(item)
        payload={'generated_at':t.isoformat(),'capacity':{'open_positions':open_positions,'max_open_positions':MAX_OPEN_POSITIONS,'available_slots':0,'telegram_new_trade_notifications':False},'policy':{'confirmation_required':True,'missed_signal_action':'EXPIRE_NO_TRADE','suppress_new_signals_when_full':True},'items':items[-100:]}
        save(OUT,payload);print('APPROVAL QUEUE: 0 pending | CAPACITY FULL 5/5 | TELEGRAM NEW-TRADE NOTIFICATIONS SUPPRESSED');return
    old_by_id={x.get('id'):x for x in old.get('items',[]) if x.get('id')};items=[]
    for symbol,decision in risk.get('decisions',{}).items():
        if len([x for x in items if x.get('status')=='PENDING'])>=slots:break
        gd=guard.get('decisions',{}).get(symbol,{})
        if not decision.get('approved') or not gd.get('executable'):continue
        action=str(decision.get('action','WAIT')).upper()
        if action not in {'LONG','SHORT'}:continue
        fp=gd.get('fingerprint') or ''
        if not fp:continue
        strategy=str(decision.get('strategy','NO_EDGE')).upper();ttl=TTL_BY_STRATEGY.get(strategy,90);trade_id=make_id(symbol,action,fp);previous=old_by_id.get(trade_id,{})
        created=previous.get('created_at') or t.isoformat();created_dt=datetime.fromisoformat(created.replace('Z','+00:00'));expires=created_dt+timedelta(seconds=ttl);status=previous.get('status','PENDING')
        if status=='PENDING' and t>=expires:status='EXPIRED'
        items.append({'id':trade_id,'symbol':symbol,'action':action,'strategy':strategy,'entry':decision.get('entry'),'stop_loss':decision.get('stop_loss'),'tp1':decision.get('tp1'),'tp2':decision.get('tp2'),'tp3':decision.get('tp3'),'risk_pct':decision.get('risk_pct'),'ai_confidence':decision.get('ai_confidence'),'fingerprint':fp,'created_at':created,'expires_at':expires.isoformat(),'ttl_seconds':ttl,'status':status,'telegram_message_id':previous.get('telegram_message_id')})
    current_ids={x['id'] for x in items}
    for item in old.get('items',[]):
        if item.get('id') in current_ids:continue
        if item.get('status') in {'PENDING','CONFIRMING'}:item['status']='EXPIRED'
        items.append(item)
    payload={'generated_at':t.isoformat(),'capacity':{'open_positions':open_positions,'max_open_positions':MAX_OPEN_POSITIONS,'available_slots':slots,'telegram_new_trade_notifications':True},'policy':{'confirmation_required':True,'missed_signal_action':'EXPIRE_NO_TRADE','revalidate_on_confirm':True,'one_time_confirmation':True,'suppress_new_signals_when_full':True},'items':items[-100:]};save(OUT,payload)
    pending=[x for x in items if x.get('status')=='PENDING'];print('APPROVAL QUEUE:',len(pending),'pending | SLOTS',slots)
    for x in pending:print(x['id'],x['symbol'],x['action'],x['strategy'],'TTL',x['ttl_seconds'])
if __name__=='__main__':main()
