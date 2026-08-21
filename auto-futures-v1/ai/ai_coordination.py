import json
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';LOGS=ROOT/'logs'
HEALTH=STATE/'ai_provider_health.json';POLICY=STATE/'ai_coordination_policy.json';CONS_LOG=LOGS/'ai_consensus.jsonl'
PROVIDERS=('claude','deepseek','codex')
FAIL_STATUSES={'TIMEOUT','ERROR','INVALID_JSON','INVALID_RESPONSE','UNAVAILABLE','RATE_LIMITED'}
CIRCUIT_FAILURES=3;CIRCUIT_MINUTES=10;MAX_EVENTS=120


def now():return datetime.now(timezone.utc)
def iso():return now().isoformat()
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def save(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def parse(ts):
    try:return datetime.fromisoformat(str(ts).replace('Z','+00:00'))
    except Exception:return None

def circuit_allowed(provider,priority='NORMAL'):
    s=load(HEALTH,{});p=(s.get('providers') or {}).get(provider,{})
    until=parse(p.get('circuit_until'))
    if not until or now()>=until:return True,'PASS'
    if str(priority).upper() in {'CRITICAL','CONFIRM','POSITION'}:
        # Critical paths may probe once instead of being permanently blinded by a stale circuit.
        last_probe=parse(p.get('last_critical_probe_at'))
        if not last_probe or (now()-last_probe).total_seconds()>=60:
            p['last_critical_probe_at']=iso();s.setdefault('providers',{})[provider]=p;save(HEALTH,s);return True,'CRITICAL_PROBE'
    return False,f'CIRCUIT_OPEN_UNTIL_{until.isoformat()}'

def record_result(provider,status,elapsed=None,review_count=0,candidate_count=0,error=None):
    s=load(HEALTH,{'providers':{}});p=s.setdefault('providers',{}).setdefault(provider,{})
    ev={'at':iso(),'status':str(status).upper(),'elapsed_seconds':elapsed,'review_count':int(review_count or 0),'candidate_count':int(candidate_count or 0),'error':str(error or '')[:300]}
    events=(p.get('events') or [])+[ev];events=events[-MAX_EVENTS:];p['events']=events;p['last_status']=ev['status'];p['last_at']=ev['at']
    if ev['status']=='OK':
        p['consecutive_failures']=0;p['last_ok_at']=ev['at'];p['circuit_until']=None
    elif ev['status'] in FAIL_STATUSES:
        n=int(p.get('consecutive_failures',0) or 0)+1;p['consecutive_failures']=n
        if n>=CIRCUIT_FAILURES:p['circuit_until']=(now()+timedelta(minutes=CIRCUIT_MINUTES)).isoformat()
    # BUDGET_BLOCKED/SKIPPED are availability states, not provider failures.
    ok=[x for x in events if x.get('status')=='OK'];fail=[x for x in events if x.get('status') in FAIL_STATUSES]
    lat=[float(x.get('elapsed_seconds')) for x in ok if x.get('elapsed_seconds') is not None]
    p['success_rate']=round(len(ok)/max(1,len(ok)+len(fail)),4);p['avg_latency_seconds']=round(sum(lat)/len(lat),2) if lat else None
    cov=[]
    for x in ok:
        c=int(x.get('candidate_count',0) or 0);r=int(x.get('review_count',0) or 0)
        if c>0:cov.append(min(1.0,r/c))
    p['coverage_rate']=round(sum(cov)/len(cov),4) if cov else None
    s['generated_at']=iso();save(HEALTH,s);return p

def health_snapshot():
    s=load(HEALTH,{'providers':{}});out={}
    for name in PROVIDERS:
        p=(s.get('providers') or {}).get(name,{})
        until=parse(p.get('circuit_until'));circuit='OPEN' if until and now()<until else 'CLOSED'
        out[name]={'last_status':p.get('last_status','UNKNOWN'),'last_ok_at':p.get('last_ok_at'),'success_rate':p.get('success_rate'),'avg_latency_seconds':p.get('avg_latency_seconds'),'coverage_rate':p.get('coverage_rate'),'consecutive_failures':int(p.get('consecutive_failures',0) or 0),'circuit':circuit,'circuit_until':p.get('circuit_until')}
    return out

def build_coordination_policy(current_decisions=None):
    rows=[]
    if CONS_LOG.exists():
        try:
            lines=CONS_LOG.read_text(encoding='utf-8').splitlines()[-120:]
            for line in lines:
                try:rows.append(json.loads(line))
                except Exception:pass
        except Exception:pass
    conflicts=Counter();provider_opposition=Counter();provider_wait=Counter();samples=0
    for row in rows:
        for sym,d in (row.get('symbols') or {}).items():
            reviews=d.get('reviews') or {};acts={p:str((reviews.get(p) or {}).get('action','MISSING')).upper() for p in PROVIDERS};vals=[x for x in acts.values() if x!='MISSING']
            if len(set(vals))>1:
                key=f"{str((reviews.get('claude') or {}).get('strategy') or (reviews.get('deepseek') or {}).get('strategy') or 'UNKNOWN').upper()}|{'/'.join(sorted(set(vals)))}";conflicts[key]+=1
            for p,a in acts.items():
                if a=='WAIT':provider_wait[p]+=1
            samples+=1
    repeated=[{'pattern':k,'count':v} for k,v in conflicts.most_common(5) if v>=2]
    policy={'generated_at':iso(),'method':'bounded coordination meta-learning; health/routing only; no autonomous source rewrite; no provider voting weight from paper PnL','provider_health':health_snapshot(),'repeated_conflicts':repeated,'observed_symbol_reviews':samples,'provider_wait_counts':dict(provider_wait),'guardrails':{'three_ai_required_for_new_entry':True,'circuit_failure_threshold':CIRCUIT_FAILURES,'circuit_minutes':CIRCUIT_MINUTES,'critical_probe_interval_seconds':60,'no_autonomous_prompt_rewrite':True,'no_live_source_rewrite':True,'do_not_suppress_real_disagreement':True}}
    save(POLICY,policy);return policy

if __name__=='__main__':print(json.dumps(build_coordination_policy(),indent=2,ensure_ascii=False))
