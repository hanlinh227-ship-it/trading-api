#!/usr/bin/env python3
"""Offline development regime router. Decision uses 00UTC observable state only; one trade/day; no CUT."""
import json,math
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h
from scripts.offline_crypto_v28_separate import PROFILE
from scripts.offline_nocut_geometry_core import simulate,stats

OUT='data/offline_crypto_h1_regime_router_v70.json';START='2026-05-01';END='2026-07-30';EXPECTED=91;TARGET=80.0
FAILED='BTC ETH SHIB TRX AAVE ADA ARB ATOM AVAX BCH BONK CRV DOGE FLOKI HBAR JUP KAITO LDO LINK LTC MOODENG NEAR OP ORDI PEPE PNUT POL POPCAT S STX SUI TAO TRUMP WIF ASTER GRASS VIRTUAL'.split()
FAMS=('BTCALIGN','RELATIVE','H1TREND','H4TREND','D1TREND','MOMENTUM','MEANREV','BREADTH','HYBRID')
HOURS=(0,4,8,12,16,20);OFFS=(.50,.75,1.00,1.25);EXPS=(2,4,6);RFS=(.50,.75,1.00,1.25);HOLDS=(8,12,18)
FEATURES=('dev','absdev','mom','absmom','rel24','btc24','breadth','breadthDist','adx','rsi','h1','h4','d1')
MIN_LEAF=10;TOPK=30

def feat(m,row):
 return {'dev':m['dev'],'absdev':abs(m['dev']),'mom':m['mom'],'absmom':abs(m['mom']),'rel24':m['rel24'],'btc24':m['btc24'],'breadth':m['breadth'],'breadthDist':abs(m['breadth']-.5),'adx':row.get('adx') or 0,'rsi':row.get('rsi') or 50,'h1':m['h1'],'h4':m['h4'],'d1':m['d1']}
def thresholds(days,f):
 z=sorted(x['f'][f] for x in days);out=[]
 for q in (.2,.35,.5,.65,.8):
  v=z[min(len(z)-1,max(0,int(q*(len(z)-1))))]
  if not out or v!=out[-1]:out.append(v)
 return out

