#!/usr/bin/env python3
import json, os, sys, math, statistics, urllib.parse, urllib.request
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

# Theory-driven rules locked before this cutoff is evaluated.
LABEL='FRESH_BLIND_2026-08-01_12UTC'; CUTOFF='2026-08-01T12:00:00Z'
HOURS=96; LOOKBACK=48; STOP_FACTOR=.75

def fast_http(url, timeout=5):
    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'breakout-v17'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

def bybit_linear_symbols():
    try:
        d=fast_http(f'{v6.BYBIT_BASE}/v5/market/instruments-info?category=linear&limit=1000')
        return {x.get('symbol') for x in ((d.get('result') or {}).get('list') or []) if x.get('status')=='Trading'}
    except Exception:return set()

def deriv_context(sym,cut,supported):
    symbol=sym+'USDT';out={'available':False,'oiChange4h':None,'funding':None,'fundingZ':0.0,'signal':0.0}
    if symbol not in supported:return out
    try:
        u=f"{v6.BYBIT_BASE}/v5/market/open-interest?category=linear&symbol={urllib.parse.quote(symbol)}&intervalTime=1h&endTime={cut}&limit=8"
        d=fast_http(u);ls=((d.get('result') or {}).get('list') or []);a=sorted([(int(x['timestamp']),float(x['openInterest'])) for x in ls if float(x.get('openInterest') or 0)>0])
        if len(a)>=5:
            out['oiChange4h']=a[-1][1]/a[-5][1]-1;out['available']=True
    except Exception:pass
    try:
        u=f"{v6.BYBIT_BASE}/v5/market/funding/history?category=linear&symbol={urllib.parse.quote(symbol)}&endTime={cut}&limit=12"
        d=fast_http(u);ls=((d.get('result') or {}).get('list') or []);fs=sorted([(int(x['fundingRateTimestamp']),float(x['fundingRate'])) for x in ls])
        if fs:
            vals=[z[1] for z in fs];out['funding']=vals[-1];mu=statistics.mean(vals);sd=statistics.pstdev(vals) if len(vals)>1 else 0;out['fundingZ']=(vals[-1]-mu)/sd if sd>1e-12 else 0;out['available']=True
    except Exception:pass
    return out

def norm(x,s):return max(-2,min(2,x/s))
def features(sym,fr,su,bf):
    r6=v6.ret(fr['H1'],6);r24=v6.ret(fr['H1'],24);r72=v6.ret(fr['H4'],18);r7=v6.ret(fr['H4'],42);b24=v6.ret(bf['H1'],24);b7=v6.ret(bf['H4'],42);rs24=r24-b24;rs7=r7-b7
    st4=v6.structure(fr['H4']);st1=v6.structure(fr['H1']);cl=su['H4']['close'];e50=su['H4']['ema50'];e200=su['H4']['ema200'];eb=(1 if e50 and cl>e50 else -1 if e50 else 0)+(0.5 if e200 and cl>e200 else -0.5 if e200 else 0)
    return {'r6':r6,'r24':r24,'r72':r72,'r7d':r7,'rs24':rs24,'rs7d':rs7,'st4':st4,'st1':st1,'emaBias':eb}

def base_score(sym,f):
    s=.55*norm(f['r6'],.01)+.85*norm(f['r24'],.025)+1.1*norm(f['r72'],.05)+1.25*norm(f['r7d'],.08)+.8*f['st4']+.45*f['st1']+.35*f['emaBias']
    if sym!='BTC':s+=.3*norm(f['rs24'],.025)+.35*norm(f['rs7d'],.07)
    return s

