#!/usr/bin/env python3
"""Offline H1 development optimizer for HBAR/TAO. One trade/day, no CUT, RR1."""
import json,heapq
from collections import defaultdict
from pathlib import Path
import scripts.offline_crypto_h1_daily_each_symbol_v47 as h
from scripts.offline_nocut_geometry_core import simulate,stats

OUT='data/offline_crypto_h1_special_v71.json';START='2026-05-01';END='2026-07-30';EXPECTED=91;TARGET=80.0
SPECIAL=('HBAR','TAO');FAMS=('BTCALIGN','RELATIVE','H1TREND','H4TREND','MOMENTUM','MEANREV','HYBRID');HOURS=range(24)
FEATURES=('dev','absdev','mom','absmom','rel24','btc24','breadth','breadthDist','adx','rsi','ret24','ret72','h1','h4','d1','weekday')
MIN_LEAF=7;MAX_DEPTH=3

def configs():
 z=[]
 for off in (.50,.75,1.00,1.25):
  for ex in (2,5):
   for rf in (.50,.75,1.00):
    for hold in (8,12,18,24):z.append(('DUAL_FADE',off,ex,1.0,rf,hold))
 for lb in (3,6,12):
  for ex in (2,5):
   for rf in (.50,.75,1.00):
    for hold in (12,18):z.append(('DUAL_BRK',lb,ex,1.0,rf,hold))
 for mode,offs in (('PB',(.35,.70)),('BRK',(.20,.45))):
  for off in offs:
   for ex in (1,3):
    for rf in (.50,.75,1.00):
     for hold in (12,18):z.append((mode,off,ex,1.0,rf,hold))
 return z

def fpack(m,row,d):
 return {'dev':m['dev'],'absdev':abs(m['dev']),'mom':m['mom'],'absmom':abs(m['mom']),'rel24':m['rel24'],'btc24':m['btc24'],'breadth':m['breadth'],'breadthDist':abs(m['breadth']-.5),'adx':row.get('adx') or 0,'rsi':row.get('rsi') or 50,'ret24':row.get('ret24') or 0,'ret72':row.get('ret72') or 0,'h1':m['h1'],'h4':m['h4'],'d1':m['d1'],'weekday':d}
def qs(vals):
 s=sorted(vals);return sorted(set(s[min(len(s)-1,max(0,int(q*(len(s)-1))))] for q in (.2,.35,.5,.65,.8)))

def main():
 base=json.load(open(h.SNAP,encoding='utf-8'));sp=json.load(open('data/provider_snapshots/tao_ton_ip_h1_jan_jul_2026_binance.json',encoding='utf-8'))
 data={s:h.enrich(base['data'][s]) for s in h.ALL};data['TAO']=h.enrich(sp['data']['TAO']);mp=h.maps(data);dm=defaultdict(lambda:defaultdict(dict));dec=defaultdict(dict);times=sorted(set().union(*(set(m) for m in mp.values())))
 for t in times:
  d=t.date().isoformat()
  if d<START or d>END:continue
  p=h.context(mp,t)
  if not p:continue
  elig,reg=p
  for sym in SPECIAL:
   q=elig.get(sym)
   if not q:continue
   i,row=q;m=h.meta(row,reg);dm[sym][d][t.hour]=(i,m)
   if t.hour==0:dec[sym][d]={'f':fpack(m,row,t.weekday())}
 cs=configs();print('CONFIGS',len(cs),flush=True);results={}
 for sym in SPECIAL:
  days=[{'day':d,'f':dec[sym][d]['f']} for d in sorted(dec[sym]) if len(dm[sym][d])==24]
  if len(days)!=EXPECTED:results[sym]={'status':'FAIL','reason':'incomplete','days':len(days)};print('NO_FULL',sym,len(days),flush=True);continue
  cache={};acts=[]
  for fam in FAMS:
   for hr in HOURS:
    local=[]
    for cfg in cs:
     v=[];rs=[]
     for x in days:
      i,m=dm[sym][x['day']][hr];sd=h.side(fam,m);k=(i,sd,cfg)
      if k not in cache:cache[k]=simulate(data[sym],i,sd,cfg)
      o=cache[k];v.append(1 if o[0]=='TP' else 0);rs.append(o[1])
     w=sum(v);score=w+0.01*sum(rs);item=(score,w,fam,hr,cfg,v,rs)
     local.append(item)
    local.sort(key=lambda x:(x[0],x[1]),reverse=True);acts.extend(local[:4])
  # Diverse compact candidate set: top overall + best per hour/family/mode.
  acts.sort(key=lambda x:(x[1],x[0]),reverse=True);chosen=acts[:50];seen={(a[2],a[3],a[4][0]) for a in chosen}
  bestmap={}
  for a in acts:
   keys=[('h',a[3]),('f',a[2]),('m',a[4][0]),('hf',a[3],a[2]),('hm',a[3],a[4][0])]
   for k in keys:
    if k not in bestmap:bestmap[k]=a
  chosen.extend(bestmap.values());uniq=[];ids=set()
  for a in chosen:
   k=(a[2],a[3],a[4])
   if k not in ids:ids.add(k);uniq.append(a)
  acts=uniq;print(sym,'CANDIDATES',len(acts),'BEST_STATIC',acts[0][1],flush=True)
  allidx=list(range(EXPECTED))
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
     # one-step gain estimate, then recursively build only promising splits
     _,wl=bestact(lo);_,wh=bestact(hi)
     if wl+wh<best['wins']:continue
     lp=build(lo,depth+1);hp=build(hi,depth+1);tw=lp['wins']+hp['wins']
     if tw>best['wins']:best={'kind':'split','feature':f,'threshold':th,'lo':lp,'hi':hp,'wins':tw}
   return best
  pol=build(allidx,0)
  def pick(p,j):
   if p['kind']=='leaf':return p['action']
   return pick(p['lo'],j) if days[j]['f'][p['feature']]<=p['threshold'] else pick(p['hi'],j)
  z=[];used=set()
  for j in allidx:
   ai=pick(pol,j);used.add(ai);a=acts[ai];z.append(('TP',1.0,0) if a[5][j] else (('SL',-1.0,0) if a[6][j]<0 else ('TIMEOUT',0.0,0)))
  s=stats(z,EXPECTED);ok=s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0;defs=[]
  for ai in sorted(used):
   a=acts[ai];c=a[4];defs.append({'id':ai,'family':a[2],'signalHourUTC':a[3],'entryMode':c[0],'param':c[1],'expiryH':c[2],'rr':1.0,'riskATR':c[4],'maxHoldH':c[5],'staticWins':a[1]})
  results[sym]={'status':'PASS' if ok else 'FAIL','decisionHourUTC':0,'router':pol,'actions':defs,'development':s};print('PASS' if ok else 'FAIL',sym,s,'ACTIONS',len(used),flush=True)
 out={'version':'CRYPTO_H1_SPECIAL_V71','scope':'HBAR and full-history TAO expanded action/regime development','definition':{'cutUsed':False,'noTradeAllowed':False,'tradesPerDay':1,'rr':1.0,'decisionUsesFuture':False,'maxRouterDepth':MAX_DEPTH,'minLeafDays':MIN_LEAF},'allPassed':all(results.get(s,{}).get('status')=='PASS' for s in SPECIAL),'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({'allPassed':out['allPassed'],'status':{s:results[s]['status'] for s in results}},indent=2),flush=True)
if __name__=='__main__':main()