def main():
 doc=json.load(open(h.SNAP,encoding='utf-8'));data={s:h.enrich(doc['data'][s]) for s in h.ALL};mp=h.maps(data);dm=defaultdict(lambda:defaultdict(dict));dec=defaultdict(dict);times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<START or d>END:continue
  p=h.context(mp,t)
  if not p:continue
  elig,reg=p
  for sym,q in elig.items():
   i,row=q;m=h.meta(row,reg);dm[sym][d][t.hour]=(i,m)
   if t.hour==0:dec[sym][d]={'f':feat(m,row)}
 results={}
 for sym in FAILED:
  days=[]
  for d in sorted(dec[sym]):
   if all(hr in dm[sym][d] for hr in HOURS):days.append({'day':d,'f':dec[sym][d]['f']})
  if len(days)!=EXPECTED:results[sym]={'status':'FAIL','reason':'incomplete H1','days':len(days)};print('NO_FULL',sym,len(days),flush=True);continue
  # build candidate actions and outcome vectors
  acts=[];cache={}
  for fam in FAMS:
   for hr in HOURS:
    for off in OFFS:
     for ex in EXPS:
      for rf in RFS:
       for hold in HOLDS:
        cfg=('DUAL_FADE',off,ex,1.0,rf,hold);vec=[];rs=[]
        for x in days:
         i,m=dm[sym][x['day']][hr];sd=h.side(fam,m);k=(i,sd,cfg)
         if k not in cache:cache[k]=simulate(data[sym],i,sd,cfg)
         o=cache[k];vec.append(1 if o[0]=='TP' else 0);rs.append(o[1])
        acts.append({'fam':fam,'hr':hr,'cfg':cfg,'v':vec,'r':rs,'wins':sum(vec)})
  acts=sorted(acts,key=lambda a:(a['wins'],sum(a['r'])),reverse=True)[:TOPK]
  n=len(days);allidx=list(range(n))
  def best_action(idx):
   if not idx:return None,-999
   best=None;bw=-1
   for ai,a in enumerate(acts):
    w=sum(a['v'][j] for j in idx)
    if w>bw:best=ai;bw=w
   return best,bw
  def best_subpolicy(idx):
   ai,w=best_action(idx);best={'kind':'leaf','action':ai,'wins':w};
   if len(idx)<2*MIN_LEAF:return best
   for f in FEATURES:
    vals=[days[j]['f'][f] for j in idx];sv=sorted(vals)
    qs=sorted(set(sv[min(len(sv)-1,max(0,int(q*(len(sv)-1))))] for q in (.3,.5,.7)))
    for th in qs:
     lo=[j for j in idx if days[j]['f'][f]<=th];hi=[j for j in idx if days[j]['f'][f]>th]
     if len(lo)<MIN_LEAF or len(hi)<MIN_LEAF:continue
     a1,w1=best_action(lo);a2,w2=best_action(hi)
     if w1+w2>best['wins']:best={'kind':'split','feature':f,'threshold':th,'loAction':a1,'hiAction':a2,'wins':w1+w2}
   return best
  root=best_subpolicy(allidx)
  # depth2: root candidate splits, each branch may have one extra split
  bestpol=root
  for f in FEATURES:
   for th in thresholds(days,f):
    lo=[j for j in allidx if days[j]['f'][f]<=th];hi=[j for j in allidx if days[j]['f'][f]>th]
    if len(lo)<2*MIN_LEAF or len(hi)<2*MIN_LEAF:continue
    lp=best_subpolicy(lo);hp=best_subpolicy(hi);w=lp['wins']+hp['wins']
    if w>bestpol['wins']:bestpol={'kind':'root','feature':f,'threshold':th,'lo':lp,'hi':hp,'wins':w}
  def pick(pol,j):
   if pol['kind']=='leaf':return pol['action']
   if pol['kind']=='split':return pol['loAction'] if days[j]['f'][pol['feature']]<=pol['threshold'] else pol['hiAction']
   return pick(pol['lo'],j) if days[j]['f'][pol['feature']]<=pol['threshold'] else pick(pol['hi'],j)
  chosen=[];z=[]
  for j in allidx:
   ai=pick(bestpol,j);chosen.append(ai);a=acts[ai];z.append(('TP',1.0,0) if a['v'][j] else (('SL',-1.0,0) if a['r'][j]<0 else ('TIMEOUT',0.0,0)))
  s=stats(z,EXPECTED);ok=s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0
  used=sorted(set(chosen));actionDefs=[]
  for ai in used:
   a=acts[ai];c=a['cfg'];actionDefs.append({'id':ai,'family':a['fam'],'signalHourUTC':a['hr'],'entryMode':'DUAL_FADE','offsetATR':c[1],'expiryH':c[2],'rr':1.0,'riskATR':c[4],'maxHoldH':c[5],'staticWins':a['wins']})
  results[sym]={'status':'PASS' if ok else 'FAIL','profile':PROFILE.get(sym,'OTHER'),'decisionHourUTC':0,'router':bestpol,'actions':actionDefs,'development':s};print('PASS' if ok else 'FAIL',sym,'wins',bestpol['wins'],s,'actions',len(used),flush=True)
 passed=[s for s in FAILED if results[s]['status']=='PASS'];failed=[s for s in FAILED if results[s]['status']!='PASS'];out={'version':'CRYPTO_H1_REGIME_ROUTER_V70','scope':'V69 failures; 00UTC observable shallow regime tree routes among top static intraday actions; exposed May-Jul development','definition':{'cutUsed':False,'noTradeAllowed':False,'tradesPerDay':1,'rr':1.0,'decisionUsesFuture':False,'maxRouterDepth':2,'minLeafDays':MIN_LEAF},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allTargetedPass':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','failed','allTargetedPass')},indent=2),flush=True)
if __name__=='__main__':main()
