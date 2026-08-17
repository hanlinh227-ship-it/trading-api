#!/usr/bin/env python3
import json, os, sys, itertools, math
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
DEV=[('DEV_12AUG','2026-08-12T12:00:00Z'),('DEV_05AUG','2026-08-05T12:00:00Z')]
POLICIES=['v6_base','tsmom','tsmom_structure','breadth_momentum','adaptive_mom_reversal']
LOOKBACKS=[32,48]
STOP_FACTORS=[0.75,0.95]
RRS=[1.5,1.7,1.9]
HOURS=96

def sgn(x,eps=1e-9): return 1 if x>eps else -1 if x<-eps else 0

def momentum_features(sym,fr,su,btc_fr):
    r6=v6.ret(fr['H1'],6);r24=v6.ret(fr['H1'],24);r72=v6.ret(fr['H4'],18);br24=v6.ret(btc_fr['H1'],24);br72=v6.ret(btc_fr['H4'],18);rs24=r24-br24;rs72=r72-br72;st4=v6.structure(fr['H4']);st1=v6.structure(fr['H1']);ema50=su['H4']['ema50'];ema200=su['H4']['ema200'];cl=su['H4']['close'];ema_bias=(1 if ema50 and cl>ema50 else -1 if ema50 else 0)+(0.5 if ema200 and cl>ema200 else -0.5 if ema200 else 0)
    def norm(r,scale):return max(-2,min(2,r/scale))
    score=0.9*norm(r6,.01)+1.2*norm(r24,.025)+1.4*norm(r72,.05)+0.9*st4+0.5*st1+0.45*ema_bias
    if sym!='BTC':score+=0.45*norm(rs24,.025)+0.35*norm(rs72,.05)
    return {'r6':r6,'r24':r24,'r72':r72,'rs24':rs24,'rs72':rs72,'st4':st4,'st1':st1,'emaBias':ema_bias,'momScore':score}

def choose_side(policy,row,breadth):
    base=row['baseSide'];f=row['feat'];su=row['su'];m=row['model'];score=f['momScore'];pos=m.get('rangePositionH1',.5)
    if policy=='v6_base':return base
    if policy=='tsmom':
        raw=1.0*sgn(f['r6'])+1.4*sgn(f['r24'])+1.7*sgn(f['r72']);return 'BUY' if raw>=0 else 'SELL'
    if policy=='tsmom_structure':return 'BUY' if score>=0 else 'SELL'
    if policy=='breadth_momentum':
        adj=score + (1.2 if breadth>=.65 else -1.2 if breadth<=.35 else 0);return 'BUY' if adj>=0 else 'SELL'
    rg=m['regime'];h4=su['H4'];h1=su['H1'];low_adx=(h4.get('adx14') or 99)<16 and (h1.get('adx14') or 99)<16
    if rg=='range' and low_adx and pos>=.85:return 'SELL'
    if rg=='range' and low_adx and pos<=.15:return 'BUY'
    adj=score + (0.8 if breadth>=.67 else -0.8 if breadth<=.33 else 0);return 'BUY' if adj>=0 else 'SELL'

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
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);base,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm);feat=momentum_features(sym,fr,su,bf);rows.append({'sym':sym,'source':source,'fr':fr,'su':su,'baseSide':base,'score':sc,'en':en,'model':model,'feat':feat,'future':future(source,sym,cut)})
        except Exception:pass
    breadth=sum(r['feat']['r24']>0 for r in rows)/len(rows) if rows else .5;return rows,breadth

def eval_cfg(rows,breadth,policy,lb,sf,rr):
    w=l=u=0
    for r in rows:
        side=choose_side(policy,r,breadth);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(r['sym'])['stopBase'];recent=r['fr']['M15'][-lb:];floor=sf*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
        z=outcome(side,en,sl,tp,r['future'])
        if z=='TP':w+=1
        elif z=='SL':l+=1
        else:u+=1
    n=w+l;wr=100*w/n if n else 0;exp=(w*rr-l)/n if n else -99;return {'wins':w,'losses':l,'unresolved':u,'winRate':round(wr,2),'expectancyR':round(exp,3)}

def main():
    ds={}
    for name,cut in DEV:
        rows,breadth=load(cut);ds[name]={'rows':rows,'breadth':breadth}
    grid=[]
    for p,lb,sf,rr in itertools.product(POLICIES,LOOKBACKS,STOP_FACTORS,RRS):
        per={k:eval_cfg(v['rows'],v['breadth'],p,lb,sf,rr) for k,v in ds.items()};minwr=min(x['winRate'] for x in per.values());minexp=min(x['expectancyR'] for x in per.values());avgwr=sum(x['winRate'] for x in per.values())/2;avgexp=sum(x['expectancyR'] for x in per.values())/2;robust=minwr+10*minexp+2.5*(rr-1.5)+.12*avgwr+3*avgexp
        grid.append({'policy':p,'lookback':lb,'stopFactor':sf,'rr':rr,'breadth':{k:round(v['breadth'],3) for k,v in ds.items()},'perSample':per,'minWinRate':round(minwr,2),'minExpectancyR':round(minexp,3),'avgWinRate':round(avgwr,2),'avgExpectancyR':round(avgexp,3),'robustScore':round(robust,3)})
    feasible=[x for x in grid if x['minExpectancyR']>0 and x['minWinRate']>=40 and x['rr']>=1.5];top=sorted(feasible,key=lambda x:(x['robustScore'],x['minWinRate'],x['rr']),reverse=True)[:20]
    with open('data/v14_dev_search.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V14 development search: short-horizon time-series momentum, H4/H1 structure, BTC-relative strength, breadth, reversal only in low-ADX extreme ranges','dev':DEV,'top':top,'grid':grid},f,indent=2)
    print(json.dumps({'top':top[:10]},indent=2))
if __name__=='__main__':main()
# trigger-v2