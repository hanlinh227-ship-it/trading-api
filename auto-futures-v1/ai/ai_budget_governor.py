import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';BUDGET=STATE/'ai_budget.json';LOCK_PATH='/tmp/auto-futures-ai-budget.lock'
CLAUDE_WINDOW_HOURS=float(os.environ.get('CLAUDE_BUDGET_WINDOW_HOURS','5'));CLAUDE_MAX_CALLS_5H=int(os.environ.get('CLAUDE_MAX_CALLS_5H','24'));CLAUDE_RESERVE_CALLS=int(os.environ.get('CLAUDE_RESERVE_CALLS_5H','6'));DEEPSEEK_DAILY_USD=float(os.environ.get('DEEPSEEK_DAILY_BUDGET_USD','1.00'));DEEPSEEK_MONTHLY_USD=float(os.environ.get('DEEPSEEK_MONTHLY_BUDGET_USD','15.00'));CODEX_MAX_CALLS_5H=int(os.environ.get('CODEX_MAX_CALLS_5H','40'))

def now():return datetime.now(timezone.utc)
@contextmanager
def locked():
    fh=open(LOCK_PATH,'w')
    try:fcntl.flock(fh.fileno(),fcntl.LOCK_EX);yield
    finally:
        try:fcntl.flock(fh.fileno(),fcntl.LOCK_UN)
        finally:fh.close()
def load():
    try:return json.loads(BUDGET.read_text(encoding='utf-8')) if BUDGET.exists() else {}
    except Exception:return {}
