#!/usr/bin/env python3
"""Offline 4H development optimizer for TON/IP. One trade/day, no CUT, RR1."""
import json
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_precision_evolver_v36 as v
from scripts.offline_crypto_v28_separate import PROFILE
from scripts.offline_nocut_geometry_core import simulate,stats

OUT='data/offline_crypto_4h_ton_ip_v72.json';START='2026-05-01';END='2026-07-30';EXPECTED=91;TARGET=80.0
SPECIAL=('TON','IP');HOURS=(0,4,8,12,16,20)
FAMS=('BTCALIGN','RELATIVE','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID','CONTRA24')
FEATURES=('dev','absdev','mom','absmom','rel24','btc24','breadth','breadthDist','adx','rsi','ret24','ret72','h4','d1','weekday')
MIN_LEAF=7;MAX_DEPTH=3

def side(f,m):
    x={'BTCALIGN':m['btc24'],'RELATIVE':m['rel24'],'H4TREND':m['h4'],'D1TREND':m['d1'],'MOMENTUM':m['mom'],
       'MEANREV':-m['dev'],'BREADTH':m['breadth']-.5,'HYBRID':.6*m['btc24']+.8*m['rel24']+.35*m['h4']+.25*m['d1']-.35*m['dev'],
       'CONTRA24':-m['rel24']}[f]
    return 1 if x>=0 else -1

def configs():
    z=[]
    for off in (.35,.50,.65,.80,1.00,1.20):
      for ex in (1,2):
       for rf in (.35,.50,.65,.80,1.00,1.20):
        for hold in (2,3,4,5,6):z.append(('DUAL_FADE',off,ex,1.0,rf,hold))
    for lb in (2,3,6):
      for ex in (1,2):
       for rf in (.50,.75,1.00):
        for hold in (3,4,6):z.append(('DUAL_BRK',lb,ex,1.0,rf,hold))
    for mode,offs in (('PB',(.25,.50,.75)),('BRK',(.15,.30,.50))):
      for off in offs:
       for ex in (1,2):
        for rf in (.50,.75,1.00):
         for hold in (3,4,6):z.append((mode,off,ex,1.0,rf,hold))
    return z

def fpack(m,row,weekday):
    return {'dev':m['dev'],'absdev':abs(m['dev']),'mom':m['mom'],'absmom':abs(m['mom']),'rel24':m['rel24'],'btc24':m['btc24'],
            'breadth':m['breadth'],'breadthDist':abs(m['breadth']-.5),'adx':row.get('adx') or 0,'rsi':row.get('rsi') or 50,
            'ret24':row.get('ret24') or 0,'ret72':row.get('ret72') or 0,'h4':m['h4'],'d1':m['d1'],'weekday':weekday}
def qs(vals):
    s=sorted(vals);return sorted(set(s[min(len(s)-1,max(0,int(q*(len(s)-1))))] for q in (.2,.35,.5,.65,.8)))

