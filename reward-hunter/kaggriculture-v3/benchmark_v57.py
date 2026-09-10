"""V5.7 canonical evaluator for kaggle-environments 1.32.7.

It preserves the V5 promotion metrics and adds lightweight economy telemetry so failed rounds
can teach the next search *why* capital underperformed: timing, crop/animal exposure, price
capture, land/hiring intensity and cash-path shape.
"""
import contextlib, hashlib, importlib, io, json, math, os, statistics, subprocess, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from policy import validate_params
from policy_v57 import make_v57
from opponents import opponent, SUITE

HERE=Path(__file__).resolve().parent
PINNED_VERSION='1.32.7'
BASE_PRICE={'WHEAT':25,'CARROT':35,'TOMATO':60,'STRAWBERRY':120,'MELON':250,'EGG':50,'MILK':160,'WOOL':200,'FERTILIZER':100}


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def provenance(params):
    import kaggle_environments
    engine=importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
    return dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),code_hash=digest(files),parameter_hash=digest(params),
                simulator_version=kaggle_environments.__version__,simulator_hash=hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
                source_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=HERE,text=True).strip()))


def cpu_limit(requested=0):
    n=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else (os.cpu_count() or 1)
    try:
        q,p=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if q!='max':n=min(n,max(1,math.floor(int(q)/int(p))))
    except Exception:pass
    return max(1,min(requested or 4,n,8))


def _safe_step(obs,configuration=None):
    cfg=configuration or {};turns=int(cfg.get('turnsPerDay',24) or 24)
    return int(obs.get('day',0) or 0)*turns+int(obs.get('hour',0) or 0)


def _composition(tiles):
    crops={'WHEAT':0,'CARROT':0,'TOMATO':0,'STRAWBERRY':0,'MELON':0};animals={'GOOSE':0,'COW':0,'SHEEP':0}
    for row in tiles:
        for t in row:
            if not isinstance(t,dict):continue
            if t.get('kind')=='PLANT' and t.get('crop') in crops:crops[t['crop']]+=1
            if t.get('animal') in animals:animals[t['animal']]+=1
    return crops,animals


def _blank_tracker():
    return dict(
        full_unlock_step=None,max_unlocked=1,peak_productive=0.,full_peak_productive=0.,peak_animals=0,
        min_money=None,peak_money=None,money_checkpoints={},
        crop_turns={'WHEAT':0,'CARROT':0,'TOMATO':0,'STRAWBERRY':0,'MELON':0},
        animal_turns={'GOOSE':0,'COW':0,'SHEEP':0},
        sell_units={k:0 for k in BASE_PRICE},sell_value={k:0. for k in BASE_PRICE},sell_scarcity={k:0. for k in BASE_PRICE},
        buy_seed_units={'WHEAT':0,'CARROT':0,'TOMATO':0,'STRAWBERRY':0,'MELON':0},
        buy_animals={'GOOSE':0,'COW':0,'SHEEP':0},buy_land=0,hires=0,buy_wheat=0,buy_fertilizer=0,
    )


