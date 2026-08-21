import json, os, hashlib, subprocess, urllib.request, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';LOGS=ROOT/'logs'
INCIDENT=STATE/'execution_incident.json';PREFLIGHT=STATE/'live_preflight.json';EXEC=STATE/'live_executor_state.json';OUT=STATE/'reliability_review.json';CACHE=STATE/'reliability_review_cache.json'
COOLDOWN_SEC=21600
sys.path.insert(0,str(ROOT/'ai'))
from ai_budget_governor import allow, record_call, record_deepseek_cost, snapshot as budget_snapshot

EXPECTED_REJECTIONS={
 'RISK_NOT_APPROVED','NO_EDGE','SCANNER_BLOCKER','AI_CONFIDENCE_BELOW_LEARNED_THRESHOLD','REQUIRE_3_AI',
 'ENTRY_MISSING','STOP_MISSING','TP_MISSING','MISSING_ENTRY_OR_PROTECTION','ENTRY_TOO_STALE_FOR_LIVE',
 'QTY_BELOW_MIN','QTY_ABOVE_MAX','NOTIONAL_BELOW_MIN','QTY_BELOW_EXCHANGE_MIN','NOTIONAL_BELOW_EXCHANGE_MIN',
 'POSITION_ALREADY_OPEN_LIVE','MAX_5_LIVE_POSITIONS','CURRENT_GUARD_REJECTED','DIRECTION_CHANGED','FINGERPRINT_CHANGED'
}
EXECUTOR_BAD_MARKERS=('ERROR','FAILED','UNKNOWN','INCIDENT','UNPROTECTED','MISMATCH')

def now():return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default

def compact_dossier():
    inc=load(INCIDENT,{});pre=load(PREFLIGHT,{});ex=load(EXEC,{})
    reasons={};abnormal={};expected={}
    for _,d in (pre.get('decisions') or {}).items():
        for r in d.get('reasons',[]) or []:
            base=str(r).split(':',1)[0];reasons[base]=reasons.get(base,0)+1
            target=expected if base in EXPECTED_REJECTIONS else abnormal
            target[base]=target.get(base,0)+1
    status=ex.get('status')
    bad_executor=bool(status and any(x in str(status).upper() for x in EXECUTOR_BAD_MARKERS))
    return {
      'incident':inc if inc.get('active') else None,
      'preflight_fatal':pre.get('fatal_errors',[]) or [],
      'abnormal_preflight_rejections':dict(sorted(abnormal.items(),key=lambda x:-x[1])[:20]),
      'expected_preflight_rejections':dict(sorted(expected.items(),key=lambda x:-x[1])[:20]),
      'executor_status':status,'executor_bad_status':bad_executor,
      'live_open_positions':pre.get('live_open_positions'),'account_ok':pre.get('account_ok'),
      'policy':{'max_positions':5,'isolated_only':True,'confirmation_required':True,'fail_closed':True,'no_source_self_rewrite':True}
    }

def fingerprint(d):return hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def parse_json(text):
    a=text.find('{');b=text.rfind('}')
    return json.loads(text[a:b+1]) if a>=0 and b>a else {'status':'INVALID_JSON','raw':text[-500:]}

def claude(prompt):
    ok,why=allow('claude','CRITICAL')
    if not ok:return {'status':'BUDGET_BLOCKED','reason':why}
    try:
        p=subprocess.run(['claude','--model','sonnet','-p',prompt],capture_output=True,text=True,timeout=150);record_call('claude','RELIABILITY_INCIDENT',{'returncode':p.returncode})
        return parse_json(p.stdout) if p.returncode==0 else {'status':'ERROR','error':p.stderr[-600:]}
    except Exception as e:return {'status':'ERROR','error':repr(e)}

def codex(prompt):
    ok,why=allow('codex','CRITICAL')
    if not ok:return {'status':'BUDGET_BLOCKED','reason':why}
    try:
        p=subprocess.run(['codex','exec',prompt],capture_output=True,text=True,timeout=180);record_call('codex','RELIABILITY_INCIDENT',{'returncode':p.returncode})
        return parse_json(p.stdout) if p.returncode==0 else {'status':'ERROR','error':p.stderr[-600:]}
    except Exception as e:return {'status':'ERROR','error':repr(e)}