def main():
    doc=json.load(open(v.SNAP,encoding='utf-8'));data={s:v.enrich(doc['data'][s]) for s in v.SYMBOLS};mp=v.maps(data)
    dm=defaultdict(lambda:defaultdict(dict));dec=defaultdict(dict);times=sorted(set().union(*(set(m) for m in mp.values())))
    for t in times:
      d=t.date().isoformat()
      if d<START or d>END:continue
      p=v.regime_at(mp,t)
      if not p:continue
      elig,reg=p
      for sym in SPECIAL:
        q=elig.get(sym)
        if not q:continue
        i,row=q;_,m=v.features(sym,row,reg,1);dm[sym][d][t.hour]=(i,m)
        if t.hour==0:dec[sym][d]={'f':fpack(m,row,t.weekday())}
    cs=configs();print('CONFIGS',len(cs),flush=True);results={}
    for sym in SPECIAL:
      days=[{'day':d,'f':dec[sym][d]['f']} for d in sorted(dec[sym]) if all(hr in dm[sym][d] for hr in HOURS)]
      if len(days)!=EXPECTED:results[sym]={'status':'FAIL','reason':'incomplete 4H','days':len(days)};print('NO_FULL',sym,len(days),flush=True);continue
      cache={};acts=[]
      for fam in FAMS:
       for hr in HOURS:
        local=[]
        for cfg in cs:
          wins=[];rs=[]
          for x in days:
            i,m=dm[sym][x['day']][hr];sd=side(fam,m);k=(i,sd,cfg)
            if k not in cache:cache[k]=simulate(data[sym],i,sd,cfg)
            o=cache[k];wins.append(1 if o[0]=='TP' else 0);rs.append(o[1])
          w=sum(wins);local.append((w+0.01*sum(rs),w,fam,hr,cfg,wins,rs))
        local.sort(key=lambda a:(a[0],a[1]),reverse=True);acts.extend(local[:6])
      acts.sort(key=lambda a:(a[1],a[0]),reverse=True);pool=acts[:70];bestmap={}
      for a in acts:
        for k in (('h',a[3]),('f',a[2]),('m',a[4][0]),('hf',a[3],a[2]),('hm',a[3],a[4][0])):
          if k not in bestmap:bestmap[k]=a
      pool.extend(bestmap.values());uniq=[];seen=set()
      for a in pool:
        k=(a[2],a[3],a[4])
        if k not in seen:seen.add(k);uniq.append(a)
      acts=uniq;print(sym,'CANDIDATES',len(acts),'BEST_STATIC',acts[0][1],flush=True)
      idxall=list(range(EXPECTED))
      def bestact(idx):
        bi=0;bw=-1
        for ai,a in enumerate(acts):
          w=sum(a[5][j] for j in idx)
          if w>bw:bw=w;bi=ai
        return bi,bw
      def build(idx,depth):
        ai,w=bestact(idx);best={'kind':'leaf','action':ai,'wins':w}
        if depth>=MAX_DEPTH or len(idx)<2*MIN_LEAF:return best
        for f in FEATURES:
          for th in qs([days[j]['f'][f] for j in idx]):
            lo=[j for j in idx if days[j]['f'][f]<=th];hi=[j for j in idx if days[j]['f'][f]>th]
            if len(lo)<MIN_LEAF or len(hi)<MIN_LEAF:continue
            _,wl=bestact(lo);_,wh=bestact(hi)
            if wl+wh<best['wins']:continue
            lp=build(lo,depth+1);hp=build(hi,depth+1);tw=lp['wins']+hp['wins']
            if tw>best['wins']:best={'kind':'split','feature':f,'threshold':th,'lo':lp,'hi':hp,'wins':tw}
        return best
      pol=build(idxall,0)
      def pick(p,j):
        if p['kind']=='leaf':return p['action']
        return pick(p['lo'],j) if days[j]['f'][p['feature']]<=p['threshold'] else pick(p['hi'],j)
      z=[];used=set()
      for j in idxall:
        ai=pick(pol,j);used.add(ai);a=acts[ai];z.append(('TP',1.0,0) if a[5][j] else (('SL',-1.0,0) if a[6][j]<0 else ('TIMEOUT',0.0,0)))
      s=stats(z,EXPECTED);ok=s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0;defs=[]
      for ai in sorted(used):
        a=acts[ai];c=a[4];defs.append({'id':ai,'family':a[2],'signalHourUTC':a[3],'entryMode':c[0],'param':c[1],'expiryBars4H':c[2],'rr':1.0,'riskATR':c[4],'maxHoldBars4H':c[5],'staticWins':a[1]})
      results[sym]={'status':'PASS' if ok else 'FAIL','profile':PROFILE.get(sym,'OTHER'),'decisionHourUTC':0,'router':pol,'actions':defs,'development':s};print('PASS' if ok else 'FAIL',sym,s,'ACTIONS',len(used),flush=True)
    out={'version':'CRYPTO_4H_TON_IP_V72','scope':'TON/IP 4H May1-Jul30 exposed development; individual observable regime router','definition':{'cutUsed':False,'noTradeAllowed':False,'tradesPerDay':1,'rr':1.0,'decisionUsesFuture':False,'maxRouterDepth':MAX_DEPTH,'minLeafDays':MIN_LEAF},'allPassed':all(results.get(s,{}).get('status')=='PASS' for s in SPECIAL),'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({'allPassed':out['allPassed'],'status':{s:results.get(s,{}).get('status') for s in SPECIAL}},indent=2),flush=True)
if __name__=='__main__':main()
