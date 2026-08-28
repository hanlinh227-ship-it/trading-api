import csv,json,math,hashlib,random
from collections import Counter,defaultdict
from pathlib import Path
P=Path('data/vietlott/power655/power655_all_draws.csv'); O=Path('data/vietlott/power655/adaptive_ensemble_research.json')
with P.open() as f:
 r=list(csv.DictReader(f))
D=[tuple(int(x[f'n{i}']) for i in range(1,7)) for x in r]; IDS=[x['draw_id'] for x in r]; N=len(D); BASE=6/55

def top6(sc): return sorted(sorted(range(1,56),key=lambda n:(-sc.get(n,0),n))[:6])
def freq(H,w,decay=1.0):
 H=H[-w:] if w else H; sc=defaultdict(float)
 for age,d in enumerate(reversed(H)):
  z=decay**age
  for n in d: sc[n]+=z
 return top6(sc)
def gap(H):
 sc={}
 for n in range(1,56):
  g=len(H)+1
  for i,d in enumerate(reversed(H),1):
   if n in d:g=i;break
  sc[n]=g
 return top6(sc)
def lag(H,k): return sorted(H[-k]) if len(H)>=k else freq(H,0)
def trans(H,w):
 H=H[-w:] if len(H)>w else H; sc=defaultdict(float)
 if len(H)<2:return freq(H,0)
 last=set(H[-1])
 for a,b in zip(H[:-1],H[1:]):
  if last.intersection(a):
   for n in b:sc[n]+=1
 return top6(sc) if sc else freq(H,0)
def pair(H,w):
 H=H[-w:] if len(H)>w else H; last=set(H[-1]); sc=defaultdict(float)
 for d in H[:-1]:
  ov=len(last.intersection(d))
  if ov:
   for n in d:sc[n]+=ov
 return top6(sc)
def sha(H,w,salt):
 H=H[-w:] if w else H; b=('|'.join(','.join(map(str,d)) for d in H)+'|'+salt).encode(); z=hashlib.sha256(b).digest(); out=[];i=0
 while len(out)<6:
  if i+1>=len(z):z+=hashlib.sha256(z).digest()
  n=((z[i]<<8)|z[i+1])%55+1;i+=2
  if n not in out:out.append(n)
 return sorted(out)
experts=[]
for w in [5,10,20,34,55,89,144,233,0]: experts.append((f'freq{w}',lambda H,w=w:freq(H,w)))
for w in [10,20,55,144]:
 for d in [.94,.97,.985]:experts.append((f'decay{w}_{d}',lambda H,w=w,d=d:freq(H,w,d)))
experts += [('gap',gap)]
for k in [1,2,3,5,7,10,21,34]:experts.append((f'lag{k}',lambda H,k=k:lag(H,k)))
for w in [20,55,144]:experts.append((f'trans{w}',lambda H,w=w:trans(H,w)))
for w in [20,55,144]:experts.append((f'pair{w}',lambda H,w=w:pair(H,w)))
for w in [5,10,21,55,144,0]:
 for s in range(4):experts.append((f'sha{w}_{s}',lambda H,w=w,s=s:sha(H,w,f'adaptive{s}')))
# Strict online expert learning: candidate library fixed before seeing targets. At t, weights use only outcomes <t.
eta=.35; alpha=20.0; scores=[0.0]*len(experts); trials=[0]*len(experts); hist=[0]*7; records=[]; block=defaultdict(lambda:[0,0,[0]*7])
for t in range(10,N):
 H=D[:t]; preds=[fn(H) for _,fn in experts]
 # shrink excess-hit estimates toward random baseline; softmax ensemble, no future data
 vals=[]
 for j in range(len(experts)):
  mean=(scores[j]+alpha*6*BASE)/(trials[j]+alpha) if trials[j]+alpha else 6*BASE
  vals.append(eta*(mean-6*BASE)*math.sqrt(max(1,trials[j])))
 m=max(vals); ws=[math.exp(v-m) for v in vals]
 vote=defaultdict(float)
 for j,p in enumerate(preds):
  for n in p: vote[n]+=ws[j]
 pred=top6(vote); actual=set(D[t]); h=len(set(pred)&actual);hist[h]+=1
 b='holdout240' if t>=N-240 else 'development';block[b][0]+=h;block[b][1]+=1;block[b][2][h]+=1
 if len(records)<30:records.append({'target':IDS[t],'known_through':IDS[t-1],'prediction':pred,'actual':sorted(actual),'hits':h})
 for j,p in enumerate(preds): scores[j]+=len(set(p)&actual);trials[j]+=1

def met(x):
 matches,draws,hh=x; return {'draws':draws,'histogram':hh,'matches':matches,'mean_hits':matches/draws,'number_accuracy':matches/(6*draws),'lift_vs_random':matches/(6*draws)-BASE,'rate_3plus':sum(hh[3:])/draws,'rate_4plus':sum(hh[4:])/draws,'rate_5plus':sum(hh[5:])/draws,'rate_6':hh[6]/draws}
allx=[sum(i*hist[i] for i in range(7)),sum(hist),hist]
res={'draw_count':N,'protocol':'strict online: know 1..10 predict 11; reveal; update expert scores; predict next. Formula weights never use current/future target.','target_note':'80% is a search target, never forced; report actual blind performance.','expert_count':len(experts),'experts':[x[0] for x in experts],'random_number_accuracy':BASE,'all_prequential':met(allx),'development':met(block['development']),'holdout240':met(block['holdout240']),'achieved_80pct_number_accuracy':met(block['holdout240'])['number_accuracy']>=.8,'early_audit':records}
O.write_text(json.dumps(res,indent=2));print(json.dumps({'all':res['all_prequential'],'holdout':res['holdout240']},indent=2))
