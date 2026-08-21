import json
import os
import urllib.request
import urllib.error
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review
from ai_budget_governor import record_deepseek_cost

URL = 'https://api.deepseek.com/chat/completions'
MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
SYSTEM = '''
You are DEEPSEEK, the adversarial risk/edge reviewer in a 24/7 Binance perpetual SCALP system.
Every eligible candidate has deep multi-timeframe data: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d.
Attack the proposed trade layer-by-layer. Reject fake breakouts, stale momentum, weak participation, excessive extension, RSI exhaustion, volatility mismatch, wide spread, funding/OI crowding, taker-flow disagreement, bad stop geometry, and targets too small after costs.
There is no daily trade-count quota. Reject for lack of edge, not arbitrary frequency. Historical learning is weak evidence only.
Return JSON only: {"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|COUNTERTREND|MIXED","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"...","invalidation":"..."}]}
No markdown.
'''

def main():
    key=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if not key:
        print(json.dumps({'status':'UNAVAILABLE','error':'DEEPSEEK_API_KEY_NOT_LOADED','reviews':{}}));return
    snap=load_snapshot();setups=[compact_setup(x) for x in candidate_setups(snap)]
    body=json.dumps({'model':MODEL,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(setups,ensure_ascii=False)}],'temperature':0.1,'max_tokens':2200,'stream':False}).encode()
    req=urllib.request.Request(URL,data=body,method='POST',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:data=json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        print(json.dumps({'status':'ERROR','error':f"HTTP_{exc.code}: {exc.read().decode(errors='replace')}",'reviews':{}}));return
    except Exception as exc:
        print(json.dumps({'status':'ERROR','error':repr(exc),'reviews':{}}));return
    usage=data.get('usage') or {};pt=int(usage.get('prompt_tokens',0) or 0);ct=int(usage.get('completion_tokens',0) or 0);tt=int(usage.get('total_tokens',pt+ct) or pt+ct)
    estimated_usd=record_deepseek_cost(pt,ct,tt)
    try:
        text=data['choices'][0]['message']['content'].strip();a,b=text.find('{'),text.rfind('}');obj=json.loads(text[a:b+1])
    except Exception as exc:
        print(json.dumps({'status':'INVALID_JSON','error':str(exc),'usage':usage,'estimated_usd':estimated_usd,'reviews':{}}));return
    clean={}
    for r in obj.get('reviews',[]):
        if not validate_review(r):continue
        sym=str(r['symbol']).upper();clean[sym]={'symbol':sym,'regime':str(r.get('regime','UNKNOWN')).upper(),'strategy':str(r.get('strategy','NO_EDGE')).upper(),'action':str(r.get('action','WAIT')).upper(),'confidence':normalize_confidence(r.get('confidence',0)),'reason':str(r.get('reason','')),'invalidation':str(r.get('invalidation',''))}
    print(json.dumps({'status':'OK','model':MODEL,'review_count':len(clean),'usage':{'prompt_tokens':pt,'completion_tokens':ct,'total_tokens':tt},'estimated_usd':round(estimated_usd,8),'reviews':clean},ensure_ascii=False))

if __name__=='__main__':main()