def _track(agent,tracker):
    def wrapped(obs,configuration=None):
        me=obs['farms'][obs['player']];tiles=me['tiles'];unlocked=len(me.get('unlocked_quadrants',['NW']))
        owned=sum(t!='LOCKED' for r in tiles for t in r);plants=sum(isinstance(t,dict) and t.get('kind')=='PLANT' for r in tiles for t in r)
        structures=sum(isinstance(t,dict) and t.get('kind') in ('COOP','PASTURE') for r in tiles for t in r);animals=sum(isinstance(t,dict) and 'animal' in t for r in tiles for t in r)
        productive=(plants+structures)/max(1,owned);tracker['max_unlocked']=max(tracker['max_unlocked'],unlocked);tracker['peak_productive']=max(tracker['peak_productive'],productive);tracker['peak_animals']=max(tracker['peak_animals'],animals)
        if unlocked>=4:
            if tracker['full_unlock_step'] is None:tracker['full_unlock_step']=_safe_step(obs,configuration)
            tracker['full_peak_productive']=max(tracker['full_peak_productive'],productive)
        money=float(me.get('money',0) or 0);tracker['min_money']=money if tracker['min_money'] is None else min(tracker['min_money'],money);tracker['peak_money']=money if tracker['peak_money'] is None else max(tracker['peak_money'],money)
        day=int(obs.get('day',0) or 0)
        if day in (5,10,15,20,25,29) and day not in tracker['money_checkpoints']:tracker['money_checkpoints'][day]=money
        crops,animal_counts=_composition(tiles)
        for k,v in crops.items():tracker['crop_turns'][k]+=v
        for k,v in animal_counts.items():tracker['animal_turns'][k]+=v
        action=agent(obs,configuration) if configuration is not None else agent(obs)
        market=action.get('market',[]) if isinstance(action,dict) else []
        prices=(obs.get('market',{}) or {}).get('prices',{});inventory=(obs.get('market',{}) or {}).get('inventory',{})
        for order in market if isinstance(market,list) else []:
            if not isinstance(order,list) or not order:continue
            op=order[0]
            if op=='SELL' and len(order)>=3 and order[1] in BASE_PRICE:
                item=order[1];q=max(0,int(order[2] or 0));price=float(prices.get(item,BASE_PRICE[item]) or BASE_PRICE[item]);scar=max(0.,10000.-float(inventory.get(item,10000) or 10000))
                tracker['sell_units'][item]+=q;tracker['sell_value'][item]+=q*price;tracker['sell_scarcity'][item]+=q*scar
            elif op=='BUY_SEED' and len(order)>=3 and order[1] in tracker['buy_seed_units']:tracker['buy_seed_units'][order[1]]+=max(0,int(order[2] or 0))
            elif op=='BUY_ANIMAL' and len(order)>=3 and order[1] in tracker['buy_animals']:tracker['buy_animals'][order[1]]+=max(0,int(order[2] or 0))
            elif op=='BUY_LAND':tracker['buy_land']+=1
            elif op=='HIRE':tracker['hires']+=1
            elif op=='BUY_PRODUCT' and len(order)>=3:
                if order[1]=='WHEAT':tracker['buy_wheat']+=max(0,int(order[2] or 0))
                elif order[1]=='FERTILIZER':tracker['buy_fertilizer']+=max(0,int(order[2] or 0))
        return action
    return wrapped


def _two_arg_adapter(agent):
    def wrapped(obs, configuration=None):return agent(obs)
    return wrapped


def _tracker_payload(tracker,steps):
    turns=max(1,int(steps));sell_units=tracker['sell_units'];total_units=sum(sell_units.values());total_value=sum(tracker['sell_value'].values());base_value=sum(BASE_PRICE[k]*v for k,v in sell_units.items())
    capture=(total_value/base_value) if base_value>0 else 0.0
    mean_scarcity=(sum(tracker['sell_scarcity'].values())/total_units) if total_units>0 else 0.0
    return dict(
        min_money=tracker['min_money'],peak_money=tracker['peak_money'],money_checkpoints={str(k):v for k,v in sorted(tracker['money_checkpoints'].items())},
        crop_exposure={k:v/turns for k,v in tracker['crop_turns'].items()},animal_exposure={k:v/turns for k,v in tracker['animal_turns'].items()},
        planned_sell_units=dict(sell_units),planned_sell_capture_ratio=capture,planned_sell_mean_scarcity=mean_scarcity,
        planned_buy_seed_units=dict(tracker['buy_seed_units']),planned_buy_animals=dict(tracker['buy_animals']),planned_buy_land=tracker['buy_land'],planned_hires=tracker['hires'],
        planned_buy_wheat=tracker['buy_wheat'],planned_buy_fertilizer=tracker['buy_fertilizer'],
    )