def score_trade(sym,f,su,deriv,breadth):
    s=base_score(sym,f);price_dir=1 if (.7*norm(f['r6'],.01)+norm(f['r24'],.025))>=0 else -1;ds=0.0;oi=deriv.get('oiChange4h')
    if oi is not None:
        if oi>.01:ds+=.8*price_dir
        elif oi<-.01:ds-=.55*price_dir
    z=deriv.get('fundingZ') or 0
    if z>1.25:ds-=.35
    elif z<-1.25:ds+=.35
    deriv['signal']=ds;s+=ds
    # Breadth is only a soft market-regime prior.
    if breadth>=.67:s+=.45
    elif breadth<=.33:s-=.45
    # Anti-chase: stretched M15 entries are prone to liquidation/rebound.
    d=su['M15'].get('dist20ATR') or 0
    if d>1.55:s-=.55
    elif d<-1.55:s+=.55
    return s

def rr_for(score,deriv,model):
    aligned=deriv.get('available') and deriv.get('signal',0)!=0 and ((score>=0)==(deriv['signal']>0))
    if aligned and abs(score)>=4.5 and model['regime']=='trend':return 1.8
    if aligned and abs(score)>=2.75:return 1.7
    return 1.5

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])

def evaluate(side,en,sl,tp,cs):
    mfe=mae=0.0
    for i,x in enumerate(cs,1):
        if side=='BUY':mfe=max(mfe,x['high']-en);mae=max(mae,en-x['low']);hs=x['low']<=sl;ht=x['high']>=tp
        else:mfe=max(mfe,en-x['low']);mae=max(mae,x['high']-en);hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return {'result':'AMBIGUOUS','mfe':mfe,'mae':mae,'candles':i}
        if hs:return {'result':'SL','mfe':mfe,'mae':mae,'candles':i}
        if ht:return {'result':'TP','mfe':mfe,'mae':mae,'candles':i}
    return {'result':'UNRESOLVED','mfe':mfe,'mae':mae,'candles':len(cs)}

def main():
    cut=v6.iso_ms(CUTOFF);supported=bybit_linear_symbols();bs,bf,bm=v6.load_frames('BTC',cut);tmp=[];errs=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);_,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm);tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'en':fr['M5'][-1]['close'],'model':model,'f':features(sym,fr,su,bf),'deriv':deriv_context(sym,cut,supported)})
        except Exception as e:errs.append({'symbol':sym+'USDT','cutoff':CUTOFF,'error':str(e)})
    breadth=sum(r['f']['r24']>0 for r in tmp)/len(tmp) if tmp else .5;rows=[]
    for r in tmp:
        sym=r['sym'];sc=score_trade(sym,r['f'],r['su'],r['deriv'],breadth);side='BUY' if sc>=0 else 'SELL';en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(sym)['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk
        rr=rr_for(sc,r['deriv'],r['model']);tp=en+rr*risk if side=='BUY' else en-rr*risk;res=evaluate(side,en,sl,tp,future(r['source'],sym,cut))
        rows.append({'symbol':sym+'USDT','cutoff':CUTOFF,'source':r['source'],'blind':True,'decision':side,'score':round(sc,3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(breadth,3),'features':r['f'],'derivatives':r['deriv'],'model':r['model'],'outcome':res})
    rows+=errs;usable=[x for x in rows if x.get('decision')];resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    s={'label':LABEL,'cutoff':CUTOFF,'isTrueBlind':True,'requested':len(v6.COINS),'marketTrades':len(usable),'dataErrors':len(errs),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(breadth,3),'derivativesCoverage':round(sum(x.get('derivatives',{}).get('available',False) for x in usable)/len(usable),3) if usable else 0}
    with open('data/blind_backtest_v17.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V17 theory-driven true blind: multi-horizon momentum 6h/24h/72h/7d + H4/H1 structure + EMA + BTC relative strength + soft breadth + Bybit historical OI/funding context; OI rise confirms price direction, OI fall penalizes liquidation/covering continuation, extreme funding is crowding penalty; 48 M15 structural SL with .75 profile ATR floor; RR1.5 base, 1.7/1.8 only on derivative-confirmed high confidence; no WAIT/LIMIT.','summary':s,'tests':rows},f,indent=2)
    print(json.dumps(s,indent=2))
if __name__=='__main__':main()
