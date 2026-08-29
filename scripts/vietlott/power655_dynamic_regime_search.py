import csv,json,math,pathlib,random
from collections import Counter
P=pathlib.Path('data/vietlott/power655'); rows=list(csv.DictReader((P/'power655_all_draws.csv').open()))
D=[set(int(r[f'n{i}']) for i in range(1,7)) for r in rows]; N=len(D)
WINDOWS=(180,300,450); STEP=30; MAXLAG=900; LEVELS=(3,4)

def spectrum(lo,hi,k,maxlag=MAXLAG):
 c=Counter(); exposure=Counter()
 for lag in range(1,min(maxlag,hi-lo-1)+1):
  exposure[lag]=hi-lo-lag
 for i in range(lo,hi):
  for j in range(max(lo,i-maxlag),i):
   if len(D[i]&D[j])==k:c[i-j]+=1
 # standardize against rate estimated within window, correcting triangular exposure
 tot=sum(c.values()); ex=sum(exposure.values()); rate=tot/ex if ex else 0
 peaks=[]
 for lag,e in exposure.items():
  mu=e*rate
  if mu>=1:
   z=(c[lag]-mu)/math.sqrt(mu)
   peaks.append((z,lag,c[lag],mu))
 return sorted(peaks,reverse=True)[:12]

rolling=[]
for w in WINDOWS:
 for hi in range(w,N+1,STEP):
  lo=hi-w
  for k in LEVELS:
   pk=spectrum(lo,hi,k)
   rolling.append({'window':w,'start_draw':lo+1,'end_draw':hi,'level':k,'peaks':[{'lag':b,'observed':c,'expected':round(mu,3),'z':round(z,3)} for z,b,c,mu in pk]})

# Persistence: lags clustered +/-3 across rolling windows.
persist={}
for k in LEVELS:
 votes=Counter(); weighted=Counter()
 for r in rolling:
  if r['level']!=k:continue
  for p in r['peaks'][:5]:
   # quantize to 7-draw bins to permit drifting peaks
   b=round(p['lag']/7)*7; votes[b]+=1; weighted[b]+=max(0,p['z'])
 persist[str(k)]=[{'lag_center':lag,'window_votes':v,'z_weight':round(weighted[lag],2)} for lag,v in votes.most_common(20)]

# Strict OOS candidate test: discover lags using first 1000 draws, test only 1001..N.
CUT=min(1000,N-200)
def global_spectrum(end,k):
 c=Counter(); exp=Counter()
 for lag in range(1,min(MAXLAG,end-1)+1):exp[lag]=end-lag
 for i in range(end):
  for j in range(max(0,i-MAXLAG),i):
   if len(D[i]&D[j])==k:c[i-j]+=1
 rate=sum(c.values())/sum(exp.values()); arr=[]
 for lag,e in exp.items():
  mu=e*rate
  if mu>=2:arr.append(((c[lag]-mu)/math.sqrt(mu),lag))
 return sorted(arr,reverse=True)

def oos_for_lag(lag,k):
 hit=0; eligible=0
 for t in range(CUT,N):
  if t-lag<0:continue
  eligible+=1
  if len(D[t]&D[t-lag])==k:hit+=1
 # null exact-overlap probability
 den=math.comb(55,6); prob=math.comb(6,k)*math.comb(49,6-k)/den
 mu=eligible*prob; z=(hit-mu)/math.sqrt(mu*(1-prob)) if mu>0 else 0
 return {'lag':lag,'level':k,'eligible':eligible,'observed':hit,'expected':round(mu,3),'z':round(z,3)}

oos={}
for k in LEVELS:
 candidates=[lag for z,lag in global_spectrum(CUT,k)[:20]]
 oos[str(k)]=[oos_for_lag(lag,k) for lag in candidates]

# Explicit 346 recurrence hypothesis from the historical 6/6 collision; test next continuation at draw 1339.
cycle346=[]
for t in range(346,N):
 ov=len(D[t]&D[t-346]);
 if ov>=3:cycle346.append({'draw':t+1,'prior_draw':t+1-346,'overlap':ov,'current':sorted(D[t]),'prior':sorted(D[t-346])})
check1339=None
if N>=1339:
 t=1338; check1339={'draw':1339,'prior_draw':993,'overlap':len(D[t]&D[t-346]),'draw_1339':sorted(D[t]),'draw_993':sorted(D[t-346])}

out={'draw_count':N,'design':{'rolling_windows':WINDOWS,'step':STEP,'max_lag':MAXLAG,'levels':LEVELS,'oos_cut':CUT,'rules':'rolling lag spectra corrected for triangular exposure; persistence uses +/-3-equivalent 7-draw bins; candidates discovered only pre-cut and tested post-cut'},'rolling_windows':rolling,'persistent_lag_candidates':persist,'strict_oos':oos,'cycle_346_all_3plus':cycle346,'cycle_346_oos_check_1339':check1339,'guardrail':'Candidate cycle is retained only if it persists across windows AND survives untouched OOS. Peaks alone are not predictive evidence.'}
(P/'dynamic_regime_search.json').write_text(json.dumps(out,indent=2)+'\n');print('dynamic regime search complete',N,'draws; check1339=',check1339)
