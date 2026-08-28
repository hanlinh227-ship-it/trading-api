import csv,json,math,pathlib,random
from collections import Counter,defaultdict
P=pathlib.Path('data/vietlott/power655'); rows=list(csv.DictReader((P/'power655_all_draws.csv').open()))
D=[tuple(int(r[f'n{i}']) for i in range(1,7)) for r in rows]; N=len(D); BASE=6/55
# Every target t uses only D[:t]. Exactly six distinct predictions.
def top6(score): return tuple(sorted(sorted(range(1,56),key=lambda x:(score[x],-x),reverse=True)[:6]))
def features(t):
 hist=D[:t]; score={x:0.0 for x in range(1,56)}
 # Bayesian-shrunk rolling frequency at several horizons.
 for W,wt in ((20,.8),(50,1.0),(100,.8),(250,.5)):
  h=hist[-W:]; c=Counter(x for d in h for x in d); den=6*len(h)+55*12*BASE
  for x in score: score[x]+=wt*((c[x]+12*BASE)/max(1,len(h)+12)-BASE)
 # Recency/hazard: time since last appearance, standardized against geometric baseline.
 last={x:t for x in score}
 for j,d in enumerate(reversed(hist)):
  for x in d:
   if last[x]==t:last[x]=j
 for x in score: score[x]+=.12*min(last[x],80)/80
 # Conditional transition from last draw, regularized.
 if t>30:
  prev=set(hist[-1]); hit=defaultdict(Counter); supp=Counter()
  for i in range(1,t):
   a=set(D[i-1]); b=set(D[i])
   for q in a:
    supp[q]+=1
    for x in b: hit[q][x]+=1
  for x in score:
   score[x]+=.5*sum((hit[q][x]+2*BASE)/(supp[q]+2) - BASE for q in prev)/6
 # Pair co-occurrence with last draw, shrink aggressively.
 pc=defaultdict(Counter); ps=Counter()
 for d in hist:
  s=set(d)
  for q in s:
   ps[q]+=1
   for x in s:
    if x!=q:pc[q][x]+=1
 if hist:
  for x in score: score[x]+=.15*sum((pc[q][x]+3*BASE)/(ps[q]+3)-BASE for q in hist[-1])/6
 return score
def predict_family(t,kind):
 s=features(t)
 if kind=='bayes': return top6(s)
 # Lag ensemble adds votes from prior draw sets, still only past information.
 if kind=='lag':
  for lag,wt in ((1,.25),(2,.18),(3,.15),(7,.12),(11,.10),(17,.08),(29,.07),(46,.06),(69,.05),(129,.04)):
   if t>=lag:
    for x in D[t-lag]:s[x]+=wt
  return top6(s)
 # Mirror/modular transform ensemble of recent draws.
 if kind=='transform':
  for lag,wt in ((1,.16),(3,.13),(7,.11),(17,.09),(46,.07),(129,.05)):
   if t>=lag:
    for x in D[t-lag]:
     for y in (56-x,((3*x+7-1)%55)+1,((5*x-11-1)%55)+1):s[y]+=wt/3
  return top6(s)
 raise ValueError(kind)
def run(kind,start=250,end=None):
 end=N if end is None else min(end,N); h=[0]*7; rec=[]
 for t in range(start,end):
  p=predict_family(t,kind); k=len(set(p)&set(D[t]));h[k]+=1;rec.append({'draw':t+1,'prediction':p,'hits':k})
 n=len(rec);matches=sum(i*h[i] for i in range(7));acc=matches/(6*n) if n else 0
 return {'family':kind,'draws':n,'histogram':h,'matches':matches,'mean_hits':matches/n if n else 0,'number_accuracy':acc,'lift_vs_random':acc-BASE,'rate_3plus':sum(h[3:])/n if n else 0,'rate_4plus':sum(h[4:])/n if n else 0,'rate_5plus':sum(h[5:])/n if n else 0,'rate_6':h[6]/n if n else 0,'records':rec}
# Family selection uses pre-holdout only; final 240 draws remain untouched by selection.
cut=max(250,N-240); families=['bayes','lag','transform']; dev=[run(k,250,cut) for k in families]; chosen=max(dev,key=lambda x:x['number_accuracy'])['family']; hold=run(chosen,cut,N)
# Chronological blocks for stability; all predictions remain walk-forward.
blocks=[]
for lo in range(250,N,200):
 r=run(chosen,lo,min(lo+200,N));blocks.append({k:v for k,v in r.items() if k!='records'})
# Approx normal z against per-number random baseline; descriptive, not proof after model search.
n=hold['draws']*6;p=BASE;se=math.sqrt(p*(1-p)/n) if n else 0;z=(hold['number_accuracy']-p)/se if se else 0
out={'draw_count':N,'protocol':'strict sequential walk-forward; prediction for t uses draws < t; family selected before final 240-draw holdout','random_number_accuracy':BASE,'development':[ {k:v for k,v in r.items() if k!='records'} for r in dev], 'selected_family':chosen,'holdout':{k:v for k,v in hold.items() if k!='records'},'holdout_z_vs_random':z,'chronological_blocks':blocks,'achieved_80pct_number_accuracy':hold['number_accuracy']>=.8,'warning':'Exploratory family search. 80% is never forced. Further large searches require nested selection and max-statistic permutation correction.'}
(P/'walkforward_statistical_search.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
