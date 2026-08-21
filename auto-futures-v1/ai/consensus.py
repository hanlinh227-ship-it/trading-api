import fcntl
import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from ai_budget_governor import allow, record_call, snapshot as budget_snapshot
from ai_coordination import circuit_allowed, record_result, health_snapshot, build_coordination_policy

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');AI_DIR=ROOT/'ai';STATE_DIR=ROOT/'state';LOG_DIR=ROOT/'logs'
SNAPSHOT=STATE_DIR/'market_snapshot.json';LIVE_PREFLIGHT=STATE_DIR/'live_preflight.json';OUT=STATE_DIR/'ai_consensus.json';CACHE=STATE_DIR/'ai_consensus_cache.json'
SCRIPTS={'claude':'claude_trader.py','deepseek':'deepseek_trader.py','codex':'codex_trader.py'};CACHE_TTL_SECONDS=90
AI_REVIEW_TIMEOUT_SECONDS=int(os.environ.get('AI_REVIEW_TIMEOUT_SECONDS','60'));COUNCIL_LOCK_WAIT_SECONDS=int(os.environ.get('AI_COUNCIL_LOCK_WAIT_SECONDS','20'));LOCK_PATH='/tmp/auto-futures-ai-council.lock'

def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def age_seconds(ts):
    try:return (datetime.now(timezone.utc)-datetime.fromisoformat(str(ts).replace('Z','+00:00'))).total_seconds()
    except Exception:return 10**9
def live_open_count():
    p=load(LIVE_PREFLIGHT,{})
    try:return max(0,int(p.get('live_open_positions',0) or 0))
    except Exception:return 0
def score(x):return float(x.get('signal_intelligence_score',x.get('setup_quality',x.get('setup_score',0))) or 0)
def actionable(snapshot):
    rows=[x for x in snapshot.get('ai_candidates') or snapshot.get('setups') or [] if str(x.get('candidate_action','WAIT')).upper() in {'LONG','SHORT'} and not (x.get('blockers') or [])]
    rows.sort(key=lambda x:(score(x),-float(x.get('spread_bps',999999) or 999999)),reverse=True);return rows[:3]
