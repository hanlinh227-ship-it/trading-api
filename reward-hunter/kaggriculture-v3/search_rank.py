"""V5.5 profit-first ladder search with continuous potential adaptation."""
import argparse,json,random
from pathlib import Path
from benchmark_v5 import evaluate,save,digest
from policy import V3_DEFAULT,validate_params
from opponents import SUITE
from package_submission import build
from raw_exec_test import check
from promotion_rank import gate
from learning_rank import (
    load_state,save_state,observe_evaluation,best_learned_patch,learned_variants,
    adaptive_plan,champion_params,record_round,weak_families,
)

META_KEYS={'cow_max','sheep_max','goose_max','target_hands','sell_batch','land_target_quadrants'}

CHOICES={
    'distance_cost':(5.,6.,7.,8.,9.),'target_hands':(9,10,11,12,13),'crop_mode':('roi','demand','fast_cash','balanced'),
    'expansion_mode':('balanced','fast','max'),'land_buffer':(40,80,120,180,260),'land_target_quadrants':(3,3,3,4),
    'fill_target':(.68,.75,.82,.88),'fill_priority':(70.,82.,92.,105.),'seed_scale':(1.0,1.25,1.45,1.7),
    'herd_mode':('none','cow_sheep','cow_sheep','dynamic'),'cow_max':(5,6,7,8,9,10),'sheep_max':(0,3,4,5,6),
    'goose_max':(0,0,1,2,3),'livestock_start_day':(0,0,1,2),'livestock_cash_buffer':(350,500,650,800),
    'animal_roi_floor':(0.0,.10,.20,.35,.50),'feed_carry':(4,5,6,8),'drop_at':(6,8,10),
    'fertilizer_mode':('herd_only','adaptive','adaptive'),'fertilizer_reserve':(0,1,2,3),'sell_batch':(4,5,6,8,10),
}


def load_meta_prior(path):
    if not path:return None
    raw=json.loads(Path(path).read_text())
    src=raw.get('summary',raw).get('recommended_params',{}) if isinstance(raw,dict) else {}
    patch={k:src[k] for k in META_KEYS if k in src}
    if any(int(patch.get(k,0) or 0)>0 for k in ('cow_max','sheep_max','goose_max')):patch['herd_mode']='dynamic'
    if not patch:return None
    p=dict(V3_DEFAULT);p.update(patch);return validate_params(p)


