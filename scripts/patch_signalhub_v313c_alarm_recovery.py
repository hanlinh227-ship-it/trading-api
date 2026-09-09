from pathlib import Path
import re

W=Path('signalhub-worker/gateway-v3.js')
w=W.read_text()

old="""  async ensureCryptoMonitor(delayMs=25){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(!active.length){try{await this.state.storage.deleteAlarm();}catch{}return {ok:true,running:false,activeCrypto:0};}
    const target=Date.now()+Math.max(25,Number(delayMs)||25),old=await this.state.storage.getAlarm();
    if(old===null||Number(old)>target+250)await this.state.storage.setAlarm(target);
    return {ok:true,running:true,activeCrypto:active.length,nextAlarmMs:target};
  }"""
new="""  async ensureCryptoMonitor(delayMs=25){
    const reg=await this.registry(),active=this.activeRows(reg).filter(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(!active.length){try{await this.state.storage.deleteAlarm();}catch{}const status={ok:true,running:false,activeCrypto:0,receivedAt:nowIso()};await this.state.storage.put('cryptoMonitorStatus',status);return status;}
    const now=Date.now(),target=now+Math.max(25,Number(delayMs)||25),old=await this.state.storage.getAlarm();
    // A Durable Object alarm can retain a stale timestamp across a deployment/restart. Always
    // re-arm on an explicit kick/register so a persisted `running:true` state can never mask a dead alarm.
    await this.state.storage.setAlarm(target);
    return {ok:true,running:true,activeCrypto:active.length,previousAlarmMs:old==null?null:Number(old),nextAlarmMs:target,rearmed:true};
  }"""
if old not in w: raise SystemExit('ensureCryptoMonitor pattern missing')
w=w.replace(old,new,1)

old_alarm="""  async alarm(){
    try{await this.cryptoMonitorCycle();}catch(e){await this.state.storage.put('cryptoMonitorStatus',{ok:false,running:true,error:String(e?.message||e),receivedAt:nowIso()});}
    const reg=await this.registry(),still=this.activeRows(reg).some(x=>String(x.market||'').toUpperCase()==='CRYPTO');
    if(still)await this.state.storage.setAlarm(Date.now()+1000);else try{await this.state.storage.deleteAlarm();}catch{}
  }"""
new_alarm="""  async alarm(){
    let still=false;
    try{await this.cryptoMonitorCycle();}
    catch(e){await this.state.storage.put('cryptoMonitorStatus',{ok:false,running:true,error:String(e?.message||e),receivedAt:nowIso()});}
    finally{
      try{const reg=await this.registry();still=this.activeRows(reg).some(x=>String(x.market||'').toUpperCase()==='CRYPTO');}catch{}
      if(still)await this.state.storage.setAlarm(Date.now()+1000);else try{await this.state.storage.deleteAlarm();}catch{}
    }
  }"""
if old_alarm not in w: raise SystemExit('alarm pattern missing')
w=w.replace(old_alarm,new_alarm,1)

# Surface actual scheduled alarm time for diagnostics; this lets CI distinguish a healthy recurring
# alarm from a stale persisted status object.
old_status="""    if(req.method==='GET'&&url.pathname==='/crypto-monitor-status'){const status=(await this.state.storage.get('cryptoMonitorStatus'))||{ok:true,running:false,cycle:0};return new Response(JSON.stringify(status),{headers:{'content-type':'application/json'}});}"""
new_status="""    if(req.method==='GET'&&url.pathname==='/crypto-monitor-status'){const status=(await this.state.storage.get('cryptoMonitorStatus'))||{ok:true,running:false,cycle:0},alarmAt=await this.state.storage.getAlarm();return new Response(JSON.stringify({...status,alarmAtMs:alarmAt==null?null:Number(alarmAt),alarmArmed:alarmAt!==null}),{headers:{'content-type':'application/json'}});}"""
if old_status not in w: raise SystemExit('monitor status pattern missing')
w=w.replace(old_status,new_status,1)

W.write_text(w)
print('patched V3.13c durable alarm recovery/re-arm')
