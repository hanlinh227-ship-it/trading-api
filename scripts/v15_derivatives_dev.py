#!/usr/bin/env python3
import json, os, sys, itertools, urllib.parse, statistics
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import v14_dev_search as v14

DEV=[('DEV_12AUG','2026-08-12T12:00:00Z'),('DEV_05AUG','2026-08-05T12:00:00Z')]
LOOKBACK=48;STOP_FACTOR=.75;HOURS=96
WEIGHTS=[0.4,0.8,1.2,1.6]
RR_MODES=['static15','confirm17','confirm19']

def deriv_stats(sym,cut):
    symbol=sym+'USDT';out={'available':False,'oiChange4h':None,'funding':None,'fundingZ':0.0,'signal':0.0}
    try:
        u=f"{v6.BYBIT_BASE}/v5/market/open-interest?category=linear&symbol={urllib.parse.quote(symbol)}&intervalTime=1h&endTime={cut}&limit=8"
        d=v6.http(u);lst=((d.get('result') or {}).get('list')) or []
        oi=sorted([(int(x['timestamp']),float(x['openInterest'])) for x in lst if float(x.get('openInterest') or 0)>0])
        if len(oi)>=5:
            latest=oi[-1][1];old=oi[-5][1];out['oiChange4h']=latest/old-1 if old else 0;out['available']=True
    except Exception:pass
    try:
        u=f"{v6.BYBIT_BASE}/v5/market/funding/history?category=linear&symbol={urllib.parse.quote(symbol)}&endTime={cut}&limit=12"
        d=v6.http(u);lst=((d.get('result') or {}).get('list')) or []
        fs=sorted([(int(x['fundingRateTimestamp']),float(x['fundingRate'])) for x in lst])
        if fs:
            vals=[x[1] for x in fs];latest=vals[-1];mu=statistics.mean(vals);sd=statistics.pstdev(vals) if len(vals)>1 else 0;out['funding']=latest;out['fundingZ']=(latest-mu)/sd if sd>1e-12 else 0;out['available']=True
    except Exception:pass
    return out

def enrich(row,cut):
    d=deriv_stats(row['sym'],cut);r6=row['feat']['r6'];oi=d['oiChange4h'];sig=0.0
    if oi is not None:
        # OI rising confirms the observed price direction; OI falling means covering/liquidation and weakens continuation.
        if oi>0.01:sig += 1.0 if r6>0 else -1.0 if r6<0 else 0
        elif oi<-0.01:sig += -0.55 if r6>0 else 0.55 if r6<0 else 0
    z=d.get('fundingZ') or 0
    # Extreme funding is a crowding penalty: positive funding leans against longs, negative against shorts.
    if z>1.25:sig-=0.45
    elif z<-1.25:sig+=0.45
    d['signal']=sig;row['deriv']=d;return row

def direction(row,w):
    adj=row['feat']['momScore']+w*row['deriv']['signal'];return ('BUY' if adj>=0 else 'SELL'),adj

def rr_for(row,adj,mode):
    if mode=='static15':return 1.5
    confirm=(row['deriv']['signal']!=0 and (adj>=0)==(row['deriv']['signal']>0) and abs(row['feat']['momScore'])>=2.5)
    return (1.7 if mode=='confirm17' else 1.9) if confirm else 1.5

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])

def outcome(side,en,sl,tp,cs):
    for x in cs:
        if side=='BUY':hs=x['low']<=sl;ht=x['high']>=tp
        else:hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return 'AMB'
        if hs:return 'SL'
        if ht:return 'TP'
    return 'UNR'

def load(cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);rows=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);base,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm);feat=v14.momentum_features(sym,fr,su,bf);r={'sym':sym,'source':source,'fr':fr,'su':su,'baseSide':base,'score':sc,'en':en,'model':model,'feat':feat};enrich(r,cut);r['future']=future(source,sym,cut);rows.append(r)
        except Exception:pass
    return rows

def eval_cfg(rows,w,mode):
    wins=loss=unr=0;total=0;rrs=[];avail=0
    for r in rows:
        side,adj=direction(r,w);rr=rr_for(r,adj,mode);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(r['sym'])['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
        z=outcome(side,en,sl,tp,r['future']);avail+=1 if r['deriv']['available'] else 0
        if z=='TP':wins+=1;total+=rr;rrs.append(rr)
        elif z=='SL':loss+=1;total-=1;rrs.append(rr)
        else:unr+=1
    n=wins+loss
    return {'wins':wins,'losses':loss,'unresolved':unr,'winRate':round(100*wins/n,2) if n else None,'avgRR':round(sum(rrs)/n,3) if n else None,'expectancyR':round(total/n,3) if n else None,'derivCoverage':round(avail/len(rows),3) if rows else 0}

def main():
    ds={name:load(cut) for name,cut in DEV};grid=[]
    for w,mode in itertools.product(WEIGHTS,RR_MODES):
        per={k:eval_cfg(v,w,mode) for k,v in ds.items()};minwr=min(x['winRate'] for x in per.values());minexp=min(x['expectancyR'] for x in per.values());avgrr=sum(x['avgRR'] for x in per.values())/2;avgwr=sum(x['winRate'] for x in per.values())/2;avgexp=sum(x['expectancyR'] for x in per.values())/2
        robust=minwr+12*minexp+4*(avgrr-1.5)+.1*avgwr+3*avgexp
        grid.append({'derivWeight':w,'rrMode':mode,'perSample':per,'minWinRate':round(minwr,2),'minExpectancyR':round(minexp,3),'avgRR':round(avgrr,3),'avgWinRate':round(avgwr,2),'avgExpectancyR':round(avgexp,3),'robustScore':round(robust,3)})
    top=sorted([x for x in grid if x['minExpectancyR']>0 and x['minWinRate']>=40],key=lambda x:(x['robustScore'],x['avgRR']),reverse=True)
    with open('data/v15_derivatives_dev.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V15 development: V14 momentum+structure plus Bybit 4h OI change and funding crowding; derivatives secondary only; 48 M15 structural SL; RR1.5 or 1.7/1.9 only when momentum+derivatives confirm.','top':top,'grid':grid},f,indent=2)
    print(json.dumps({'top':top[:10]},indent=2))
if __name__=='__main__':main()
