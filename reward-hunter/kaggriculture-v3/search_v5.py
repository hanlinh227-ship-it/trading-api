"""V5 staged search over crop economics, herd mix, fertilizer, labor and expansion."""
import argparse,json,random
from pathlib import Path
from benchmark_v5 import evaluate,save,digest
from policy import V3_DEFAULT
from opponents import SUITE
from package_submission import build
from raw_exec_test import check
from promotion_v5 import gate


def candidates(n,seed):
    rng=random.Random(seed); base=dict(V3_DEFAULT); pool=[]
    presets=[
        {},
        {'herd_mode':'none','fertilizer_mode':'off','crop_mode':'roi'},
        {'herd_mode':'cow_sheep','cow_max':8,'sheep_max':6,'goose_max':0,'crop_mode':'roi','fertilizer_mode':'adaptive','target_hands':12},
        {'herd_mode':'cow_sheep','cow_max':6,'sheep_max':4,'crop_mode':'roi','target_hands':11,'sell_batch':5},
        {'herd_mode':'dynamic','cow_max':8,'sheep_max':6,'goose_max':2,'crop_mode':'roi','fertilizer_mode':'adaptive','feed_carry':5},
        {'herd_mode':'dynamic','cow_max':6,'sheep_max':6,'goose_max':3,'crop_mode':'demand','fertilizer_mode':'adaptive','feed_carry':6},
        {'herd_mode':'dynamic','cow_max':10,'sheep_max':4,'goose_max':0,'crop_mode':'roi','fertilizer_mode':'herd_only','target_hands':13},
        {'herd_mode':'cow_sheep','cow_max':8,'sheep_max':4,'crop_mode':'fast_cash','livestock_start_day':2,'land_buffer':100},
        {'herd_mode':'dynamic','cow_max':7,'sheep_max':5,'goose_max':1,'crop_mode':'roi','expansion_mode':'max','land_buffer':80,'seed_scale':1.7},
        {'herd_mode':'dynamic','cow_max':8,'sheep_max':6,'goose_max':0,'crop_mode':'roi','expansion_mode':'fast','land_buffer':260,'fill_target':.82},
        {'herd_mode':'none','crop_mode':'demand','target_hands':13,'seed_scale':1.8,'sell_batch':5},
        {'herd_mode':'dynamic','cow_max':5,'sheep_max':3,'goose_max':2,'crop_mode':'roi','fertilizer_mode':'adaptive','sell_batch':4,'drop_at':6},
    ]
    for patch in presets:
        p=dict(base);p.update(patch)
        if p not in pool:pool.append(p)
        if len(pool)>=n:return pool[:n]
    keys=('distance_cost','target_hands','crop_mode','expansion_mode','land_buffer','fill_target','fill_priority','seed_scale','herd_mode','cow_max','sheep_max','goose_max','livestock_start_day','livestock_cash_buffer','feed_carry','drop_at','fertilizer_mode','sell_batch')
    while len(pool)<n:
        p=dict(rng.choice(pool));k=rng.choice(keys)
        choices={
            'distance_cost':(5.,7.,9.,12.),'target_hands':(10,11,12,13,14),'crop_mode':('roi','demand','fast_cash','balanced'),
            'expansion_mode':('balanced','fast','max'),'land_buffer':(50,100,180,260,400),'fill_target':(.70,.78,.84,.90,.94),
            'fill_priority':(70.,82.,90.,102.,115.),'seed_scale':(1.0,1.3,1.55,1.8,2.1),'herd_mode':('none','cow_sheep','dynamic'),
            'cow_max':(4,6,8,10),'sheep_max':(0,3,4,6,8),'goose_max':(0,1,2,4),'livestock_start_day':(0,1,2,3,4),
            'livestock_cash_buffer':(200,400,600,900,1300),'feed_carry':(3,4,5,6,8),'drop_at':(5,7,8,10,12),
            'fertilizer_mode':('off','herd_only','adaptive'),'sell_batch':(3,4,5,6,8,10),
        }
        p[k]=rng.choice(choices[k])
        if p not in pool:pool.append(p)
    return pool


def run(out,n=20,workers=0,study_seed=5059):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'search.json').exists():raise ValueError('fresh output directory required')
    blocks=random.Random(study_seed).sample(range(100000,2000000000),18)
    train=blocks[:3];duel=blocks[3:7];hold=blocks[7:11];final=blocks[11:15];package_seed=blocks[15]
    pool=candidates(n,study_seed);history=[]
    def ev(p,seeds,fams,label,steps=720,kind='v3',path=None):
        r=evaluate(p,seeds,fams,steps,workers,kind,path);save(out/(label+'.json'),r);print(label,json.dumps(r['metrics']),flush=True);return r
    stages=[
        ('A',train[:1],('starter','incumbent'),240,max(8,n//2)),
        ('B',train[:2],('starter','incumbent','early_sell','expansion'),480,max(4,n//4)),
        ('C',train,SUITE,720,max(2,min(3,n//6))),
    ]
    frozen=None
    for stage,seeds,fams,steps,keep in stages:
        ranked=[]
        for p in pool:
            r=ev(p,seeds,fams,stage+'-'+digest(p)[:10],steps);ranked.append((r['metrics']['objective'],p,r))
        ranked.sort(key=lambda x:(x[0],digest(x[1])),reverse=True);history.append(dict(stage=stage,ranking=[dict(params=p,metrics=r['metrics']) for _,p,r in ranked]))
        pool=[p for _,p,_ in ranked[:keep]]
        if stage=='C':frozen=ranked[0][2]
    best=pool[0]
    d=ev(best,duel,('incumbent',),'D-duel');h=ev(best,hold,SUITE,'E-holdout');bh=ev(best,hold,SUITE,'E-baseline',kind='incumbent')
    f=ev(best,final,SUITE,'F-final');bf=ev(best,final,SUITE,'F-baseline',kind='incumbent')
    package=build(best,out/'candidate-main.py');runtime=check(out/'candidate-main.py')
    packaged=ev(best,[package_seed],('incumbent',),'package-check',path=out/'candidate-main.py');source=ev(best,[package_seed],('incumbent',),'source-check')
    keys=('margin','valid','statuses','terminal_unsold_units','final_unlocked_quadrants','final_animals')
    runtime['episode_equivalence']='PASS' if all(all(a.get(k)==b.get(k) for k in keys) for a,b in zip(packaged['rows'],source['rows'])) and all(r['valid'] for r in packaged['rows']) else 'FAIL'
    decision=gate(frozen,d,h,f,bh,bf,runtime)
    result=dict(best_params=best,stages=history,promotion=decision,runtime=runtime,package=package,duel=d['metrics'],holdout=h['metrics'],final=f['metrics'],
                baseline_holdout=bh['metrics'],baseline_final=bf['metrics'],provenance=frozen['provenance'],study_seed=study_seed,
                seed_sets=dict(train=train,duel=duel,holdout=hold,final=final,package=[package_seed]),submission_performed=False)
    save(out/'search.json',result)
    if decision['pass_gate']:save(out/'champion_v5.json',dict(params=best,evidence=result))
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--candidates',type=int,default=20);ap.add_argument('--workers',type=int,default=0);ap.add_argument('--study-seed',type=int,default=5059);a=ap.parse_args()
    if not 4<=a.candidates<=64:ap.error('candidates 4..64')
    run(a.output,a.candidates,a.workers,a.study_seed)
