#!/usr/bin/env python3
import json,os,re,statistics,itertools
FILES=['data/blind_backtest_v24_validation.json','data/blind_backtest_v26.json','data/blind_backtest_v27_final.json','data/final_market_vs_limit_blind.json']
DR=re.compile(r'20\d\d-\d\d-\d\d')
def num(d,k,z=None):
 v=d.get(k,z) if isinstance(d,dict) else z
 return v if isinstance(v,(int,float)) and not isinstance(v,bool) else z
def dt(x):
 m=DR.search(x) if isinstance(x,str) else None;return m.group(0) if m else None
def walk(x,c=None):
 c=dict(c or {})
 if isinstance(x,dict):
  for k in ('cutoff','signalTime','entryTime','date'):
   q=dt(x.get(k));
   if q:c['date']=q;break
  for k in ('priceBreadth','flowBreadth','flowCoverage'):
   q=num(x,k)
   if q is not None:c[k]=q
  if isinstance(x.get('marketRegime'),str):c['marketRegime']=x['marketRegime'].lower()
  s=x.get('symbol') or x.get('pair');side=x.get('side') or x.get('decision')
  if isinstance(s,str):c['symbol']=s.replace('/','').upper()
  if isinstance(side,str):c['side']=side.upper()
  yield x,c
  for k,v in x.items():
   cc=dict(c);q=dt(str(k));
   if q:cc['date']=q
   yield from walk(v,cc)
 elif isinstance(x,list):
  for v in x:yield from walk(v,c)
def ores(m):
 o=m.get('outcome') if isinstance(m,dict) else None
 if isinstance(o,dict):return (o.get('result') or '').upper()
 if isinstance(o,str):return o.upper()
 return (m.get('result') or '').upper() if isinstance(m,dict) and isinstance(m.get('result'),str) else ''
def rr(m):
 for k in ('rr','plannedRR','effectiveRR','avgPlannedRR'):
  q=num(m,k)
  if q is not None:return float(q)
def rv(m):
 r=ores(m)
 if r in ('TP','WIN','TARGET'):return rr(m) or 1.0
 if r in ('SL','LOSS','STOP'):return -1.0
def load():
 z=[];seen=set()
 for fn in FILES:
  if not os.path.exists(fn):continue
  x=json.load(open(fn,encoding='utf-8'))
  for d,c in walk(x):
   s=c.get('symbol');day=c.get('date')
   if not s or not s.endswith('USDT') or not day:continue
   m=d.get('market') if isinstance(d.get('market'),dict) else None
   if m is None and ores(d) and any(k in d for k in ('entry','sl','tp')):m=d
   y=rv(m)
   if y is None:continue
   mod=d.get('model') if isinstance(d.get('model'),dict) else {}
   rec={'date':day,'symbol':s,'side':c.get('side',''),'r':y,'rr':rr(m) or num(d,'plannedRR',1.0) or 1.0,
        'b':c.get('priceBreadth'),'score':num(d,'score',num(d,'macroScore',0)) or 0,'macro':num(d,'macroScore',0) or 0,
        'micro':num(d,'microScore',0) or 0,'htf':num(mod,'htfScore',0) or 0,'reg':str(mod.get('regime') or c.get('marketRegime') or 'unknown').lower()}
   key=(fn,day,s,rec['side'],num(m,'entry',num(d,'entry')),y)
   if key in seen:continue
   seen.add(key);z.append(rec)
 return z
def sm(a):
 if not a:return {'n':0}
 w=sum(x['r']>0 for x in a);l=sum(x['r']<0 for x in a);n=w+l
 return {'n':len(a),'dates':len(set(x['date'] for x in a)),'wins':w,'losses':l,'wr':round(100*w/n,2) if n else None,'meanR':round(statistics.mean(x['r'] for x in a),3),'avgRR':round(statistics.mean(x['rr'] for x in a),3)}
def rules():
 for p in itertools.product(('ANY','BULL70','BULL85','BULL93','BEAR30','BEAR15','EXTREME','ALIGN'),('ANY','BUY','SELL','ALIGN'),(0,2,3.5,5),(0,4,7),(0,6,10),('ANY','trend','transition'),('ANY','MICRO')):yield p
def ok(x,p):
 bm,sd,sc,ma,ht,rg,mi=p;b=x['b'];s=x['side']
 if bm!='ANY':
  if b is None:return False
  if bm=='BULL70' and b<.70:return False
  if bm=='BULL85' and b<.85:return False
  if bm=='BULL93' and b<.93:return False
  if bm=='BEAR30' and b>.30:return False
  if bm=='BEAR15' and b>.15:return False
  if bm=='EXTREME' and not (b>=.8 or b<=.2):return False
  if bm=='ALIGN' and ((b>=.5 and s!='BUY') or (b<.5 and s!='SELL')):return False
 if sd=='BUY' and s!='BUY':return False
 if sd=='SELL' and s!='SELL':return False
 if sd=='ALIGN':
  if b is None or ((b>=.5 and s!='BUY') or (b<.5 and s!='SELL')):return False
 if abs(x['score'])<sc or abs(x['macro'])<ma or abs(x['htf'])<ht:return False
 if rg!='ANY' and x['reg']!=rg:return False
 if mi=='MICRO' and x['micro']!=0 and ((s=='BUY' and x['micro']<=0) or (s=='SELL' and x['micro']>=0)):return False
 return True
def best(train,minn):
 q=None
 for p in rules():
  a=[x for x in train if ok(x,p)];s=sm(a)
  if s.get('n',0)<minn or s.get('dates',0)<3 or (s.get('avgRR') or 0)<1:continue
  key=(1 if (s['wr'] or 0)>=80 else 0,s['wr'] or 0,s['meanR'],min(s['n'],100))
  if q is None or key>q[0]:q=(key,p,s)
 return q
def main():
 a=load();days=sorted(set(x['date'] for x in a));wf=[];by={}
 for i,d in enumerate(days):
  today=[x for x in a if x['date']==d]
  if i<4:by[d]={'warmup':True,'all':sm(today)};continue
  tr=[x for x in a if x['date']<d];q=best(tr,max(20,int(len(tr)*.04)))
  z=[x for x in today if q and ok(x,q[1])];wf+=z
  by[d]={'warmup':False,'all':sm(today),'rule':q[1] if q else None,'train':q[2] if q else None,'selected':sm(z)}
 ins=best(a,max(40,int(len(a)*.07)));out={'version':'CRYPTO REGIME V3 FAST','providerCreditsUsed':0,'all':sm(a),'walkForward':sm(wf),'inSample':{'rule':ins[1] if ins else None,'performance':ins[2] if ins else None},'byDate':by}
 out['targetMet']=bool((out['walkForward'].get('wr') or 0)>=80 and (out['walkForward'].get('avgRR') or 0)>=1 and out['walkForward'].get('n',0)>=20)
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
