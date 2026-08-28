import csv,json,math,itertools,collections,statistics,pathlib
P=pathlib.Path('data/vietlott/power655'); rows=list(csv.DictReader((P/'power655_all_draws.csv').open()))
draws=[tuple(int(r[f'n{i}']) for i in range(1,7)) for r in rows]; N=len(draws)

def wrap(x): return ((int(x)-1)%55)+1
def rev(x):
 s=str(x); y=int(s[::-1]); return y if 1<=y<=55 else None
def dr(x):
 x=abs(int(x)); return 0 if x==0 else 1+(x-1)%9

def features(a):
 S=set(a); out={'raw':set(a),'mirror':{56-x for x in a},'reverse':{y for x in a if (y:=rev(x))},'digitroot':{dr(x) for x in a}}
 for k in range(2,7):
  sums=set(); diffs=set(); prods=set(); ratios=set(); mods=set()
  for c in itertools.combinations(a,k):
   sm=sum(c); sums.add(wrap(sm)); mods.add(sm%55 or 55)
   diffs.add(wrap(max(c)-min(c)))
   pr=math.prod(c); prods.add(wrap(pr))
   for x,y in itertools.permutations(c,2):
    if y and x%y==0 and 1<=x//y<=55: ratios.add(x//y)
  out[f'sum{k}']=sums; out[f'diff{k}']=diffs; out[f'prod{k}']=prods; out[f'ratio{k}']=ratios; out[f'mod{k}']=mods
 # positional shifts and adjacent differences
 out['adjdiff']={abs(a[i+1]-a[i]) for i in range(5)}
 out['gapsum']={wrap(sum(abs(a[i+1]-a[i]) for i in range(5)))}
 return out
F=[features(a) for a in draws]; names=list(F[0])
# Score whether transform outputs from t hit any raw number at t+lag. Baseline is empirical target coverage under circularly shifted target order.
MAXL=min(700,N-1); results=[]
for name in names:
 for lag in range(1,MAXL+1):
  hits=tot=0
  for t in range(N-lag):
   A=F[t][name]; B=set(draws[t+lag]); hits+=len(A&B); tot+=6
  rate=hits/tot
  results.append((rate,name,lag,hits,tot))
# null per feature: average rate across lags, then z-like residual per lag; this removes feature-set-size bias.
by=collections.defaultdict(list)
for r in results: by[r[1]].append(r)
ranked=[]
for name,rs in by.items():
 p=sum(x[3] for x in rs)/sum(x[4] for x in rs)
 for rate,n,lag,hits,tot in rs:
  var=tot*p*(1-p); z=(hits-tot*p)/math.sqrt(var) if var else 0
  ranked.append((z,rate,n,lag,hits,tot,p))
ranked.sort(reverse=True)
# Stability: compare same transform+lag in thirds.
def segment(name,lag,lo,hi):
 h=tot=0
 for t in range(lo,min(hi,N-lag)):
  h+=len(F[t][name]&set(draws[t+lag])); tot+=6
 return h/tot if tot else None
cands=[]
for z,rate,name,lag,hits,tot,p in ranked[:300]:
 seg=[segment(name,lag,0,N//3),segment(name,lag,N//3,2*N//3),segment(name,lag,2*N//3,N)]
 valid=[x for x in seg if x is not None]
 stable=(min(valid)>p if valid else False)
 cands.append({'transform':name,'lag':lag,'rate':round(rate,6),'feature_baseline':round(p,6),'z_exploratory':round(z,3),'third_rates':[None if x is None else round(x,6) for x in seg],'above_baseline_all_thirds':stable})
# Harmonic families among top stable candidates: lags near integer multiples within +/-2.
stable=[x for x in cands if x['above_baseline_all_thirds']]
harm=[]
for name in names:
 ls=sorted(x['lag'] for x in stable if x['transform']==name)
 for base in ls:
  fam=[x for x in ls if x>base and any(abs(x-m*base)<=2 for m in range(2,7))]
  if fam: harm.append({'transform':name,'base_lag':base,'harmonics':fam})
# Affine maps x -> a*x+b mod55, restricted a coprime to55, lags 1..365; exact transformed-number hit rate.
aff=[]
As=[a for a in range(1,55) if math.gcd(a,55)==1]
for lag in range(1,min(365,N)):
 for aa in As:
  for b in range(0,55,5): # coarse scan to control search multiplicity
   h=tot=0
   for t in range(N-lag):
    pred={wrap(aa*x+b) for x in draws[t]}; h+=len(pred&set(draws[t+lag])); tot+=6
   aff.append((h/tot,lag,aa,b,h,tot))
aff.sort(reverse=True)
out={'draw_count':N,'max_lag':MAXL,'transform_count':len(names),'method':'Transform outputs at draw t matched against six raw numbers at t+lag. Exploratory feature-specific lag baseline; thirds stability filter. Affine scan coarse b step=5.','top_candidates':cands[:100],'stable_candidates':stable[:100],'harmonic_families':harm[:100],'top_affine_raw_rates':[{'lag':l,'a':a,'b':b,'rate':round(r,6),'hits':h,'total_slots':t} for r,l,a,b,h,t in aff[:50]],'warning':'Exploratory multiple-hypothesis scan. Peaks are not evidence of non-random mechanism until Monte Carlo surrogate and strict walk-forward validation.'}
(P/'math_transform_cycle_research.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'top':cands[:10],'stable_count':len(stable),'harmonics':harm[:10],'affine':out['top_affine_raw_rates'][:5]},indent=2))
