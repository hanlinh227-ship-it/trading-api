import json
import os
import urllib.request
import urllib.error
from common import load_snapshot, candidate_setups, compact_setup, parse_review_response, role_prompt
from ai_budget_governor import record_deepseek_cost

URL='https://api.deepseek.com/chat/completions'
MODEL=os.environ.get('DEEPSEEK_MODEL','deepseek-v4-flash')
TIMEOUT_SECONDS=int(os.environ.get('DEEPSEEK_REVIEW_TIMEOUT_SECONDS','36'))
ROLE='''
You are DEEPSEEK, the adversarial edge/risk reviewer in a Binance perpetual SCALP council.
Specialty: attack fake breakouts, weak participation, extension, spread/cost drag, funding/OI crowding, taker-flow disagreement, volatility mismatch, and stop/target geometry.
Do not reject because a timeframe is merely neutral. Reject only material edge/risk invalidation.
Do not reverse casually; normally WAIT when scanner direction is not defensible.
'''
SYSTEM=role_prompt(ROLE)

def main():
    key=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if not key:
        print(json.dumps({'status':'UNAVAILABLE','error':'DEEPSEEK_API_KEY_NOT_LOADED','reviews':{}}));return
    snap=load_snapshot();setups=[compact_setup(x) for x in candidate_setups(snap)]
    if not setups:
        print(json.dumps({'status':'OK','model':MODEL,'review_count':0,'reviews':{},'transport':'API_JSON'}));return
    request_body={'model':MODEL,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':'MARKET_DATA='+json.dumps(setups,ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'temperature':0.05,'max_tokens':900,'stream':False}
    req=urllib.request.Request(URL,data=json.dumps(request_body).encode(),method='POST',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'AUTO-FUTURES-V10-DEEPSEEK'})
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT_SECONDS) as r:data=json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode(errors='replace')[-900:];status='RATE_LIMITED' if exc.code==429 else 'ERROR';print(json.dumps({'status':status,'error':f'HTTP_{exc.code}: {raw}','reviews':{}}));return
    except Exception as exc:
        status='TIMEOUT' if 'timed out' in repr(exc).lower() else 'ERROR';print(json.dumps({'status':status,'error':repr(exc),'reviews':{}}));return
    usage=data.get('usage') or {};pt=int(usage.get('prompt_tokens',0) or 0);ct=int(usage.get('completion_tokens',0) or 0);tt=int(usage.get('total_tokens',pt+ct) or pt+ct);hit=int(usage.get('prompt_cache_hit_tokens',0) or 0);miss=int(usage.get('prompt_cache_miss_tokens',max(0,pt-hit)) or 0)
    estimated_usd=record_deepseek_cost(pt,ct,tt,hit,miss,MODEL)
    try:text=data['choices'][0]['message']['content'].strip()
    except Exception as exc:
        print(json.dumps({'status':'INVALID_RESPONSE','error':str(exc),'usage':usage,'estimated_usd':estimated_usd,'reviews':{}}));return
    if not text:
        print(json.dumps({'status':'EMPTY_OUTPUT','error':'DEEPSEEK_JSON_MODE_EMPTY_CONTENT','usage':usage,'estimated_usd':estimated_usd,'reviews':{}}));return
    clean,status=parse_review_response(text,setups)
    print(json.dumps({'status':status,'model':MODEL,'review_count':len(clean),'transport':'API_JSON','usage':{'prompt_tokens':pt,'completion_tokens':ct,'total_tokens':tt,'prompt_cache_hit_tokens':hit,'prompt_cache_miss_tokens':miss},'estimated_usd':round(estimated_usd,8),'reviews':clean},ensure_ascii=False))

if __name__=='__main__':main()
