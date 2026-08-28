import csv,json,random,math,pathlib,statistics
P=pathlib.Path('data/vietlott/power655'); R=random.Random(6552026)
rows=list(csv.DictReader((P/'power655_all_draws.csv').open())); D=[tuple(int(r[f'n{i}']) for i in range(1,7)) for r in rows]; N=len(D)
def w(x):return ((int(x)-1)%55)+1
# Strict blind: tune only on prior history; test future held-out block. A prediction is exactly 6 distinct numbers.
def transform(src,a,b,c,mode):
 out=[]
 for i,x in enumerate(src):
  y=src[(i+c)%6]
  if mode==0:z=a*x+b
  elif mode==1:z=a*x+b*y
  elif mode==2:z=a*x-b*y
  elif mode==3:z=a*(56-x)+b
  elif mode==4:z=a*x+b*(i+1)
  elif mode==5:z=a*(x+y)+b
  else:z=a*(x-y)+b
  out.append(w(z))
 # deterministic collision repair, no target access
 used=set(); fixed=[]
 for i,z in enumerate(out):
  while z in used:z=w(z+1)
  used.add(z);fixed.append(z)
 return tuple(sorted(fixed))
def eval_rule(rule,lo,hi):
 lag,a,b,c,m=rule; hist=[0]*7; exact=0; total=0
 for t in range(lo,min(hi,N-lag)):
  p=set(transform(D[t],a,b,c,m)); k=len(p&set(D[t+lag])); hist[k]+=1;exact+=k;total+=1
 return hist, exact/(6*total) if total else 0,total
# Randomly generate large family, select only TRAIN. Then freeze and blind TEST.
train_end=900; valid_end=1150; test_start=1150
rules=[]
for _ in range(120000):
 lag=R.randint(1,365);a=R.randint(-20,20) or 1;b=R.randint(-55,55);c=R.randint(0,5);m=R.randint(0,6);rules.append((lag,a,b,c,m))
sc=[]
for r in rules:
 h,rate,n=eval_rule(r,0,train_end)
 # objective prioritizes >=5/6 and >=4/6, not ordinary 1-number hits
 score=(h[6]*20+h[5]*8+h[4]*3+h[3])/(n or 1)
 sc.append((score,rate,r,h))
sc.sort(reverse=True)
# validate top 3000, freeze top 100 by validation score
val=[]
for _,_,r,th in sc[:3000]:
 h,rate,n=eval_rule(r,train_end,valid_end); score=(h[6]*20+h[5]*8+h[4]*3+h[3])/(n or 1);val.append((score,rate,r,h,th))
val.sort(reverse=True)
final=[]
for vs,vr,r,vh,th in val[:100]:
 h,rate,n=eval_rule(r,test_start,N); final.append({'rule':{'lag':r[0],'a':r[1],'b':r[2],'rotation':r[3],'mode':r[4]},'train_hist':th,'validation_hist':vh,'blind_test_hist':h,'blind_test_draws':n,'blind_test_number_accuracy':round(rate,6),'blind_test_5plus_rate':round((h[5]+h[6])/n,6) if n else None,'blind_test_4plus_rate':round((h[4]+h[5]+h[6])/n,6) if n else None})
final.sort(key=lambda x:(x['blind_test_5plus_rate'] or 0,x['blind_test_4plus_rate'] or 0,x['blind_test_number_accuracy']),reverse=True)
# The 80% threshold can mean >=4.8/6; operationalize as >=5/6 per draw. Also report number-wise 80%.
out={'draw_count':N,'blind_protocol':{'train':'draw indices 1-900','validation':'901-1150','blind_test':'1151-1390','random_rules':len(rules),'selection':'target never used to fit a rule after validation; final test untouched'},'threshold_definition':'80% of six numbers means at least 5/6 numbers in a draw; also report aggregate per-number accuracy.','best_blind_results':final[:50],'any_rule_80pct_number_accuracy':any((x['blind_test_number_accuracy'] or 0)>=.8 for x in final),'any_rule_80pct_draws_at_5plus':any((x['blind_test_5plus_rate'] or 0)>=.8 for x in final),'warning':'If no rule reaches 80% blind, do not loosen the blind protocol or search the held-out outcomes; that would be look-ahead overfit.'}
(P/'blind_random_transform_search.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