def play(job):
    params,family,seed,seat,steps,kind,agent_path=job
    from kaggle_environments import make
    engine=importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    original=engine._apply_unit_action;counts=[dict(actions=0,moves=0,passes=0,noops=0),dict(actions=0,moves=0,passes=0,noops=0)];player=[-1]
    def audited(farm,private,idx,action,*args,**kwargs):
        if idx==0:player[0]=(player[0]+1)%2
        c=counts[player[0]];c['actions']+=1;op=action[0] if isinstance(action,list) and action else 'INVALID';c['moves']+=op in ('NORTH','SOUTH','EAST','WEST');c['passes']+=op=='PASS'
        pos=engine._farmer_position(farm,idx);before=repr((pos,farm['tiles'][pos[1]][pos[0]],private)) if pos is not None and op!='PASS' else None
        out=original(farm,private,idx,action,*args,**kwargs);pos2=engine._farmer_position(farm,idx);after=repr((pos2,farm['tiles'][pos2[1]][pos2[0]],private)) if pos2 is not None and op!='PASS' else None
        if op!='PASS' and before==after:c['noops']+=1
        return out
    engine._apply_unit_action=audited;tracker=_blank_tracker()
    row=dict(seed=seed,seat=seat,opponent=family,steps=steps,kind=kind,valid=False,error=None)
    try:
        base=opponent('incumbent') if kind=='incumbent' else make_v57(params)
        if kind=='incumbent':base=_two_arg_adapter(base)
        candidate=agent_path if agent_path else _track(base,tracker);agents=[candidate,opponent(family)] if seat==0 else [opponent(family),candidate]
        env=make('kaggriculture',configuration={'seed':int(seed),'episodeSteps':steps},debug=True)
        with contextlib.redirect_stdout(io.StringIO()) as cap:env.run(agents)
        statuses=[str(s.status) for s in env.state];row['statuses']=statuses;row['valid']=statuses==['DONE','DONE']
        if not row['valid']:row['error']=cap.getvalue()[-4000:]
        farms=env.state[0].observation.farms;mine=farms[seat];private=env.state[seat].observation.private
        row['candidate_money']=float(mine['money']);row['opponent_money']=float(farms[1-seat]['money']);row['margin']=row['candidate_money']-row['opponent_money'];row['efficiency']=counts[seat]
        row['terminal_unsold_units']=sum(private['shed'].values())+sum(sum(i.values()) for i in private['inventories']);tiles=mine['tiles'];row['final_unlocked_quadrants']=len(mine.get('unlocked_quadrants',['NW']))
        row['final_plants']=sum(isinstance(t,dict) and t.get('kind')=='PLANT' for r in tiles for t in r);row['final_animals']=sum(isinstance(t,dict) and 'animal' in t for r in tiles for t in r);row['final_structures']=sum(isinstance(t,dict) and t.get('kind') in ('COOP','PASTURE') for r in tiles for t in r)
        row['full_unlock_step']=tracker['full_unlock_step'];row['full_unlock_day']=tracker['full_unlock_step']/24 if tracker['full_unlock_step'] is not None else None;row['peak_productive_utilization']=tracker['peak_productive'];row['full_farm_peak_productive_utilization']=tracker['full_peak_productive'];row['peak_animals']=tracker['peak_animals']
        row['economy']=_tracker_payload(tracker,steps)
    except Exception as e:
        row['valid']=False;row['error']=f'{type(e).__name__}: {e}'
    finally:engine._apply_unit_action=original
    return row


def _mean_map(valid,path):
    keys=set()
    for r in valid:
        d=r.get('economy',{}).get(path,{})
        if isinstance(d,dict):keys.update(d)
    return {k:statistics.mean(float(r.get('economy',{}).get(path,{}).get(k,0) or 0) for r in valid) for k in sorted(keys)}


