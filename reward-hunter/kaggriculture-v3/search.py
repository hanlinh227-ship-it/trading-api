"""Structured ablations + deterministic mutation; no holdout-driven retry or submission."""
import argparse
import json
import random
from pathlib import Path
from benchmark import evaluate,save,digest
from policy import V3_DEFAULT
from opponents import SUITE
from package_submission import build
from raw_exec_test import check
from promotion import gate


def candidates(n,seed):
    rng=random.Random(seed)
    pool=[dict(V3_DEFAULT)]
    for change in ({'crop_mode':'grains'},{'crop_mode':'demand'},{'harvest_wait':False},{'market':False},{'distance_cost':18.},{'target_hands':9},{'target_hands':13}):
        pool.append(dict(V3_DEFAULT,**change))
    pool=pool[:n]
    while len(pool)<n:
        p=dict(rng.choice(pool));p[rng.choice(('distance_cost','target_hands','crop_mode'))]=None
        if p['distance_cost'] is None:p['distance_cost']=rng.choice((4.,9.,14.,22.))
        if p['target_hands'] is None:p['target_hands']=rng.choice((7,9,11,13))
        if p['crop_mode'] is None:p['crop_mode']=rng.choice(('balanced','grains','demand'))
        if p not in pool:pool.append(p)
    return pool


def run(out,n=8,workers=0,smoke=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    # Reruns in same output directory require explicit new study: never reuse final holdout.
    if (out/'search.json').exists():raise ValueError('Use a new output directory/study; final holdout already consumed')
    seeds=[101,103];hold=[7001,7003,7007,7013];final=[9001,9007,9011,9013];duelseeds=[211,223,227,229]
    steps=120 if smoke else 720
    pool=candidates(n,1919);history=[]
    def ev(p,ss,fs,label,kind='v3',path=None):
        r=evaluate(p,ss,fs,steps,workers,kind,path);save(out/(label+'.json'),r)
        print(label,json.dumps(r['metrics']),flush=True);return r
    for stage,ss,fs,keep in [('A',seeds[:1],('starter','incumbent'),max(2,n//2)),('B',seeds,('incumbent','early_sell','grains'),2),('C',seeds,SUITE,1)]:
        ranked=[]
        for p in pool:
            r=ev(p,ss,fs,stage+'-'+digest(p)[:10]);ranked.append((r['metrics']['objective'],p,r))
        ranked.sort(key=lambda x:(x[0],digest(x[1])),reverse=True)
        history.append(dict(stage=stage,ranking=[dict(params=p,metrics=r['metrics']) for _,p,r in ranked]))
        pool=[p for _,p,_ in ranked[:keep]]
    best=pool[0];train=ranked[0][2]
    duel=ev(best,duelseeds,('incumbent',),'D-duel')
    h=ev(best,hold,SUITE,'E-holdout');bh=ev(best,hold,SUITE,'E-baseline','incumbent')
    f=ev(best,final,SUITE,'F-final');bf=ev(best,final,SUITE,'F-baseline','incumbent')
    package=build(best,out/'candidate-main.py');runtime=check(out/'candidate-main.py')
    packaged=ev(best,[997],('incumbent',),'packaged',path=out/'candidate-main.py')
    source=ev(best,[997],('incumbent',),'source')
    keys=('margin','valid','statuses','efficiency','terminal_unsold_units')
    runtime['episode_equivalence']='PASS' if all(all(a[k]==b[k] for k in keys) for a,b in zip(packaged['rows'],source['rows'])) and all(r['valid'] for r in packaged['rows']) else 'FAIL'
    decision=gate(train,duel,h,f,bh,bf,runtime)
    result=dict(best_params=best,stages=history,promotion=decision,runtime=runtime,package=package,
                duel=duel['metrics'],holdout=h['metrics'],final=f['metrics'],baseline_holdout=bh['metrics'],baseline_final=bf['metrics'],provenance=train['provenance'],
                study_seed_sets=dict(train=seeds,duel=duelseeds,holdout=hold,final=final),submission_performed=False)
    save(out/'search.json',result)
    if decision['pass_gate']:save(out/'champion.json',dict(params=best,evidence=result))
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--candidates',type=int,default=8);ap.add_argument('--workers',type=int,default=0);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    if not 2<=a.candidates<=64:ap.error('candidates must be 2..64')
    run(a.output,a.candidates,a.workers,a.smoke)
