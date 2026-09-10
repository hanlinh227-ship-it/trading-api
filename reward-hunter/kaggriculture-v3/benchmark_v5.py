"""V5 canonical evaluator for kaggle-environments 1.32.7 with mixed-farm telemetry."""
import contextlib, hashlib, importlib, io, json, math, os, statistics, subprocess, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from policy import make_v3, validate_params
from opponents import opponent, SUITE

HERE=Path(__file__).resolve().parent
PINNED_VERSION='1.32.7'


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def provenance(params):
    import kaggle_environments
    engine=importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
    return dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),
                code_hash=digest(files),parameter_hash=digest(params),simulator_version=kaggle_environments.__version__,
                simulator_hash=hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
                source_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=HERE,text=True).strip()))


def cpu_limit(requested=0):
    n=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else (os.cpu_count() or 1)
    try:
        q,p=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if q!='max': n=min(n,max(1,math.floor(int(q)/int(p))))
    except Exception: pass
    return max(1,min(requested or 4,n,8))


def _track(agent, tracker):
    def wrapped(obs, configuration=None):
        me=obs['farms'][obs['player']]; tiles=me['tiles']; unlocked=len(me.get('unlocked_quadrants',['NW']))
        owned=sum(t!='LOCKED' for r in tiles for t in r)
        plants=sum(isinstance(t,dict) and t.get('kind')=='PLANT' for r in tiles for t in r)
        structures=sum(isinstance(t,dict) and t.get('kind') in ('COOP','PASTURE') for r in tiles for t in r)
        animals=sum(isinstance(t,dict) and 'animal' in t for r in tiles for t in r)
        productive=(plants+structures)/max(1,owned)
        tracker['max_unlocked']=max(tracker['max_unlocked'],unlocked)
        tracker['peak_productive']=max(tracker['peak_productive'],productive)
        tracker['peak_animals']=max(tracker['peak_animals'],animals)
        if unlocked>=4:
            if tracker['full_unlock_step'] is None: tracker['full_unlock_step']=int(obs.get('step',0))
            tracker['full_peak_productive']=max(tracker['full_peak_productive'],productive)
        return agent(obs,configuration) if configuration is not None else agent(obs)
    return wrapped


def play(job):
    params,family,seed,seat,steps,kind,agent_path=job
    from kaggle_environments import make
    engine=importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    original=engine._apply_unit_action; counts=[dict(actions=0,moves=0,passes=0,noops=0),dict(actions=0,moves=0,passes=0,noops=0)]; player=[-1]
    def audited(farm,private,idx,action,*args,**kwargs):
        if idx==0: player[0]=(player[0]+1)%2
        c=counts[player[0]]; c['actions']+=1; op=action[0] if isinstance(action,list) and action else 'INVALID'
        c['moves']+=op in ('NORTH','SOUTH','EAST','WEST'); c['passes']+=op=='PASS'
        pos=engine._farmer_position(farm,idx)
        before=repr((pos,farm['tiles'][pos[1]][pos[0]],private)) if pos is not None and op!='PASS' else None
        out=original(farm,private,idx,action,*args,**kwargs)
        pos2=engine._farmer_position(farm,idx)
        after=repr((pos2,farm['tiles'][pos2[1]][pos2[0]],private)) if pos2 is not None and op!='PASS' else None
        if op!='PASS' and before==after: c['noops']+=1
        return out
    engine._apply_unit_action=audited
    tracker=dict(full_unlock_step=None,max_unlocked=1,peak_productive=0.,full_peak_productive=0.,peak_animals=0)
    row=dict(seed=seed,seat=seat,opponent=family,steps=steps,kind=kind,valid=False,error=None)
    try:
        base=opponent('incumbent') if kind=='incumbent' else make_v3(params)
        candidate=agent_path if agent_path else _track(base,tracker)
        agents=[candidate,opponent(family)] if seat==0 else [opponent(family),candidate]
        env=make('kaggriculture',configuration={'seed':int(seed),'episodeSteps':steps},debug=True)
        with contextlib.redirect_stdout(io.StringIO()) as cap: env.run(agents)
        statuses=[str(s.status) for s in env.state]; row['statuses']=statuses; row['valid']=statuses==['DONE','DONE']
        if not row['valid']: row['error']=cap.getvalue()[-4000:]
        farms=env.state[0].observation.farms; mine=farms[seat]; private=env.state[seat].observation.private
        row['candidate_money']=float(mine['money']); row['opponent_money']=float(farms[1-seat]['money']); row['margin']=row['candidate_money']-row['opponent_money']
        row['efficiency']=counts[seat]; row['terminal_unsold_units']=sum(private['shed'].values())+sum(sum(i.values()) for i in private['inventories'])
        tiles=mine['tiles']; row['final_unlocked_quadrants']=len(mine.get('unlocked_quadrants',['NW']))
        row['final_plants']=sum(isinstance(t,dict) and t.get('kind')=='PLANT' for r in tiles for t in r)
        row['final_animals']=sum(isinstance(t,dict) and 'animal' in t for r in tiles for t in r)
        row['final_structures']=sum(isinstance(t,dict) and t.get('kind') in ('COOP','PASTURE') for r in tiles for t in r)
        row['full_unlock_step']=tracker['full_unlock_step']; row['full_unlock_day']=tracker['full_unlock_step']/24 if tracker['full_unlock_step'] is not None else None
        row['peak_productive_utilization']=tracker['peak_productive']; row['full_farm_peak_productive_utilization']=tracker['full_peak_productive']; row['peak_animals']=tracker['peak_animals']
    except Exception as e:
        row['valid']=False; row['error']=f'{type(e).__name__}: {e}'
    finally: engine._apply_unit_action=original
    return row