def deepseek(prompt):
    ok,why=allow('deepseek','CRITICAL')
    if not ok:return {'status':'BUDGET_BLOCKED','reason':why}
    key=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if not key:return {'status':'UNAVAILABLE'}
    body=json.dumps({'model':os.environ.get('DEEPSEEK_MODEL','deepseek-chat'),'messages':[{'role':'system','content':'Adversarial reliability reviewer for Binance USD-M execution. Only treat concrete technical failure evidence as a live blocker. Expected trade rejections are not incidents. JSON only.'},{'role':'user','content':prompt}],'temperature':0.1,'max_tokens':1000,'stream':False}).encode()
    try:
        req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=body,method='POST',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=120) as r:data=json.loads(r.read().decode())
        u=data.get('usage') or {};record_deepseek_cost(u.get('prompt_tokens',0),u.get('completion_tokens',0),u.get('total_tokens'))
        return parse_json(data['choices'][0]['message']['content'])
    except Exception as e:return {'status':'ERROR','error':repr(e)}

def main():
    dossier=compact_dossier()
    has_problem=bool(dossier['incident'] or dossier['preflight_fatal'] or dossier['abnormal_preflight_rejections'] or dossier['executor_bad_status'] or dossier.get('account_ok') is False)
    fp=fingerprint(dossier);cache=load(CACHE,{})
    try:age=(now()-datetime.fromisoformat(str(cache.get('reviewed_at','')).replace('Z','+00:00'))).total_seconds()
    except Exception:age=10**9
    if not has_problem:
        out={'generated_at':now().isoformat(),'fingerprint':fp,'severity':'LOW','must_block_live':False,'dossier':dossier,'reviews':{},'policy':{'event_gated':True,'reason':'NO_TECHNICAL_FAILURE_EVIDENCE','expected_trade_rejections_do_not_block_live':True,'budget':budget_snapshot()}}
        OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');print('RELIABILITY COUNCIL: healthy/expected rejections only; 0 AI tokens');return
    if cache.get('fingerprint')==fp and age<COOLDOWN_SEC:
        print('RELIABILITY COUNCIL: unchanged technical failure evidence; cached; 0 AI tokens');return
    base='''Review this technical failure dossier for a Binance USD-M futures system. IMPORTANT: expected trade-quality rejections are normal and must NOT be treated as incidents. Only concrete execution/account/preflight technical failures may block live. Return JSON only: {"severity":"LOW|MEDIUM|HIGH|CRITICAL","root_causes":[...],"missing_guards":[...],"recommended_changes":[...],"tests":[...],"must_block_live":true|false}. DOSSIER='''+json.dumps(dossier,ensure_ascii=False)
    prompts={'claude':'Architecture/context reviewer. '+base,'deepseek':'Adversarial failure reviewer. '+base,'codex':'Code correctness/idempotency reviewer. '+base}
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={'claude':pool.submit(claude,prompts['claude']),'deepseek':pool.submit(deepseek,prompts['deepseek']),'codex':pool.submit(codex,prompts['codex'])};reviews={k:f.result() for k,f in fs.items()}
    valid=[r for r in reviews.values() if isinstance(r,dict) and r.get('status') not in {'BUDGET_BLOCKED','UNAVAILABLE','ERROR'}]
    must_block=bool(dossier['incident'] or dossier['preflight_fatal'] or dossier['executor_bad_status'] or dossier.get('account_ok') is False) or any(bool(r.get('must_block_live')) for r in valid)
    rank={'LOW':0,'MEDIUM':1,'HIGH':2,'CRITICAL':3};sevs=[str(r.get('severity','LOW')).upper() for r in valid];severity=max(sevs,key=lambda x:rank.get(x,0)) if sevs else ('HIGH' if must_block else 'MEDIUM')
    out={'generated_at':now().isoformat(),'fingerprint':fp,'severity':severity,'must_block_live':must_block,'dossier':dossier,'reviews':reviews,'policy':{'event_gated':True,'cooldown_seconds':COOLDOWN_SEC,'expected_trade_rejections_do_not_block_live':True,'source_code_auto_rewrite':False,'budget':budget_snapshot()}}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');CACHE.write_text(json.dumps({'fingerprint':fp,'reviewed_at':now().isoformat()},indent=2),encoding='utf-8');LOGS.mkdir(parents=True,exist_ok=True)
    with (LOGS/'reliability_learning.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'generated_at':out['generated_at'],'fingerprint':fp,'severity':severity,'must_block_live':must_block},ensure_ascii=False)+'\n')
    print('RELIABILITY COUNCIL:',severity,'| BLOCK LIVE:',must_block,'| incident-driven budget-governed review')
if __name__=='__main__':main()