def candidates(n,seed,meta_prior=None,learning_state=None,plan=None):
    rng=random.Random(seed);base=dict(V3_DEFAULT);pool=[];plan=plan or {}
    presets=[
        {'land_target_quadrants':4,'herd_mode':'cow_sheep','cow_max':6,'sheep_max':4,'target_hands':11,'sell_batch':5,'livestock_start_day':2},
        {'land_target_quadrants':3,'herd_mode':'cow_sheep','cow_max':9,'sheep_max':4,'goose_max':0,'target_hands':10,'livestock_start_day':0,'sell_batch':5,'fertilizer_reserve':1,'animal_roi_floor':.10},
        {'land_target_quadrants':3,'herd_mode':'cow_sheep','cow_max':9,'sheep_max':5,'goose_max':0,'target_hands':9,'livestock_start_day':0,'sell_batch':6,'fertilizer_reserve':1,'animal_roi_floor':.05},
        {'land_target_quadrants':3,'herd_mode':'cow_sheep','cow_max':8,'sheep_max':4,'target_hands':10,'livestock_start_day':0,'land_buffer':80,'sell_batch':5,'animal_roi_floor':.15},
        {'land_target_quadrants':3,'herd_mode':'cow_sheep','cow_max':7,'sheep_max':4,'target_hands':10,'livestock_start_day':1,'crop_mode':'fast_cash','sell_batch':5,'fertilizer_reserve':1},
        {'land_target_quadrants':3,'herd_mode':'dynamic','cow_max':8,'sheep_max':5,'goose_max':2,'target_hands':10,'livestock_start_day':0,'animal_roi_floor':.35,'sell_batch':5},
        {'land_target_quadrants':3,'herd_mode':'dynamic','cow_max':6,'sheep_max':4,'goose_max':3,'target_hands':9,'crop_mode':'demand','animal_roi_floor':.30,'fertilizer_reserve':0},
        {'land_target_quadrants':3,'herd_mode':'none','fertilizer_mode':'off','crop_mode':'roi','target_hands':9,'sell_batch':6},
        {'land_target_quadrants':4,'herd_mode':'none','fertilizer_mode':'off','crop_mode':'roi','target_hands':11,'sell_batch':6},
        {'land_target_quadrants':4,'herd_mode':'cow_sheep','cow_max':9,'sheep_max':4,'target_hands':12,'livestock_start_day':0,'animal_roi_floor':.10,'fertilizer_reserve':1},
        {'land_target_quadrants':3,'herd_mode':'cow_sheep','cow_max':10,'sheep_max':3,'target_hands':10,'livestock_start_day':0,'animal_roi_floor':0.0,'fertilizer_reserve':0},
        {'land_target_quadrants':3,'herd_mode':'cow_sheep','cow_max':6,'sheep_max':6,'target_hands':10,'livestock_start_day':0,'animal_roi_floor':.15,'fertilizer_reserve':2},
    ]
    # Long-lived elites are evaluated first so a good lineage cannot disappear because of one noisy round.
    if learning_state:
        for elite in reversed(champion_params(learning_state,limit=4)):
            presets.insert(0,elite)
    if meta_prior:
        patch={k:v for k,v in meta_prior.items() if k in base};patch.setdefault('land_target_quadrants',3);presets.insert(1,patch)
    if learning_state and int(learning_state.get('matches',0) or 0)>=8:
        patch=best_learned_patch(learning_state,CHOICES,min_samples=4,focus_families=plan.get('focus_families'))
        if patch:
            learned=dict(base);learned.update(patch);presets.insert(1,learned)
    for patch in presets:
        p=dict(base);p.update(patch);p=validate_params(p)
        if p not in pool:pool.append(p)
        if len(pool)>=n:return pool[:n]
    keys=tuple(CHOICES)
    while len(pool)<n:
        p=dict(rng.choice(pool));k=rng.choice(keys);p[k]=rng.choice(CHOICES[k]);p=validate_params(p)
        if p not in pool:pool.append(p)
    return pool


