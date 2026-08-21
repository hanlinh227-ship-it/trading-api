import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ai_budget_governor import allow, record_call, snapshot as budget_snapshot

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');AI_DIR=ROOT/'ai';STATE_DIR=ROOT/'state';LOG_DIR=ROOT/'logs'
SNAPSHOT=STATE_DIR/'market_snapshot.json';LIVE_PREFLIGHT=STATE_DIR/'live_preflight.json';OUT=STATE_DIR/'ai_consensus.json';CACHE=STATE_DIR/'ai_consensus_cache.json'
SCRIPTS={'claude':'claude_trader.py','deepseek':'deepseek_trader.py','codex':'codex_trader.py'};CACHE_TTL_SECONDS=90

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

def event_fingerprint(snapshot,live_count):
    rows=[]
    for x in snapshot.get('ai_candidates') or snapshot.get('setups') or []:
        action=str(x.get('candidate_action','WAIT')).upper()
        if action not in {'LONG','SHORT'}:continue
        rows.append({'symbol':x.get('symbol'),'action':action,'strategy':x.get('strategy'),'regime':x.get('regime'),'quality5':int(float(x.get('setup_quality',0) or 0)//5)*5,'blockers':x.get('blockers') or [],'warnings':(x.get('warnings') or [])[:3]})
    raw=json.dumps({'candidates':rows[:12],'live_open_count':live_count},sort_keys=True,separators=(',',':'))
    return hashlib.sha256(raw.encode()).hexdigest()

def actionable(snapshot):
    return [x for x in snapshot.get('ai_candidates') or snapshot.get('setups') or [] if str(x.get('candidate_action','WAIT')).upper() in {'LONG','SHORT'}]

def run_ai(name,script,priority):
    ok,why=allow(name,priority)
    if not ok:return name,{'status':'BUDGET_BLOCKED','budget_reason':why,'reviews':{}}
    try:
        p=subprocess.run(['python3',script],cwd=AI_DIR,capture_output=True,text=True,timeout=220)
        if name in {'claude','codex'}:record_call(name,purpose='LIVE_POSITION_REVIEW' if priority=='POSITION' else 'TRADE_REVIEW',meta={'returncode':p.returncode})
        if p.returncode!=0:return name,{'status':'ERROR','error':p.stderr[-1500:],'reviews':{}}
        out=p.stdout.strip()
        if not out:return name,{'status':'ERROR','error':'EMPTY_OUTPUT','reviews':{}}
        return name,json.loads(out.splitlines()[-1])
    except Exception as exc:
        if name in {'claude','codex'}:record_call(name,purpose='FAILED_CALL',meta={'error':type(exc).__name__})
        return name,{'status':'ERROR','error':repr(exc),'reviews':{}}

def main():
    snapshot=load(SNAPSHOT,{'setups':[]});live_count=live_open_count();fp=event_fingerprint(snapshot,live_count);cache=load(CACHE,{})
    candidates=actionable(snapshot)
    if not candidates and live_count<=0:
        out={'generated_at':datetime.now(timezone.utc).isoformat(),'policy':{'token_mode':'EVENT_GATED','reason':'NO_ACTIONABLE_SETUP_AND_NO_LIVE_POSITION','paper_positions_ignored_for_ai_budget':True,'budget':budget_snapshot()},'claude_status':'SKIPPED','deepseek_status':'SKIPPED','codex_status':'SKIPPED','symbols':{}}
        OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');print('3-AI SKIPPED: no actionable setup and no LIVE position');return
    if cache.get('fingerprint')==fp and age_seconds(cache.get('generated_at'))<CACHE_TTL_SECONDS and cache.get('consensus'):
        out=cache['consensus'];out['generated_at']=datetime.now(timezone.utc).isoformat();out.setdefault('policy',{})['token_mode']='CACHE_REUSE';out['policy']['budget']=budget_snapshot();OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');print('3-AI CACHE REUSED');return
    priority='POSITION' if live_count>0 else 'NORMAL'
    print('Starting budget-governed Claude + DeepSeek + Codex reviewers...',flush=True)
    results={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(run_ai,n,s,priority) for n,s in SCRIPTS.items()]
        for f in futures:n,r=f.result();results[n]=r
    review_maps={n:(results.get(n,{}).get('reviews',{}) or {}) for n in SCRIPTS};symbols=sorted(set().union(*(set(x) for x in review_maps.values())));decisions={}
    for symbol in symbols:
        reviews={n:review_maps[n].get(symbol) for n in SCRIPTS};available={n:r for n,r in reviews.items() if isinstance(r,dict)}
        actions=[str(r.get('action','WAIT')).upper() for r in available.values()];conf=[float(r.get('confidence',0) or 0) for r in available.values()]
        longs,shorts,waits=actions.count('LONG'),actions.count('SHORT'),actions.count('WAIT');final_action,reason='WAIT','NO_EDGE'
        if len(available)<3:reason='MISSING_AI_REVIEW_OR_BUDGET_BLOCK'
        elif longs>=2 and shorts==0:
            directional=[float(r.get('confidence',0) or 0) for r in available.values() if str(r.get('action','')).upper()=='LONG']
            if directional and sum(directional)/len(directional)>=62:final_action,reason='LONG','TWO_OF_THREE_PLUS_NO_OPPOSITION'
            else:reason='LONG_CONFIDENCE_TOO_LOW'
        elif shorts>=2 and longs==0:
            directional=[float(r.get('confidence',0) or 0) for r in available.values() if str(r.get('action','')).upper()=='SHORT']
            if directional and sum(directional)/len(directional)>=62:final_action,reason='SHORT','TWO_OF_THREE_PLUS_NO_OPPOSITION'
            else:reason='SHORT_CONFIDENCE_TOO_LOW'
        elif longs and shorts:reason='DIRECTIONAL_CONFLICT'
        elif waits==3:reason='THREE_AI_WAIT'
        decisions[symbol]={'reviews':reviews,'available_reviewers':len(available),'actions':actions,'average_confidence':round(sum(conf)/len(conf),2) if conf else 0.0,'final_action':final_action,'reason':reason}
    out={'generated_at':datetime.now(timezone.utc).isoformat(),'policy':{'style':'SCALP_ONLY_24_7','decision_rule':'2_of_3_same_direction_no_opposition','three_ai_required':True,'token_mode':'EVENT_GATED_BUDGET_GOVERNED','cache_ttl_seconds':CACHE_TTL_SECONDS,'priority':priority,'live_open_positions_hint':live_count,'paper_positions_ignored_for_ai_budget':True,'budget':budget_snapshot()},'claude_status':results.get('claude',{}).get('status','ERROR'),'deepseek_status':results.get('deepseek',{}).get('status','ERROR'),'codex_status':results.get('codex',{}).get('status','ERROR'),'symbols':decisions}
    STATE_DIR.mkdir(parents=True,exist_ok=True);LOG_DIR.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');CACHE.write_text(json.dumps({'generated_at':out['generated_at'],'fingerprint':fp,'consensus':out},indent=2,ensure_ascii=False),encoding='utf-8')
    with (LOG_DIR/'ai_consensus.jsonl').open('a',encoding='utf-8') as log:log.write(json.dumps(out,ensure_ascii=False)+'\n')
    print('='*48);print('V8 BUDGET-GOVERNED THREE-AI CONSENSUS');print('='*48);print('Claude:',out['claude_status'],'DeepSeek:',out['deepseek_status'],'Codex:',out['codex_status']);print('LIVE POSITIONS HINT:',live_count);print('BUDGET:',json.dumps(out['policy']['budget'],ensure_ascii=False))
    for s,d in decisions.items():print(s,'|','/'.join(d['actions']),'| FINAL',d['final_action'],'| CONF',d['average_confidence'],'|',d['reason'])
if __name__=='__main__':main()
