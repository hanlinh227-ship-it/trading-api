import csv,json,math,pathlib,random
from collections import Counter,defaultdict
P=pathlib.Path('data/vietlott/power655'); rows=list(csv.DictReader((P/'power655_all_draws.csv').open()))
D=[tuple(int(r[f'n{i}']) for i in range(1,7)) for r in rows]; N=len(D); BASE=6/55

def top6(s): return tuple(sorted(sorted(range(1,56),key=lambda x:(s[x],-x),reverse=True)[:6]))
def score_family(t,name):
 h=D[:t]; s={x:0.0 for x in range(1,56)}
 if name.startswith('freq'):
  W=int(name[4:]); c=Counter(x for d in h[-W:] for x in d)
  for x in s:s[x]=(c[x]+2)/(6*min(W,len(h))+110)
 elif name.startswith('gap'):
  last={x:999 for x in s}
  for j,d in enumerate(reversed(h)):
   for x in d:
    if last[x]==999:last[x]=j
  sign=1 if name=='gap_overdue' else -1
  for x in s:s[x]=sign*min(last[x],100)
 elif name.startswith('lag'):
  lag=int(name[3:]);
  if t>=lag:
   for x in D[t-lag]:s[x]=1
 elif name=='transition':
  if not h:return s
  prev=set(h[-1]); hit=defaultdict(Counter); supp=Counter()
  for i in range(1,t):
   for q in D[i-1]:
    supp[q]+=1
    for x in D[i]:hit[q][x]+=1
  for x in s:s[x]=sum((hit[q][x]+1)/(supp[q]+10) for q in prev)
 elif name=='paircore':
  if not h:return s
  prev=set(h[-1]); pc=Counter()
  for d in h:
   ov=len(prev&set(d))
   if ov>=2:
    for x in d:pc[x]+=ov
  for x in s:s[x]=pc[x]
 return s
F=['freq20','freq50','freq100','freq250','gap_overdue','gap_recent','transition','paircore']+[f'lag{x}' for x in (1,2,3,7,11,17,29,46,63,69,76,81,84,90)]
# At each draw, rank functions using ONLY their prior 120 realized predictions. Then ensemble top historical performers.
history={f:[] for f in F}; records=[]
for t in range(250,N):
 preds={f:top6(score_family(t,f)) for f in F}
 # historical rolling skill, no current outcome access
 skill={}
 for f in F:
  a=history[f][-120:]
  skill[f]=(sum(a)/len(a) if a else BASE*6)
 chosen=sorted(F,key=lambda f:(skill[f],f),reverse=True)[:5]
 vote={x:0.0 for x in range(1,56)}
 for rank,f in enumerate(chosen):
  w=1/(rank+1)
  for x in preds[f]:vote[x]+=w
 final=top6(vote); actual=set(D[t]); k=len(set(final)&actual)
 records.append({'draw':t+1,'chosen':chosen,'prediction':final,'hits':k})
 for f in F:history[f].append(len(set(preds[f])&actual))
# untouched evaluation summaries by chronological blocks
hist=[0]*7
for r in records:hist[r['hits']]+=1
blocks=[]
for lo in range(0,len(records),200):
 q=records[lo:lo+200]; hh=[0]*7
 for r in q:hh[r['hits']]+=1
 blocks.append({'start_draw':q[0]['draw'],'end_draw':q[-1]['draw'],'n':len(q),'histogram':hh,'mean_hits':sum(r['hits'] for r in q)/len(q)})
# Function appearance: which functions survive adaptive selection and their realized rolling skill.
sel=Counter(f for r in records for f in r['chosen']); fs={}
for f in F:
 a=history[f]; fs[f]={'selected_count':sel[f],'mean_hits':sum(a)/len(a),'rate_3plus':sum(v>=3 for v in a)/len(a),'rate_4plus':sum(v>=4 for v in a)/len(a),'rate_5plus':sum(v>=5 for v in a)/len(a)}
# final next-draw prediction uses all 1390 outcomes only as history, never a future target.
t=N; skill={f:sum(history[f][-120:])/len(history[f][-120:]) for f in F}; chosen=sorted(F,key=lambda f:(skill[f],f),reverse=True)[:5]; preds={f:top6(score_family(t,f)) for f in F}; vote={x:0.0 for x in range(1,56)}
for rank,f in enumerate(chosen):
 for x in preds[f]:vote[x]+=1/(rank+1)
next6=top6(vote)
out={'draw_count':N,'protocol':'strict per-draw blind adaptive ensemble: at t all scores and function selection use only draws < t; current outcome revealed only after prediction','functions':F,'overall':{'n':len(records),'histogram':hist,'mean_hits':sum(r['hits'] for r in records)/len(records),'rate_3plus':sum(hist[3:])/len(records),'rate_4plus':sum(hist[4:])/len(records),'rate_5plus':sum(hist[5:])/len(records)},'blocks':blocks,'function_appearance':fs,'next_draw_candidate':{'draw':N+1,'chosen_functions':chosen,'numbers':next6,'function_recent_skill':{f:skill[f] for f in chosen}},'warning':'Lottery remains stochastic. Candidate is a research output, not a guaranteed winning set; retain only functions with stable blind performance versus random/Monte Carlo.'}
(P/'blind_function_ensemble.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['overall'],indent=2));print(out['next_draw_candidate'])
