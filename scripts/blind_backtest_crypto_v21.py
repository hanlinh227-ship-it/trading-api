#!/usr/bin/env python3
import json, math, os, statistics, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core

# Locked theory-driven per-coin regime classifier; both dates untouched before this file.
CUTOFFS=[('BLIND_JUL16','2026-07-16T12:00:00Z'),('BLIND_JUL14','2026-07-14T12:00:00Z')]
HOURS=96;LOOKBACK=48;STOP_FACTOR=.75

def corr(a,b):
    if len(a)<3:return 0.0
    ma=statistics.mean(a);mb=statistics.mean(b);sa=sum((x-ma)**2 for x in a);sb=sum((y-mb)**2 for y in b)
    if sa<=0 or sb<=0:return 0.0
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(sa*sb)
def serial_features(fr):
    c=fr['H1'];cl=[x['close'] for x in c[-100:]];rets=[cl[i]/cl[i-1]-1 for i in range(1,len(cl)) if cl[i-1]]
    ac1=corr(rets[:-1],rets[1:]) if len(rets)>3 else 0;ac4=corr(rets[:-4],rets[4:]) if len(rets)>8 else 0
    x=cl[-25:] if len(cl)>=25 else cl;path=sum(abs(x[i]-x[i-1]) for i in range(1,len(x)));eff=abs(x[-1]-x[0])/path if path else 0
    return {'acf1':ac1,'acf4':ac4,'efficiency24h':eff}

def norm(x,s):return max(-2,min(2,x/s))
def momentum_score(f):return .8*norm(f['r6'],.01)+1.15*norm(f['r24'],.025)+1.3*norm(f['r72'],.05)+.65*f['st4']+.35*f['st1']+.3*f['emaBias']
def classify(su,serial):
    adx=su['H4'].get('adx14') or 0;eff=serial['efficiency24h'];ac=(serial['acf1']+serial['acf4'])/2
    if adx>=20 and eff>=.28 and ac>=-.08:return 'persistent'
    if adx<18 and (eff<=.20 or ac<=-.10):return 'mean_reverting'
    return 'hybrid'
def decide(sym,f,su,model,serial,breadth):
    state=classify(su,serial);ms=momentum_score(f);pos=model.get('rangePositionH1',.5);rsi=su['M15'].get('rsi14') or 50;dist=su['M15'].get('dist20ATR') or 0
    if state=='persistent':score=ms
    elif state=='mean_reverting':
        # Position dominates only in an actually choppy/reverting coin.
        mr=(.5-pos)*5.0 + (50-rsi)/18.0 - .35*dist
        score=mr if abs(mr)>=.35 else -0.55*ms
    else:
        # Hybrid: momentum core, but fade only when the coin is both stretched and at a range edge.
        score=.72*ms+.28*(model.get('htfScore',0)/3.0)
        if pos>=.86 and (dist>=1.25 or rsi>=68):score-=1.4
        elif pos<=.14 and (dist<=-1.25 or rsi<=32):score+=1.4
    if sym!='BTC':
        score += .25*norm(f['rs24'],.025)+.20*norm(f['rs7d'],.07)
    # breadth is only a tiny prior, not an override.
    if breadth>=.75:score+=.25
    elif breadth<=.25:score-=.25
    side='BUY' if score>=0 else 'SELL';sgn=1 if side=='BUY' else -1;align=sum(x*sgn>0 for x in (f['r6'],f['r24'],f['r72'],f['r7d']))
    if state=='persistent' and align>=3 and abs(score)>=2.5:rr=1.85
    elif state=='persistent':rr=1.70
    elif state=='hybrid' and abs(score)>=2.5:rr=1.70
    elif state=='hybrid':rr=1.60
    else:rr=1.50
    return side,score,rr,{'state':state,'momentumScore':ms,'serial':serial,'rangePosition':pos,'m15RSI':rsi,'m15DistATR':dist,'alignment':align}

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])
def evaluate(side,en,sl,tp,cs):
    for i,x in enumerate(cs,1):
        if side=='BUY':hs=x['low']<=sl;ht=x['high']>=tp
        else:hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return {'result':'AMBIGUOUS','candles':i}
        if hs:return {'result':'SL','candles':i}
        if ht:return {'result':'TP','candles':i}
    return {'result':'UNRESOLVED','candles':len(cs)}
def run(label,cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);tmp=[];errs=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);_,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm);f=core.features(sym,fr,su,bf);tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'model':model,'f':f,'serial':serial_features(fr),'en':fr['M5'][-1]['close']})
        except Exception as e:errs.append({'symbol':sym+'USDT','cutoff':cutoff,'error':str(e)})
    breadth=sum(r['f']['r24']>0 for r in tmp)/len(tmp) if tmp else .5;rows=[]
    for r in tmp:
        sym=r['sym'];side,score,rr,meta=decide(sym,r['f'],r['su'],r['model'],r['serial'],breadth);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(sym)['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk
        tp=en+rr*risk if side=='BUY' else en-rr*risk;res=evaluate(side,en,sl,tp,future(r['source'],sym,cut));rows.append({'symbol':sym+'USDT','cutoff':cutoff,'blind':True,'decision':side,'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(breadth,3),'analysis':meta,'model':r['model'],'features':r['f'],'outcome':res})
    rows+=errs;usable=[x for x in rows if x.get('decision')];resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    from collections import Counter
    states=Counter(x['analysis']['state'] for x in usable)
    s={'label':label,'cutoff':cutoff,'isTrueBlind':True,'marketTrades':len(usable),'dataErrors':len(errs),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(breadth,3),'states':dict(states)}
    return {'summary':s,'tests':rows}
def main():
    samples={n:run(n,c) for n,c in CUTOFFS};p={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V21 locked per-coin serial-regime forced-market: each coin classified from pre-cutoff H1 return autocorrelation + 24h efficiency + H4 ADX into persistent/hybrid/mean-reverting; persistent uses 6h/24h/72h momentum+structure, mean-reverting uses H1 range position+M15 RSI/distance, hybrid blends momentum and HTF with edge exhaustion; BTC relative strength/breadth soft only; 48 M15 structural SL + .75 profile ATR floor; RR1.5-1.85 by state/confidence; no WAIT/LIMIT.','samples':samples}
    with open('data/blind_backtest_v21.json','w') as f:json.dump(p,f,indent=2)
    print(json.dumps({k:v['summary'] for k,v in samples.items()},indent=2))
if __name__=='__main__':main()
