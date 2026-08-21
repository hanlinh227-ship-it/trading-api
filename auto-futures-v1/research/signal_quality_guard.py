import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state'
SNAP=STATE/'market_snapshot.json';OUT=STATE/'signal_quality_guard.json'
DEFAULT_COST_BPS=12.0

def now():return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def f(x,default=None):
    try:return float(x)
    except Exception:return default
def unique(xs):
    out=[]
    for x in xs:
        if x and x not in out:out.append(x)
    return out

def tfv(s,tf,key):return f(((s.get('timeframes') or {}).get(tf) or {}).get(key))
def evaluate(s):
    action=str(s.get('candidate_action','WAIT')).upper();strategy=str(s.get('strategy','NO_EDGE')).upper()
    blockers=list(s.get('blockers') or []);warnings=list(s.get('warnings') or [])
    if action not in {'LONG','SHORT'}:
        return s,{'eligible_for_ai':False,'reason':'NOT_ACTIONABLE'}
    sign=1 if action=='LONG' else -1
    entry=f(s.get('entry'));stop=f(s.get('stop_loss'));tp1=f(s.get('tp1'));tp3=f(s.get('tp3'))
    spread=f(s.get('spread_bps'),0.0) or 0.0;cost=f(s.get('estimated_roundtrip_cost_bps'),DEFAULT_COST_BPS) or DEFAULT_COST_BPS
    risk_bps=None;reward1_bps=None
    if entry and entry>0 and stop is not None:
        risk_bps=abs(entry-stop)/entry*10000
        if risk_bps<=max(8.0,cost*1.75):blockers.append('QUALITY_GUARD: stop distance too small versus trading cost/noise')
        if spread>min(12.0,max(2.0,risk_bps*0.25)):blockers.append('QUALITY_GUARD: spread consumes too much of stop distance')
    else:blockers.append('QUALITY_GUARD: invalid entry/stop geometry')
    if entry and entry>0 and tp1 is not None:
        reward1_bps=abs(tp1-entry)/entry*10000
        if reward1_bps<=cost*1.8:blockers.append('QUALITY_GUARD: TP1 edge too small after round-trip cost')
    if None not in (entry,stop,tp3):
        if action=='LONG' and not (stop<entry<tp3):blockers.append('QUALITY_GUARD: LONG protection geometry invalid')
        if action=='SHORT' and not (stop>entry>tp3):blockers.append('QUALITY_GUARD: SHORT protection geometry invalid')

    mtf=s.get('mtf_alignment') or {};macro=f(mtf.get('macro'),0.0) or 0.0;setup=f(mtf.get('setup'),0.0) or 0.0;trigger=f(mtf.get('trigger'),0.0) or 0.0
    if trigger*sign<0.10:blockers.append('QUALITY_GUARD: execution trigger lacks directional confirmation')
    if setup*sign<-0.25:blockers.append('QUALITY_GUARD: setup layer materially opposes entry')
    if macro*sign<-0.45:blockers.append('QUALITY_GUARD: macro layer strongly opposes entry')

    d5=tfv(s,'5m','distance_ema21_atr')
    if d5 is not None and d5*sign>2.15:blockers.append('QUALITY_GUARD: 5m entry is overextended/chased')
    rsi1=tfv(s,'1m','rsi14');v1=tfv(s,'1m','volume_ratio');v5=tfv(s,'5m','volume_ratio');m5=tfv(s,'5m','momentum_3')
    if strategy=='BREAKOUT':
        participation=max(v for v in (v1,v5) if v is not None) if any(v is not None for v in (v1,v5)) else None
        if participation is not None and participation<0.90:blockers.append('QUALITY_GUARD: breakout lacks participation')
        if m5 is not None and m5*sign<=0:warnings.append('QUALITY_GUARD: breakout 5m momentum not yet expanding')
    elif strategy=='MOMENTUM':
        if v1 is not None and v1<0.55:warnings.append('QUALITY_GUARD: momentum participation is weak')
        if abs(trigger)<0.25:blockers.append('QUALITY_GUARD: momentum trigger too weak')
    elif strategy=='TREND_PULLBACK':
        if macro*sign<0.20 or setup*sign<0.20:blockers.append('QUALITY_GUARD: pullback lacks aligned higher/setup structure')
    elif strategy=='MEAN_REVERSION':
        if abs(macro)>0.65:blockers.append('QUALITY_GUARD: mean reversion fighting strong macro trend')

    if rsi1 is not None:
        if action=='LONG' and rsi1>76:warnings.append('QUALITY_GUARD: LONG trigger RSI stretched')
        if action=='SHORT' and rsi1<24:warnings.append('QUALITY_GUARD: SHORT trigger RSI stretched')

    base=f(s.get('setup_quality',s.get('setup_score',0)),0.0) or 0.0
    penalty=min(18.0,2.5*len([x for x in warnings if str(x).startswith('QUALITY_GUARD')]))
    score=max(0.0,min(100.0,base-penalty))
    s['blockers']=unique(blockers);s['warnings']=unique(warnings);s['signal_intelligence_score']=round(score,2)
    s['signal_intelligence']={'engine':'V10_SIGNAL_QUALITY_GUARD','risk_bps':round(risk_bps,3) if risk_bps is not None else None,'tp1_reward_bps':round(reward1_bps,3) if reward1_bps is not None else None,'spread_bps':round(spread,3),'roundtrip_cost_bps':round(cost,3),'macro':macro,'setup':setup,'trigger':trigger,'eligible_for_ai':not bool(s['blockers'])}
    return s,s['signal_intelligence']

def main():
    snap=load(SNAP,{})
    report={'generated_at':now().isoformat(),'engine':'V10_SIGNAL_QUALITY_GUARD','symbols':{}}
    maps={}
    primary=snap.get('ai_candidates') or snap.get('setups') or []
    for x in primary:
        if not isinstance(x,dict) or not x.get('symbol'):continue
        y,meta=evaluate(x);maps[str(y['symbol']).upper()]=y;report['symbols'][str(y['symbol']).upper()]={'eligible':bool(meta.get('eligible_for_ai')),'blockers':y.get('blockers',[]),'warnings':y.get('warnings',[]),'score':y.get('signal_intelligence_score')}
    for key in ('ai_candidates','setups'):
        rows=snap.get(key)
        if not isinstance(rows,list):continue
        snap[key]=[maps.get(str(x.get('symbol','')).upper(),x) if isinstance(x,dict) else x for x in rows]
    SNAP.write_text(json.dumps(snap,indent=2,ensure_ascii=False),encoding='utf-8');OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    eligible=sum(1 for x in report['symbols'].values() if x.get('eligible'));print(f'SIGNAL QUALITY GUARD: {eligible}/{len(report["symbols"])} actionable candidates remain eligible for 3-AI')
if __name__=='__main__':main()