def run(out,n=24,workers=0,study_seed=7549,meta_prior_path=None,learning_state_path=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'search.json').exists():raise ValueError('fresh output directory required')
    blocks=random.Random(study_seed).sample(range(100000,2000000000),18)
    train=blocks[:3];duel=blocks[3:7];hold=blocks[7:11];final=blocks[11:15];package_seed=blocks[15]
    state=load_state(learning_state_path)
    plan=adaptive_plan(state,n);effective_n=plan['candidate_count']
    meta_prior=load_meta_prior(meta_prior_path);pool=candidates(effective_n,study_seed,meta_prior,state,plan);history=[];rng=random.Random(study_seed ^ 0x54A7)
    print('POTENTIAL_PLAN',json.dumps(plan,sort_keys=True),flush=True)

    def ev(p,seeds,fams,label,steps=720,kind='v3',path=None,learn=True):
        nonlocal state
        r=evaluate(p,seeds,fams,steps,workers,kind,path);save(out/(label+'.json'),r);print(label,json.dumps(r['metrics']),flush=True)
        if learn and kind=='v3' and path is None:
            state=observe_evaluation(state,p,r,label);save_state(learning_state_path,state)
            print('LEARNING',json.dumps({'matches':state['matches'],'wins':state['wins'],'losses':state['losses'],'ties':state['ties'],'invalid':state['invalid'],'weak_families':weak_families(state),'last_label':label},sort_keys=True),flush=True)
        return r

    stages=[
        ('A',train[:1],('starter','incumbent'),240,max(8,effective_n//3)),
        ('B',train[:2],('starter','incumbent','early_sell','expansion','grains'),480,max(4,effective_n//6)),
        ('C',train,SUITE,720,max(2,min(6,effective_n//8))),
    ]
    frozen=None
    for stage,seeds,fams,steps,keep in stages:
        ranked=[]
        for p in pool:
            r=ev(p,seeds,fams,stage+'-'+digest(p)[:10],steps);ranked.append((r['metrics']['objective'],p,r))
        ranked.sort(key=lambda x:(x[0],digest(x[1])),reverse=True)
        history.append(dict(stage=stage,ranking=[dict(params=p,metrics=r['metrics']) for _,p,r in ranked],learning_matches=state['matches']))
        if stage=='C':
            pool=[p for _,p,_ in ranked[:keep]];frozen=ranked[0][2]
        else:
            elite_count=max(2,min(keep,(keep+1)//2));elites=[p for _,p,_ in ranked[:elite_count]]
            pool=learned_variants(
                elites,state,CHOICES,validate_params,rng,keep,
                focus_families=plan.get('focus_families'),
                exploration=plan.get('exploration',.18),
                mutation_steps=plan.get('mutation_steps',1),
            )
            for _,p,_ in ranked:
                if len(pool)>=keep:break
                if p not in pool:pool.append(p)
    best=pool[0]
    d=ev(best,duel,('incumbent',),'D-duel');h=ev(best,hold,SUITE,'E-holdout');bh=ev(best,hold,SUITE,'E-baseline',kind='incumbent',learn=False)
    f=ev(best,final,SUITE,'F-final');bf=ev(best,final,SUITE,'F-baseline',kind='incumbent',learn=False)
    package=build(best,out/'candidate-main.py');runtime=check(out/'candidate-main.py')
    packaged=ev(best,[package_seed],('incumbent',),'package-check',path=out/'candidate-main.py',learn=False);source=ev(best,[package_seed],('incumbent',),'source-check',learn=False)
    keys=('margin','valid','statuses','terminal_unsold_units','final_unlocked_quadrants','final_animals')
    runtime['episode_equivalence']='PASS' if all(all(a.get(k)==b.get(k) for k in keys) for a,b in zip(packaged['rows'],source['rows'])) and all(r['valid'] for r in packaged['rows']) else 'FAIL'
    decision=gate(frozen,d,h,f,bh,bf,runtime)
    state=record_round(state,best,d['metrics'],h['metrics'],f['metrics'],decision,label='run-'+str(study_seed))
    next_plan=adaptive_plan(state,n)
    learned_patch=best_learned_patch(state,CHOICES,min_samples=4,focus_families=next_plan.get('focus_families'))
    result=dict(
        best_params=best,stages=history,promotion=decision,runtime=runtime,package=package,
        duel=d['metrics'],holdout=h['metrics'],final=f['metrics'],baseline_holdout=bh['metrics'],baseline_final=bf['metrics'],
        provenance=frozen['provenance'],study_seed=study_seed,
        seed_sets=dict(train=train,duel=duel,holdout=hold,final=final,package=[package_seed]),
        submission_performed=False,public_meta_prior=meta_prior or 'built-in public high-Elo livestock priors',
        lane='continuous-potential-rank-climb',round_plan=plan,next_round=next_plan,
        learning=dict(matches=state['matches'],wins=state['wins'],losses=state['losses'],ties=state['ties'],invalid=state['invalid'],weak_families=weak_families(state),best_learned_patch=learned_patch,champion_count=len(state.get('champions',[])),control=state.get('control',{}),state_path=str(learning_state_path or 'ephemeral')),
    )
    save(out/'search.json',result);save_state(learning_state_path,state)
    if decision['pass_gate']:save(out/'PROMOTION_READY_rank.json',dict(params=best,evidence=result))
    print('NEXT_POTENTIAL_PLAN',json.dumps(next_plan,sort_keys=True),flush=True)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--candidates',type=int,default=24);ap.add_argument('--workers',type=int,default=0);ap.add_argument('--study-seed',type=int,default=7549);ap.add_argument('--meta-prior');ap.add_argument('--learning-state');a=ap.parse_args()
    if not 8<=a.candidates<=64:ap.error('candidates 8..64')
    run(a.output,a.candidates,a.workers,a.study_seed,a.meta_prior,a.learning_state)