def save(x):
    STATE.mkdir(parents=True,exist_ok=True);tmp=BUDGET.with_suffix('.json.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(BUDGET)
def parse(ts):
    try:return datetime.fromisoformat(str(ts).replace('Z','+00:00'))
    except Exception:return None
def prune_calls(calls,hours):
    cutoff=now()-timedelta(hours=hours);return [x for x in (calls or []) if parse(x.get('at')) and parse(x.get('at'))>=cutoff]
def month_key(dt=None):return (dt or now()).strftime('%Y-%m')
def day_key(dt=None):return (dt or now()).strftime('%Y-%m-%d')

def snapshot():
    s=load();claude=prune_calls(s.get('claude_calls',[]),CLAUDE_WINDOW_HOURS);codex=prune_calls(s.get('codex_calls',[]),CLAUDE_WINDOW_HOURS);costs=s.get('deepseek_costs',[]);today=day_key();month=month_key();daily=sum(float(x.get('usd',0) or 0) for x in costs if str(x.get('day'))==today);monthly=sum(float(x.get('usd',0) or 0) for x in costs if str(x.get('month'))==month);last_ds=costs[-1] if costs else {}
    return {'generated_at':now().isoformat(),'claude':{'window_hours':CLAUDE_WINDOW_HOURS,'max_calls':CLAUDE_MAX_CALLS_5H,'used_calls':len(claude),'remaining_calls':max(0,CLAUDE_MAX_CALLS_5H-len(claude)),'reserve_calls':CLAUDE_RESERVE_CALLS,'exact_provider_tokens_remaining_known':False},'deepseek':{'daily_budget_usd':DEEPSEEK_DAILY_USD,'daily_spent_usd':round(daily,8),'daily_remaining_usd':round(max(0,DEEPSEEK_DAILY_USD-daily),8),'monthly_budget_usd':DEEPSEEK_MONTHLY_USD,'monthly_spent_usd':round(monthly,8),'monthly_remaining_usd':round(max(0,DEEPSEEK_MONTHLY_USD-monthly),8),'paid_api':True,'last_model':last_ds.get('model'),'last_cache_hit_tokens':last_ds.get('prompt_cache_hit_tokens',0),'last_cache_miss_tokens':last_ds.get('prompt_cache_miss_tokens',0)},'codex':{'window_hours':CLAUDE_WINDOW_HOURS,'max_calls':CODEX_MAX_CALLS_5H,'used_calls':len(codex),'remaining_calls':max(0,CODEX_MAX_CALLS_5H-len(codex))}}

def allow(provider,priority='NORMAL'):
    snap=snapshot();p=provider.lower();priority=priority.upper()
    if p=='claude':
        rem=snap['claude']['remaining_calls']
        if priority in {'CRITICAL','POSITION','CONFIRM'}:return rem>0,('PASS' if rem>0 else 'CLAUDE_5H_BUDGET_EXHAUSTED')
        return rem>CLAUDE_RESERVE_CALLS,('PASS' if rem>CLAUDE_RESERVE_CALLS else 'CLAUDE_RESERVE_PROTECTED')
    if p=='deepseek':
        d=snap['deepseek'];ok=d['daily_remaining_usd']>0 and d['monthly_remaining_usd']>0;return ok,('PASS' if ok else 'DEEPSEEK_USD_BUDGET_EXHAUSTED')
    if p=='codex':
        rem=snap['codex']['remaining_calls'];return rem>0,('PASS' if rem>0 else 'CODEX_5H_BUDGET_EXHAUSTED')
    return False,'UNKNOWN_PROVIDER'

def record_call(provider,purpose='TRADE_REVIEW',meta=None):
    with locked():
        s=load();p=provider.lower();row={'at':now().isoformat(),'purpose':purpose,'meta':meta or {}}
        if p=='claude':s['claude_calls']=prune_calls(s.get('claude_calls',[]),CLAUDE_WINDOW_HOURS)+[row]
        elif p=='codex':s['codex_calls']=prune_calls(s.get('codex_calls',[]),CLAUDE_WINDOW_HOURS)+[row]
        save(s)

def deepseek_rates(model):
    # Official DeepSeek pricing snapshot used only for local budget estimation.
    # AUTO_MODEL intentionally ignores legacy manual price vars unless explicitly requested.
    if os.environ.get('DEEPSEEK_PRICE_MODE','AUTO_MODEL').upper()=='MANUAL':
        return float(os.environ.get('DEEPSEEK_CACHE_HIT_USD_PER_M_TOKENS','0.0028')),float(os.environ.get('DEEPSEEK_CACHE_MISS_USD_PER_M_TOKENS','0.14')),float(os.environ.get('DEEPSEEK_OUTPUT_USD_PER_M_TOKENS','0.28'))
    m=str(model or '').lower()
    if 'pro' in m:return .003625,.435,.87
    return .0028,.14,.28

def record_deepseek_cost(prompt_tokens,completion_tokens,total_tokens=None,prompt_cache_hit_tokens=0,prompt_cache_miss_tokens=None,model='deepseek-v4-flash'):
    pt=int(prompt_tokens or 0);ct=int(completion_tokens or 0);hit=max(0,int(prompt_cache_hit_tokens or 0));miss=int(prompt_cache_miss_tokens if prompt_cache_miss_tokens is not None else max(0,pt-hit));hit=min(hit,pt);miss=max(0,min(miss,pt-hit if hit else pt));hit_rate,miss_rate,out_rate=deepseek_rates(model);usd=hit/1_000_000*hit_rate+miss/1_000_000*miss_rate+ct/1_000_000*out_rate
    with locked():
        s=load();row={'at':now().isoformat(),'day':day_key(),'month':month_key(),'model':model,'prompt_tokens':pt,'completion_tokens':ct,'total_tokens':int(total_tokens or (pt+ct)),'prompt_cache_hit_tokens':hit,'prompt_cache_miss_tokens':miss,'rates_per_m':{'cache_hit':hit_rate,'cache_miss':miss_rate,'output':out_rate},'usd':usd};s.setdefault('deepseek_costs',[]).append(row);s['deepseek_costs']=s['deepseek_costs'][-5000:];save(s)
    return usd

if __name__=='__main__':print(json.dumps(snapshot(),indent=2,ensure_ascii=False))
