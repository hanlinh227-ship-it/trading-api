"""V5.7 profit-first ladder search with monotonic capital and agro-economic learning."""
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
    adaptive_plan,champion_params,weak_families,
)
from monotonic_rank import (
    accepted_params,is_taboo,failure_penalty,decide_and_record,
    record_monotonic_round,summary as monotonic_summary,
)
from agro_reasoning import (
    PUBLIC_META_PRIORS,observe_agro_evaluation,agro_penalty,agro_quality_score,
    recovery_patches,summary as agro_summary,
)

META_KEYS={'cow_max','sheep_max','goose_max','target_hands','sell_batch','land_target_quadrants'}
# Stable regression panel. Search/holdout seeds are always >=100000, so these fixed seeds are
# never part of candidate selection. They provide a comparable capital high-water mark across rounds.
MONOTONIC_SEEDS=(7319,29077)
MONOTONIC_FAMILIES=SUITE

CHOICES={
    'distance_cost':(5.,6.,7.,8.,9.),'target_hands':(9,10,11,12,13),'crop_mode':('roi','demand','fast_cash','balanced','grains'),
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
    rng=random.Random(seed);base=dict(V3_DEFAULT);pool=[];plan=plan or {};learning_state=learning_state or {}
    # Historical public top patterns are only priors.  Failure-derived recovery hypotheses and
    # our accepted champion are inserted ahead of them, so the system becomes increasingly personal.
    presets=list(PUBLIC_META_PRIORS)+[
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

    def add(p):
        p=validate_params(dict(p))
        if is_taboo(learning_state,p):return False
        if p in pool:return False
        pool.append(p);return True

    accepted=accepted_params(learning_state)
    if accepted:add(accepted)
    for elite in champion_params(learning_state,limit=4):add(elite)
    if meta_prior:
        patch={k:v for k,v in meta_prior.items() if k in base};patch.setdefault('land_target_quadrants',3)
        p=dict(base);p.update(patch);add(p)
    if learning_state and int(learning_state.get('matches',0) or 0)>=8:
        patch=best_learned_patch(learning_state,CHOICES,min_samples=4,focus_families=plan.get('focus_families'))
        if patch:
            learned=dict(base);learned.update(patch);add(learned)
    # Mistakes are converted into new hypotheses before generic/public presets are tried again.
    for recovery in recovery_patches(learning_state,accepted or base,limit=max(4,min(8,n//3))):
        add(recovery)
    for patch in presets:
        p=dict(base);p.update(patch);add(p)
        if len(pool)>=n:return pool[:n]

    keys=tuple(CHOICES);attempts=0
    while len(pool)<n and attempts<n*250:
        attempts+=1
        parent=dict(rng.choice(pool or [validate_params(base)]))
        edits=max(1,min(4,int(plan.get('mutation_steps',1))))
        for _ in range(1+rng.randrange(edits)):
            k=rng.choice(keys);parent[k]=rng.choice(CHOICES[k])
        add(parent)
    if len(pool)<n:
        raise RuntimeError('unable to build non-taboo candidate pool')
    return pool[:n]


def _repeat_panel(metrics):
    # monotonic_rank expects three blocks. Feeding the same fixed regression panel into all three
    # preserves its strict per-block checks without tripling compute.
    return {'duel':metrics,'holdout':metrics,'final':metrics}


def run(out,n=24,workers=0,study_seed=7549,meta_prior_path=None,learning_state_path=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'search.json').exists():raise ValueError('fresh output directory required')
    blocks=random.Random(study_seed).sample(range(100000,2000000000),18)
    train=blocks[:3];duel=blocks[3:7];hold=blocks[7:11];final=blocks[11:15];package_seed=blocks[15]
    state=load_state(learning_state_path)
    plan=adaptive_plan(state,n);effective_n=plan['candidate_count']
    monotonic_base=accepted_params(state)
    if monotonic_base is None:
        archived=champion_params(state,limit=1)
        monotonic_base=archived[0] if archived else None
    meta_prior=load_meta_prior(meta_prior_path);pool=candidates(effective_n,study_seed,meta_prior,state,plan);history=[];rng=random.Random(study_seed ^ 0x54A7)
    print('POTENTIAL_PLAN',json.dumps(plan,sort_keys=True),flush=True)
    print('MONOTONIC_START',json.dumps(monotonic_summary(state),sort_keys=True),flush=True)
    print('AGRO_START',json.dumps(agro_summary(state),sort_keys=True),flush=True)

    def ev(p,seeds,fams,label,steps=720,kind='v3',path=None,learn=True):
        nonlocal state
        r=evaluate(p,seeds,fams,steps,workers,kind,path);save(out/(label+'.json'),r);print(label,json.dumps(r['metrics']),flush=True)
        if learn and kind=='v3' and path is None:
            state=observe_evaluation(state,p,r,label)
            state=observe_agro_evaluation(state,p,r,label)
            save_state(learning_state_path,state)
            print('LEARNING',json.dumps({'matches':state['matches'],'wins':state['wins'],'losses':state['losses'],'ties':state['ties'],'invalid':state['invalid'],'weak_families':weak_families(state),'agro':agro_summary(state),'last_label':label},sort_keys=True),flush=True)
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
            r=ev(p,seeds,fams,stage+'-'+digest(p)[:10],steps)
            penalty=failure_penalty(state,p)
            agro_p=agro_penalty(state,p)
            agro_q=agro_quality_score(r,p)
            rank_score=r['metrics']['objective']+0.8*agro_q-18.0*min(4.0,penalty)-12.0*min(4.0,agro_p)
            ranked.append((rank_score,p,r,penalty,agro_p,agro_q))
        ranked.sort(key=lambda x:(x[0],digest(x[1])),reverse=True)
        history.append(dict(stage=stage,ranking=[dict(params=p,metrics=r['metrics'],failure_penalty=pen,agro_penalty=ap,agro_quality=aq,rank_score=score) for score,p,r,pen,ap,aq in ranked],learning_matches=state['matches']))
        if stage=='C':
            pool=[p for _,p,_,_,_,_ in ranked[:keep]];frozen=ranked[0][2]
        else:
            elite_count=max(2,min(keep,(keep+1)//2));elites=[p for _,p,_,_,_,_ in ranked[:elite_count]]
            generated=learned_variants(
                elites,state,CHOICES,validate_params,rng,max(keep*2,keep+4),
                focus_families=plan.get('focus_families'),
                exploration=plan.get('exploration',.18),
                mutation_steps=plan.get('mutation_steps',1),
            )
            new_pool=[]
            for p in sorted(generated,key=lambda q:(failure_penalty(state,q)+agro_penalty(state,q),digest(q))):
                if not is_taboo(state,p) and p not in new_pool:new_pool.append(p)
                if len(new_pool)>=keep:break
            for _,p,_,_,_,_ in ranked:
                if len(new_pool)>=keep:break
                if not is_taboo(state,p) and p not in new_pool:new_pool.append(p)
            pool=new_pool
            if not pool:raise RuntimeError('all stage survivors were taboo')

    best=pool[0]
    d=ev(best,duel,('incumbent',),'D-duel');h=ev(best,hold,SUITE,'E-holdout');bh=ev(best,hold,SUITE,'E-baseline',kind='incumbent',learn=False)
    f=ev(best,final,SUITE,'F-final');bf=ev(best,final,SUITE,'F-baseline',kind='incumbent',learn=False)

    capital=ev(best,MONOTONIC_SEEDS,MONOTONIC_FAMILIES,'G-capital-regression',learn=False)
    mono_incumbent=None;capital_incumbent=None
    if monotonic_base is not None and digest(monotonic_base)!=digest(best):
        capital_incumbent=ev(monotonic_base,MONOTONIC_SEEDS,MONOTONIC_FAMILIES,'G-capital-incumbent',learn=False)
        mono_incumbent=_repeat_panel(capital_incumbent['metrics'])
    state,mono_decision=decide_and_record(
        state,best,_repeat_panel(capital['metrics']),mono_incumbent,label='run-'+str(study_seed)
    )

    package=build(best,out/'candidate-main.py');runtime=check(out/'candidate-main.py')
    packaged=ev(best,[package_seed],('incumbent',),'package-check',path=out/'candidate-main.py',learn=False);source=ev(best,[package_seed],('incumbent',),'source-check',learn=False)
    keys=('margin','valid','statuses','terminal_unsold_units','final_unlocked_quadrants','final_animals')
    runtime['episode_equivalence']='PASS' if all(all(a.get(k)==b.get(k) for k in keys) for a,b in zip(packaged['rows'],source['rows'])) and all(r['valid'] for r in packaged['rows']) else 'FAIL'

    strict=gate(frozen,d,h,f,bh,bf,runtime)
    decision=dict(strict);decision['strict_pass_gate']=bool(strict.get('pass_gate',False));decision['monotonic']=mono_decision
    reasons=list(strict.get('reasons',[]))
    if not mono_decision.get('pass',False):
        reasons.append('monotonic_non_regression')
        reasons.extend('monotonic_'+str(x) for x in mono_decision.get('reasons',[]))
    decision['reasons']=list(dict.fromkeys(reasons))
    decision['pass_gate']=bool(strict.get('pass_gate',False) and mono_decision.get('pass',False))

    state=record_monotonic_round(state,best,d['metrics'],h['metrics'],f['metrics'],decision,mono_decision,label='run-'+str(study_seed))
    next_plan=adaptive_plan(state,n)
    learned_patch=best_learned_patch(state,CHOICES,min_samples=4,focus_families=next_plan.get('focus_families'))
    mono_state=monotonic_summary(state);agro_state=agro_summary(state)
    result=dict(
        best_params=best,stages=history,promotion=decision,runtime=runtime,package=package,
        duel=d['metrics'],holdout=h['metrics'],final=f['metrics'],baseline_holdout=bh['metrics'],baseline_final=bf['metrics'],
        capital_regression=capital['metrics'],capital_regression_incumbent=(capital_incumbent or {}).get('metrics'),
        capital_regression_seeds=list(MONOTONIC_SEEDS),capital_regression_families=list(MONOTONIC_FAMILIES),
        monotonic=mono_state,agro_reasoning=agro_state,
        provenance=frozen['provenance'],study_seed=study_seed,
        seed_sets=dict(train=train,duel=duel,holdout=hold,final=final,package=[package_seed]),
        submission_performed=False,public_meta_prior=meta_prior or 'public top patterns used as priors, never copied trajectories',
        lane='agro-economic-monotonic-continuous-potential-rank-climb',round_plan=plan,next_round=next_plan,
        learning=dict(matches=state['matches'],wins=state['wins'],losses=state['losses'],ties=state['ties'],invalid=state['invalid'],weak_families=weak_families(state),best_learned_patch=learned_patch,champion_count=len(state.get('champions',[])),control=state.get('control',{}),state_path=str(learning_state_path or 'ephemeral')),
    )
    save(out/'search.json',result);save_state(learning_state_path,state)
    if decision['pass_gate']:save(out/'PROMOTION_READY_rank.json',dict(params=best,evidence=result))
    print('MONOTONIC_DECISION',json.dumps(mono_decision,sort_keys=True),flush=True)
    print('MONOTONIC_STATE',json.dumps(mono_state,sort_keys=True),flush=True)
    print('AGRO_STATE',json.dumps(agro_state,sort_keys=True),flush=True)
    print('NEXT_POTENTIAL_PLAN',json.dumps(next_plan,sort_keys=True),flush=True)
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--candidates',type=int,default=24);ap.add_argument('--workers',type=int,default=0);ap.add_argument('--study-seed',type=int,default=7549);ap.add_argument('--meta-prior');ap.add_argument('--learning-state');a=ap.parse_args()
    if not 8<=a.candidates<=64:ap.error('candidates 8..64')
    run(a.output,a.candidates,a.workers,a.study_seed,a.meta_prior,a.learning_state)