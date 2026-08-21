import json
import os
import subprocess
import urllib.request
import urllib.error
from common import load_snapshot, candidate_setups, compact_setup, parse_review_response, role_prompt

CLI_MODEL = os.environ.get('CLAUDE_CLI_MODEL','sonnet')
API_MODEL = os.environ.get('CLAUDE_API_MODEL','').strip()
API_KEY = os.environ.get('ANTHROPIC_API_KEY','').strip()
TIMEOUT_SECONDS = int(os.environ.get('CLAUDE_REVIEW_TIMEOUT_SECONDS','48'))
ROLE = '''
You are CLAUDE, the market-context/regime reviewer for Binance USDT perpetual scalps.
Specialty: context coherence, higher-timeframe pressure, regime fit, chase/exhaustion risk, and trigger timing.
Use 1d/4h/1h for pressure, 30m/15m for setup/regime, and 5m/3m/1m for trigger quality.
Do not duplicate portfolio/risk/exchange checks handled elsewhere. Focus on market context and timing.
'''
PROMPT = role_prompt(ROLE)
API_URL='https://api.anthropic.com/v1/messages'

def run_api(setups):
    # Static system prefix is cacheable; volatile market data stays outside the
    # cached prefix. This follows Anthropic prompt-caching guidance. If the
    # configured model/prompt is below provider cache thresholds, the request
    # still works; usage simply reports no cache read/write.
    body={
        'model':API_MODEL,
        'max_tokens':900,
        'temperature':0,
        'system':[{'type':'text','text':PROMPT,'cache_control':{'type':'ephemeral'}}],
        'messages':[{'role':'user','content':'MARKET_DATA='+json.dumps(setups,ensure_ascii=False,separators=(',',':'))}],
    }
    req=urllib.request.Request(API_URL,data=json.dumps(body).encode(),method='POST',headers={
        'x-api-key':API_KEY,'anthropic-version':'2023-06-01','content-type':'application/json','user-agent':'AUTO-FUTURES-V10-CLAUDE'
    })
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT_SECONDS) as r:data=json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return {'status':'ERROR','error':f'HTTP_{exc.code}:{exc.read().decode(errors="replace")[-700:]}','reviews':{},'transport':'API_CACHED'}
    except Exception as exc:
        return {'status':'ERROR','error':repr(exc),'reviews':{},'transport':'API_CACHED'}
    text=''.join(str(x.get('text','')) for x in data.get('content',[]) if x.get('type')=='text')
    clean,status=parse_review_response(text,setups)
    usage=data.get('usage') or {}
    return {'status':status,'model':API_MODEL,'review_count':len(clean),'reviews':clean,'transport':'API_CACHED','cache_usage':{
        'input_tokens':usage.get('input_tokens',0),'output_tokens':usage.get('output_tokens',0),
        'cache_creation_input_tokens':usage.get('cache_creation_input_tokens',0),'cache_read_input_tokens':usage.get('cache_read_input_tokens',0)
    }}

def run_cli(setups):
    payload=PROMPT+'\nMARKET_DATA='+json.dumps(setups,ensure_ascii=False,separators=(',',':'))
    try:
        p=subprocess.run(['claude','--model',CLI_MODEL,'-p',payload],capture_output=True,text=True,timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {'status':'TIMEOUT','timeout_seconds':TIMEOUT_SECONDS,'reviews':{},'transport':'CLI'}
    except Exception as exc:
        return {'status':'ERROR','error':repr(exc),'reviews':{},'transport':'CLI'}
    if p.returncode!=0:return {'status':'ERROR','error':p.stderr[-700:],'reviews':{},'transport':'CLI'}
    clean,status=parse_review_response(p.stdout.strip(),setups)
    return {'status':status,'model':CLI_MODEL,'review_count':len(clean),'reviews':clean,'transport':'CLI','prompt_cache':'NOT_EXPOSED_BY_CLI'}

def main():
    snap=load_snapshot();setups=[compact_setup(x) for x in candidate_setups(snap)]
    if not setups:
        print(json.dumps({'status':'OK','model':API_MODEL or CLI_MODEL,'review_count':0,'reviews':{},'transport':'IDLE'}));return
    # API caching is opt-in only when both credentials and an explicit model id
    # exist. Existing Claude subscription/CLI deployments keep working unchanged.
    out=run_api(setups) if API_KEY and API_MODEL else run_cli(setups)
    print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':main()