def summary(rows):
    n=len(rows); valid=[r for r in rows if r.get('valid')]
    if not valid:return dict(games=n,valid_games=0,win_rate=0,mean_margin=None,p20_margin=None,worst_margin=None,objective=-1e9)
    margins=sorted(r['margin'] for r in valid); wins=sum(x>0 for x in margins); ties=sum(x==0 for x in margins)
    mean=statistics.mean(margins); p20=margins[int(.2*(len(margins)-1))]; worst=margins[0]
    actions=sum(r['efficiency']['actions'] for r in valid); noop=sum(r['efficiency']['noops'] for r in valid)/max(1,actions)
    waste=sum(r['efficiency']['moves']+r['efficiency']['passes'] for r in valid)/max(1,actions); tail=sum(m<-5000 for m in margins)/n
    unlock=sum(r['final_unlocked_quadrants']>=4 for r in valid)/n; days=[r['full_unlock_day'] if r['full_unlock_day'] is not None else r['steps']/24+1 for r in valid]
    productive=statistics.mean(r['full_farm_peak_productive_utilization'] for r in valid); animals=statistics.mean(r['peak_animals'] for r in valid)
    objective=(600*(wins+.5*ties)/n+150*math.tanh(mean/6000)+110*math.tanh(p20/6000)+45*math.tanh(worst/6000)
               -2200*(n-len(valid))/n-180*noop-22*waste-180*tail+60*unlock+30*productive+8*min(1,animals/8)-2.0*statistics.mean(days))
    return dict(games=n,valid_games=len(valid),wins=wins,ties=ties,win_rate=wins/n,mean_margin=mean,median_margin=statistics.median(margins),
                p20_margin=p20,worst_margin=worst,mean_money=statistics.mean(r['candidate_money'] for r in valid),noop_rate=noop,movement_idle_rate=waste,
                catastrophic_rate=tail,objective=objective,full_unlock_rate=unlock,mean_full_unlock_day=statistics.mean(days),
                mean_full_farm_peak_productive_utilization=productive,mean_peak_animals=animals,
                mean_terminal_unsold_units=statistics.mean(r['terminal_unsold_units'] for r in valid))


def evaluate(params=None,seeds=(101,),families=SUITE,steps=720,workers=0,kind='v3',agent_path=None):
    params=validate_params(params); prov=provenance(params)
    if prov['simulator_version']!=PINNED_VERSION: raise ValueError(f"Need kaggle-environments {PINNED_VERSION}, got {prov['simulator_version']}")
    seeds=tuple(seeds); families=tuple(families)
    jobs=[(params,f,s,seat,steps,kind,str(agent_path) if agent_path else None) for f in families for s in seeds for seat in (0,1)]
    w=cpu_limit(workers)
    rows=list(map(play,jobs)) if w==1 else list(ProcessPoolExecutor(max_workers=w).map(play,jobs))
    return dict(metrics=summary(rows),by_family={f:summary([r for r in rows if r['opponent']==f]) for f in families},
                by_seat={str(s):summary([r for r in rows if r['seat']==s]) for s in (0,1)},rows=rows,seeds=list(seeds),families=list(families),steps=steps,
                workers=w,params=params,kind=kind,provenance=prov,timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))


def save(path,data):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