def summary(rows):
    n=len(rows);valid=[r for r in rows if r.get('valid')]
    if not valid:return dict(games=n,valid_games=0,win_rate=0,mean_margin=None,p20_margin=None,worst_margin=None,objective=-1e9)
    margins=sorted(r['margin'] for r in valid);wins=sum(x>0 for x in margins);ties=sum(x==0 for x in margins);mean=statistics.mean(margins);p20=margins[int(.2*(len(margins)-1))];worst=margins[0]
    actions=sum(r['efficiency']['actions'] for r in valid);noop=sum(r['efficiency']['noops'] for r in valid)/max(1,actions);waste=sum(r['efficiency']['moves']+r['efficiency']['passes'] for r in valid)/max(1,actions);tail=sum(m<-5000 for m in margins)/n
    unlock=sum(r['final_unlocked_quadrants']>=4 for r in valid)/n;days=[r['full_unlock_day'] if r['full_unlock_day'] is not None else r['steps']/24+1 for r in valid];productive=statistics.mean(r['full_farm_peak_productive_utilization'] for r in valid);animals=statistics.mean(r['peak_animals'] for r in valid)
    objective=(600*(wins+.5*ties)/n+150*math.tanh(mean/6000)+110*math.tanh(p20/6000)+45*math.tanh(worst/6000)-2200*(n-len(valid))/n-180*noop-22*waste-180*tail+60*unlock+30*productive+8*min(1,animals/8)-2.0*statistics.mean(days))
    checkpoints={}
    for day in ('5','10','15','20','25','29'):
        vals=[r.get('economy',{}).get('money_checkpoints',{}).get(day) for r in valid]
        vals=[float(v) for v in vals if v is not None]
        checkpoints[day]=statistics.mean(vals) if vals else None
    return dict(games=n,valid_games=len(valid),wins=wins,ties=ties,win_rate=wins/n,mean_margin=mean,median_margin=statistics.median(margins),p20_margin=p20,worst_margin=worst,mean_money=statistics.mean(r['candidate_money'] for r in valid),noop_rate=noop,movement_idle_rate=waste,catastrophic_rate=tail,objective=objective,full_unlock_rate=unlock,mean_full_unlock_day=statistics.mean(days),mean_full_farm_peak_productive_utilization=productive,mean_peak_animals=animals,mean_terminal_unsold_units=statistics.mean(r['terminal_unsold_units'] for r in valid),
                mean_min_money=statistics.mean(float(r.get('economy',{}).get('min_money',0) or 0) for r in valid),mean_peak_money=statistics.mean(float(r.get('economy',{}).get('peak_money',0) or 0) for r in valid),mean_money_checkpoints=checkpoints,
                mean_planned_sell_capture_ratio=statistics.mean(float(r.get('economy',{}).get('planned_sell_capture_ratio',0) or 0) for r in valid),mean_planned_sell_scarcity=statistics.mean(float(r.get('economy',{}).get('planned_sell_mean_scarcity',0) or 0) for r in valid),
                mean_crop_exposure=_mean_map(valid,'crop_exposure'),mean_animal_exposure=_mean_map(valid,'animal_exposure'),mean_sell_units=_mean_map(valid,'planned_sell_units'),mean_buy_seed_units=_mean_map(valid,'planned_buy_seed_units'),mean_buy_animals=_mean_map(valid,'planned_buy_animals'),
                mean_planned_buy_land=statistics.mean(float(r.get('economy',{}).get('planned_buy_land',0) or 0) for r in valid),mean_planned_hires=statistics.mean(float(r.get('economy',{}).get('planned_hires',0) or 0) for r in valid),mean_planned_buy_wheat=statistics.mean(float(r.get('economy',{}).get('planned_buy_wheat',0) or 0) for r in valid),mean_planned_buy_fertilizer=statistics.mean(float(r.get('economy',{}).get('planned_buy_fertilizer',0) or 0) for r in valid))


def evaluate(params=None,seeds=(101,),families=SUITE,steps=720,workers=0,kind='v3',agent_path=None):
    params=validate_params(params);prov=provenance(params)
    if prov['simulator_version']!=PINNED_VERSION:raise ValueError(f"Need kaggle-environments {PINNED_VERSION}, got {prov['simulator_version']}")
    seeds=tuple(seeds);families=tuple(families);jobs=[(params,f,s,seat,steps,kind,str(agent_path) if agent_path else None) for f in families for s in seeds for seat in (0,1)];w=cpu_limit(workers)
    rows=list(map(play,jobs)) if w==1 else list(ProcessPoolExecutor(max_workers=w).map(play,jobs))
    return dict(metrics=summary(rows),by_family={f:summary([r for r in rows if r['opponent']==f]) for f in families},by_seat={str(s):summary([r for r in rows if r['seat']==s]) for s in (0,1)},rows=rows,seeds=list(seeds),families=list(families),steps=steps,workers=w,params=params,kind=kind,provenance=prov,timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))


def save(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
