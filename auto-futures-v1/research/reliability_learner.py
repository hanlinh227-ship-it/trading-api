import json, os, hashlib, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';LOGS=ROOT/'logs'
INCIDENT=STATE/'execution_incident.json';PREFLIGHT=STATE/'live_preflight.json';EXEC=STATE/'live_executor_state.json';OUT=STATE/'reliability_review.json';CACHE=STATE/'reliability_review_cache.json'
COOLDOWN_SEC=21600

def now():return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def compact_dossier():
    inc=load(INCIDENT,{});pre=load(PREFLIGHT,{});ex=load(EXEC,{})
    reasons={}
    for s,d in (pre.get('decisions') or {}).items():
        for r in d.get('reasons',[]) or []:reasons[r]=reasons.get(r,0)+1
    return {'incident':inc if inc.get('active') else None,'preflight_fatal':pre.get('fatal_errors',[]) or [],'preflight_rejections':dict(sorted(reasons.items(),key=lambda x:-x[1])[:20]),'executor_status':ex.get('status'),'executor_executed':ex.get('executed'),'policy':{'max_positions':5,'isolated_only':True,'confirmation_required':True,'fail_closed':True,'no_source_self_rewrite':True}}
def fingerprint(d):return hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def parse_json(text):
    a=text.find('{');b=text.rfind('}')
    return json.loads(text[a:b+1]) if a>=0 and b>a else {'status':'INVALID_JSON','raw':text[-500:]}
def claude(prompt):
    try:
        p=subprocess.run(['claude','--model','sonnet','-p',prompt],capture_output=True,text=True,timeout=150)
        return parse_json(p.stdout) if p.returncode==0 else {'status':'ERROR','error':p.stderr[-600:]}
    except Exception as e:return {'status':'ERROR','error':repr(e)}
def codex(prompt):
    try:
        p=subprocess.run(['codex','exec',prompt],capture_output=True,text=True,timeout=180)
        return parse_json(p.stdout) if p.returncode==0 else {'status':'ERROR','error':p.stderr[-600:]}
    except Exception as e:return {'status':'ERROR','error':repr(e)}
def deepseek(prompt):
    key=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if not key:return {'status':'UNAVAILABLE'}
    body=json.dumps({'model':os.environ.get('DEEPSEEK_MODEL','deepseek-chat'),'messages':[{'role':'system','content':'You are an adversarial reliability reviewer for an automated Binance USD-M futures execution system. Find failure chains, race conditions, unsafe assumptions and missing fail-closed guards. JSON only.'},{'role':'user','content':prompt}],'temperature':0.1,'max_tokens':1400,'stream':False}).encode()
    try:
        req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=body,method='POST',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=120) as r:data=json.loads(r.read().decode())
        return parse_json(data['choices'][0]['message']['content'])
    except Exception as e:return {'status':'ERROR','error':repr(e)}
def main():
    dossier=compact_dossier();has_problem=bool(dossier['incident'] or dossier['preflight_fatal'] or dossier['preflight_rejections'] or (dossier['executor_status'] and 'EXECUTED' not in str(dossier['executor_status']) and 'DRY_RUN' not in str(dossier['executor_status']) and dossier['executor_status']!='NO_TELEGRAM_CONFIRMATION'))
    fp=fingerprint(dossier);cache=load(CACHE,{})
    try:age=(now()-datetime.fromisoformat(str(cache.get('reviewed_at','')).replace('Z','+00:00'))).total_seconds()
    except Exception:age=10**9
    if not has_problem:
        print('RELIABILITY COUNCIL: no new failure evidence; 0 AI tokens');return
    if cache.get('fingerprint')==fp and age<COOLDOWN_SEC:
        print('RELIABILITY COUNCIL: unchanged evidence; cached; 0 AI tokens');return
    base='''Review this compact failure dossier for a Binance USD-M futures AI trading system. The system uses per-trade Telegram confirmation, max 5 isolated positions, server-side SL/TP, live preflight, idempotent entry clientOrderId, and incident lock. Do NOT suggest removing confirmation or safety gates. Return JSON only with: {"severity":"LOW|MEDIUM|HIGH|CRITICAL","root_causes":[...],"missing_guards":[...],"recommended_changes":[...],"tests":[...],"must_block_live":true|false}. Focus on concrete engineering reliability, not trading alpha. DOSSIER='''+json.dumps(dossier,ensure_ascii=False)
    prompts={'claude':'You are the architecture/context reviewer. '+base,'deepseek':'You are the adversarial failure reviewer. '+base,'codex':'You are the code correctness/idempotency reviewer. '+base}
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={'claude':pool.submit(claude,prompts['claude']),'deepseek':pool.submit(deepseek,prompts['deepseek']),'codex':pool.submit(codex,prompts['codex'])}
        reviews={k:f.result() for k,f in fs.items()}
    must_block=any(bool((r or {}).get('must_block_live')) for r in reviews.values() if isinstance(r,dict));sevs=[str((r or {}).get('severity','LOW')).upper() for r in reviews.values() if isinstance(r,dict)];rank={'LOW':0,'MEDIUM':1,'HIGH':2,'CRITICAL':3};severity=max(sevs,key=lambda x:rank.get(x,0)) if sevs else 'LOW'
    out={'generated_at':now().isoformat(),'fingerprint':fp,'severity':severity,'must_block_live':must_block,'dossier':dossier,'reviews':reviews,'policy':{'event_gated':True,'cooldown_seconds':COOLDOWN_SEC,'source_code_auto_rewrite':False,'human_or_ci_validated_change_required':True}}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8');CACHE.write_text(json.dumps({'fingerprint':fp,'reviewed_at':now().isoformat()},indent=2),encoding='utf-8');LOGS.mkdir(parents=True,exist_ok=True)
    with (LOGS/'reliability_learning.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'generated_at':out['generated_at'],'fingerprint':fp,'severity':severity,'must_block_live':must_block},ensure_ascii=False)+'\n')
    print('RELIABILITY COUNCIL:',severity,'| BLOCK LIVE:',must_block,'| 3 reviewers completed')
if __name__=='__main__':main()
