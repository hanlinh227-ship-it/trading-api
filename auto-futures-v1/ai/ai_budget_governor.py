import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/opt/trading/trading-api/auto-futures-v1')
STATE = ROOT / 'state'
BUDGET = STATE / 'ai_budget.json'
LOCK_PATH = '/tmp/auto-futures-ai-budget.lock'

CLAUDE_WINDOW_HOURS = float(os.environ.get('CLAUDE_BUDGET_WINDOW_HOURS', '5'))
CLAUDE_MAX_CALLS_5H = int(os.environ.get('CLAUDE_MAX_CALLS_5H', '24'))
CLAUDE_RESERVE_CALLS = int(os.environ.get('CLAUDE_RESERVE_CALLS_5H', '6'))
DEEPSEEK_DAILY_USD = float(os.environ.get('DEEPSEEK_DAILY_BUDGET_USD', '1.00'))
DEEPSEEK_MONTHLY_USD = float(os.environ.get('DEEPSEEK_MONTHLY_BUDGET_USD', '15.00'))
CODEX_MAX_CALLS_5H = int(os.environ.get('CODEX_MAX_CALLS_5H', '40'))


def now(): return datetime.now(timezone.utc)
@contextmanager
def locked():
    fh=open(LOCK_PATH,'w')
    try:
        fcntl.flock(fh.fileno(),fcntl.LOCK_EX);yield
    finally:
        try:fcntl.flock(fh.fileno(),fcntl.LOCK_UN)
        finally:fh.close()
def load():
    try: return json.loads(BUDGET.read_text(encoding='utf-8')) if BUDGET.exists() else {}
    except Exception: return {}
def save(x):
    STATE.mkdir(parents=True, exist_ok=True);tmp=BUDGET.with_suffix('.json.tmp');tmp.write_text(json.dumps(x, indent=2, ensure_ascii=False), encoding='utf-8');tmp.replace(BUDGET)
def parse(ts):
    try: return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except Exception: return None
def prune_calls(calls, hours):
    cutoff = now() - timedelta(hours=hours);out=[]
    for x in calls or []:
        dt=parse(x.get('at'))
        if dt and dt >= cutoff: out.append(x)
    return out
def month_key(dt=None): return (dt or now()).strftime('%Y-%m')
def day_key(dt=None): return (dt or now()).strftime('%Y-%m-%d')

def snapshot():
    s=load();claude=prune_calls(s.get('claude_calls',[]), CLAUDE_WINDOW_HOURS);codex=prune_calls(s.get('codex_calls',[]), CLAUDE_WINDOW_HOURS);costs=s.get('deepseek_costs',[]);today=day_key();month=month_key();daily=sum(float(x.get('usd',0) or 0) for x in costs if str(x.get('day'))==today);monthly=sum(float(x.get('usd',0) or 0) for x in costs if str(x.get('month'))==month)
    return {'generated_at':now().isoformat(),'claude':{'window_hours':CLAUDE_WINDOW_HOURS,'max_calls':CLAUDE_MAX_CALLS_5H,'used_calls':len(claude),'remaining_calls':max(0,CLAUDE_MAX_CALLS_5H-len(claude)),'reserve_calls':CLAUDE_RESERVE_CALLS,'exact_provider_tokens_remaining_known':False},'deepseek':{'daily_budget_usd':DEEPSEEK_DAILY_USD,'daily_spent_usd':round(daily,8),'daily_remaining_usd':round(max(0,DEEPSEEK_DAILY_USD-daily),8),'monthly_budget_usd':DEEPSEEK_MONTHLY_USD,'monthly_spent_usd':round(monthly,8),'monthly_remaining_usd':round(max(0,DEEPSEEK_MONTHLY_USD-monthly),8),'paid_api':True},'codex':{'window_hours':CLAUDE_WINDOW_HOURS,'max_calls':CODEX_MAX_CALLS_5H,'used_calls':len(codex),'remaining_calls':max(0,CODEX_MAX_CALLS_5H-len(codex))}}

def allow(provider, priority='NORMAL'):
    snap=snapshot();p=provider.lower();priority=priority.upper()
    if p=='claude':
        rem=snap['claude']['remaining_calls']
        if priority in {'CRITICAL','POSITION','CONFIRM'}: return rem>0, ('PASS' if rem>0 else 'CLAUDE_5H_BUDGET_EXHAUSTED')
        return rem>CLAUDE_RESERVE_CALLS, ('PASS' if rem>CLAUDE_RESERVE_CALLS else 'CLAUDE_RESERVE_PROTECTED')
    if p=='deepseek':
        d=snap['deepseek'];ok=d['daily_remaining_usd']>0 and d['monthly_remaining_usd']>0;return ok, ('PASS' if ok else 'DEEPSEEK_USD_BUDGET_EXHAUSTED')
    if p=='codex':
        rem=snap['codex']['remaining_calls'];return rem>0, ('PASS' if rem>0 else 'CODEX_5H_BUDGET_EXHAUSTED')
    return False,'UNKNOWN_PROVIDER'

def record_call(provider, purpose='TRADE_REVIEW', meta=None):
    with locked():
        s=load();p=provider.lower();row={'at':now().isoformat(),'purpose':purpose,'meta':meta or {}}
        if p=='claude': s['claude_calls']=prune_calls(s.get('claude_calls',[]),CLAUDE_WINDOW_HOURS)+[row]
        elif p=='codex': s['codex_calls']=prune_calls(s.get('codex_calls',[]),CLAUDE_WINDOW_HOURS)+[row]
        save(s)

def record_deepseek_cost(prompt_tokens, completion_tokens, total_tokens=None):
    in_per_m=float(os.environ.get('DEEPSEEK_INPUT_USD_PER_M_TOKENS','0.28'));out_per_m=float(os.environ.get('DEEPSEEK_OUTPUT_USD_PER_M_TOKENS','0.42'));usd=(float(prompt_tokens or 0)/1_000_000)*in_per_m+(float(completion_tokens or 0)/1_000_000)*out_per_m
    with locked():
        s=load();row={'at':now().isoformat(),'day':day_key(),'month':month_key(),'prompt_tokens':int(prompt_tokens or 0),'completion_tokens':int(completion_tokens or 0),'total_tokens':int(total_tokens or ((prompt_tokens or 0)+(completion_tokens or 0))),'usd':usd};s.setdefault('deepseek_costs',[]).append(row);s['deepseek_costs']=s['deepseek_costs'][-5000:];save(s)
    return usd

if __name__=='__main__': print(json.dumps(snapshot(), indent=2, ensure_ascii=False))