def event_fingerprint(snapshot,live_count):
    rows=[]
    for x in actionable(snapshot):rows.append({'symbol':x.get('symbol'),'action':str(x.get('candidate_action')).upper(),'strategy':x.get('strategy'),'regime':x.get('regime'),'quality5':int(score(x)//5)*5,'warnings':(x.get('warnings') or [])[:3]})
    return hashlib.sha256(json.dumps({'candidates':rows,'live_open_count':live_count},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def acquire_council_lock():
    fh=open(LOCK_PATH,'w');deadline=time.time()+COUNCIL_LOCK_WAIT_SECONDS
    while True:
        try:fcntl.flock(fh.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);return fh
        except BlockingIOError:
            if time.time()>=deadline:fh.close();return None
            time.sleep(.2)

def run_ai(name,script,priority,candidate_count):
    circuit_ok,circuit_reason=circuit_allowed(name,priority)
    if not circuit_ok:
        r={'status':'CIRCUIT_OPEN','circuit_reason':circuit_reason,'reviews':{}};record_result(name,r['status'],review_count=0,candidate_count=candidate_count,error=circuit_reason);return name,r
    budget_ok,budget_reason=allow(name,priority)
    if not budget_ok:
        r={'status':'BUDGET_BLOCKED','budget_reason':budget_reason,'reviews':{}};record_result(name,r['status'],review_count=0,candidate_count=candidate_count,error=budget_reason);return name,r
    started=datetime.now(timezone.utc)
    try:
        p=subprocess.run(['python3',script],cwd=AI_DIR,capture_output=True,text=True,timeout=AI_REVIEW_TIMEOUT_SECONDS);elapsed=(datetime.now(timezone.utc)-started).total_seconds()
        if name in {'claude','codex'}:record_call(name,purpose='LIVE_POSITION_REVIEW' if priority=='POSITION' else 'TRADE_REVIEW',meta={'returncode':p.returncode,'elapsed_seconds':round(elapsed,2)})
        if p.returncode!=0:r={'status':'ERROR','error':p.stderr[-1000:],'elapsed_seconds':round(elapsed,2),'reviews':{}}
        else:
            out=p.stdout.strip()
            if not out:r={'status':'ERROR','error':'EMPTY_OUTPUT','elapsed_seconds':round(elapsed,2),'reviews':{}}
            else:
                try:r=json.loads(out.splitlines()[-1]);r['elapsed_seconds']=round(elapsed,2)
                except Exception as exc:r={'status':'INVALID_JSON','error':repr(exc),'elapsed_seconds':round(elapsed,2),'reviews':{}}
    except subprocess.TimeoutExpired:
        elapsed=(datetime.now(timezone.utc)-started).total_seconds()
        if name in {'claude','codex'}:record_call(name,purpose='TIMEOUT',meta={'elapsed_seconds':round(elapsed,2)})
        r={'status':'TIMEOUT','error':f'AI_REVIEW_TIMEOUT_{AI_REVIEW_TIMEOUT_SECONDS}S','elapsed_seconds':round(elapsed,2),'reviews':{}}
    except Exception as exc:
        elapsed=(datetime.now(timezone.utc)-started).total_seconds()
        if name in {'claude','codex'}:record_call(name,purpose='FAILED_CALL',meta={'error':type(exc).__name__,'elapsed_seconds':round(elapsed,2)})
        r={'status':'ERROR','error':repr(exc),'elapsed_seconds':round(elapsed,2),'reviews':{}}
    record_result(name,r.get('status','ERROR'),elapsed=r.get('elapsed_seconds'),review_count=len(r.get('reviews') or {}),candidate_count=candidate_count,error=r.get('error') or r.get('budget_reason') or r.get('circuit_reason'));return name,r

def make_decisions(results):
    review_maps={n:(results.get(n,{}).get('reviews',{}) or {}) for n in SCRIPTS};symbols=sorted(set().union(*(set(x) for x in review_maps.values()))) if review_maps else [];all_ok=all(str((results.get(n) or {}).get('status','')).upper()=='OK' for n in SCRIPTS);decisions={}
    for symbol in symbols:
        reviews={n:review_maps[n].get(symbol) for n in SCRIPTS};available={n:r for n,r in reviews.items() if isinstance(r,dict)};actions=[str(r.get('action','WAIT')).upper() for r in available.values()];longs,shorts,waits=actions.count('LONG'),actions.count('SHORT'),actions.count('WAIT');final_action,reason='WAIT','NO_EDGE';directional_conf=[]
        if not all_ok or len(available)<3:reason='THREE_AI_HEALTH_REQUIRED'
        elif longs>=2 and shorts==0:
            directional_conf=[float(r.get('confidence',0) or 0) for r in available.values() if str(r.get('action','')).upper()=='LONG'];avg=sum(directional_conf)/len(directional_conf) if directional_conf else 0
            if avg>=62:final_action,reason='LONG','TWO_OF_THREE_PLUS_NO_OPPOSITION'
            else:reason='LONG_CONFIDENCE_TOO_LOW'
        elif shorts>=2 and longs==0:
            directional_conf=[float(r.get('confidence',0) or 0) for r in available.values() if str(r.get('action','')).upper()=='SHORT'];avg=sum(directional_conf)/len(directional_conf) if directional_conf else 0
            if avg>=62:final_action,reason='SHORT','TWO_OF_THREE_PLUS_NO_OPPOSITION'
            else:reason='SHORT_CONFIDENCE_TOO_LOW'
        elif longs and shorts:reason='TRUE_DIRECTIONAL_CONFLICT'
        elif waits==3:reason='THREE_AI_WAIT'
        conf=round(sum(directional_conf)/len(directional_conf),2) if directional_conf else 0.0;decisions[symbol]={'reviews':reviews,'available_reviewers':len(available),'actions':actions,'average_confidence':conf,'consensus_confidence':conf,'confidence_definition':'DIRECTIONAL_REVIEWERS_ONLY','final_action':final_action,'reason':reason}
    return decisions

def write_idle(reason):
    h=health_snapshot();last=load(OUT,{});out={'generated_at':datetime.now(timezone.utc).isoformat(),'last_active_consensus_at':last.get('last_active_consensus_at') or last.get('generated_at'),'policy':{'token_mode':'IDLE','reason':reason,'budget':budget_snapshot(),'provider_health':h},'claude_status':(h.get('claude') or {}).get('last_status','UNKNOWN'),'deepseek_status':(h.get('deepseek') or {}).get('last_status','UNKNOWN'),'codex_status':(h.get('codex') or {}).get('last_status','UNKNOWN'),'reviewer_latency_seconds':{n:(h.get(n) or {}).get('avg_latency_seconds') for n in SCRIPTS},'symbols':{}}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');build_coordination_policy();print('3-AI IDLE:',reason)

def main():
    snapshot=load(SNAPSHOT,{'setups':[]});live_count=live_open_count();fp=event_fingerprint(snapshot,live_count);cache=load(CACHE,{});candidates=actionable(snapshot)
    if not candidates and live_count<=0:return write_idle('NO_ACTIONABLE_SETUP_AND_NO_LIVE_POSITION')
    if cache.get('fingerprint')==fp and age_seconds(cache.get('generated_at'))<CACHE_TTL_SECONDS and cache.get('consensus'):
        out=cache['consensus'];out['generated_at']=datetime.now(timezone.utc).isoformat();out.setdefault('policy',{})['token_mode']='CACHE_REUSE';out['policy']['budget']=budget_snapshot();out['policy']['provider_health']=health_snapshot();OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');print('3-AI CACHE REUSED');return
    lock=acquire_council_lock()
    if not lock:
        if cache.get('fingerprint')==fp and age_seconds(cache.get('generated_at'))<180 and cache.get('consensus'):
            out=cache['consensus'];out['generated_at']=datetime.now(timezone.utc).isoformat();out.setdefault('policy',{})['token_mode']='SINGLE_FLIGHT_CACHE_REUSE';OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');print('3-AI SINGLE-FLIGHT: reused current cache');return
        return write_idle('COUNCIL_BUSY_NO_FRESH_CACHE')
    try:
        cache=load(CACHE,{})
        if cache.get('fingerprint')==fp and age_seconds(cache.get('generated_at'))<CACHE_TTL_SECONDS and cache.get('consensus'):
            out=cache['consensus'];out['generated_at']=datetime.now(timezone.utc).isoformat();out.setdefault('policy',{})['token_mode']='POST_LOCK_CACHE_REUSE';OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');print('3-AI POST-LOCK CACHE REUSED');return
        priority='POSITION' if live_count>0 else 'NORMAL';print(f'Starting V10 coordinated 3-AI council | top {len(candidates)} | timeout {AI_REVIEW_TIMEOUT_SECONDS}s...',flush=True);results={}
        with ThreadPoolExecutor(max_workers=3) as pool:
            future_map={pool.submit(run_ai,n,s,priority,len(candidates)):n for n,s in SCRIPTS.items()}
            for f in as_completed(future_map):n,r=f.result();results[n]=r;print(f'AI reviewer finished: {n} | {r.get("status")} | {r.get("elapsed_seconds","-")}s',flush=True)
        decisions=make_decisions(results);generated=datetime.now(timezone.utc).isoformat();provider_meta={n:{k:(results.get(n,{}) or {}).get(k) for k in ('model','transport','cache_usage','usage','estimated_usd') if (results.get(n,{}) or {}).get(k) is not None} for n in SCRIPTS}
        out={'generated_at':generated,'last_active_consensus_at':generated,'policy':{'style':'SCALP_ONLY_24_7','decision_rule':'2_of_3_same_direction_no_opposition','three_ai_required':True,'confidence_rule':'directional_reviewers_only','token_mode':'COORDINATED_SINGLE_FLIGHT_TOP3','candidate_limit':3,'cache_ttl_seconds':CACHE_TTL_SECONDS,'ai_review_timeout_seconds':AI_REVIEW_TIMEOUT_SECONDS,'priority':priority,'budget':budget_snapshot(),'provider_health':health_snapshot()},'claude_status':results.get('claude',{}).get('status','ERROR'),'deepseek_status':results.get('deepseek',{}).get('status','ERROR'),'codex_status':results.get('codex',{}).get('status','ERROR'),'reviewer_latency_seconds':{n:(results.get(n,{}) or {}).get('elapsed_seconds') for n in SCRIPTS},'provider_meta':provider_meta,'symbols':decisions}
        STATE_DIR.mkdir(parents=True,exist_ok=True);LOG_DIR.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');CACHE.write_text(json.dumps({'generated_at':generated,'fingerprint':fp,'consensus':out},indent=2,ensure_ascii=False),encoding='utf-8')
        with (LOG_DIR/'ai_consensus.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(out,ensure_ascii=False)+'\n')
        coord=build_coordination_policy(decisions);print('='*56);print('V10 COORDINATED THREE-AI COUNCIL');print('='*56);print('Claude:',out['claude_status'],'DeepSeek:',out['deepseek_status'],'Codex:',out['codex_status']);print('LATENCY:',json.dumps(out['reviewer_latency_seconds']));print('HEALTH:',json.dumps(coord.get('provider_health',{}),ensure_ascii=False))
        for s,d in decisions.items():print(s,'|','/'.join(d['actions']),'| FINAL',d['final_action'],'| DIR_CONF',d['consensus_confidence'],'|',d['reason'])
    finally:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_UN);lock.close()
        except Exception:pass
if __name__=='__main__':main()
