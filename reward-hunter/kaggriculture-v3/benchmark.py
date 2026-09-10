"""Official episodes, paired seeds/seats, auditable per-game failure and efficiency data."""
import argparse
import contextlib
import hashlib
import importlib
import io
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from policy import make_v3, validate_params
from opponents import opponent, SUITE

HERE=Path(__file__).resolve().parent
PINNED_SIMULATOR_HASH='9741c0470a8db98a70644491d5121ae6295413343d1a08ef9fcee35e0b76f2c5'

def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def provenance(params):
    import kaggle_environments
    engine=importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
    return dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip(),
                code_hash=digest(files),source_files=files,parameter_hash=digest(params),
                source_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=HERE,text=True).strip()),
                simulator_version=kaggle_environments.__version__,
                simulator_hash=hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest())


def cpu_limit(requested=0):
    count=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max':count=min(count,max(1,math.floor(int(quota)/int(period))))
    except (OSError,ValueError):pass
    return max(1,min(requested or 4,count,8))


def play(job):
    params,family,seed,seat,steps,kind,agent_path=job
    from kaggle_environments import make
    engine=importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    original=engine._apply_unit_action
    counts=[dict(actions=0,moves=0,passes=0,noops=0),dict(actions=0,moves=0,passes=0,noops=0)]
    player=[-1]
    def audited(farm,private,idx,action,*args,**kwargs):
        if idx==0:player[0]=(player[0]+1)%2
        c=counts[player[0]];c['actions']+=1
        op=action[0] if isinstance(action,list) and action else 'INVALID'
        c['moves']+=op in ('NORTH','SOUTH','EAST','WEST');c['passes']+=op=='PASS'
        x,y=engine._farmer_position(farm,idx)
        def snapshot():
            return repr((engine._farmer_position(farm,idx),farm['tiles'][y][x],private))
        before=snapshot() if op!='PASS' else None
        result=original(farm,private,idx,action,*args,**kwargs)
        if op!='PASS' and before==snapshot():c['noops']+=1
        return result
    engine._apply_unit_action=audited
    row=dict(seed=seed,seat=seat,opponent=family,steps=steps,kind=kind,valid=False,
             candidate_money=None,opponent_money=None,margin=None,error=None)
    try:
        candidate=agent_path if agent_path else (opponent('incumbent') if kind=='incumbent' else make_v3(params))
        agents=[candidate,opponent(family)] if seat==0 else [opponent(family),candidate]
        env=make('kaggriculture',configuration={'seed':int(seed),'episodeSteps':steps},debug=True)
        with contextlib.redirect_stdout(io.StringIO()) as captured:env.run(agents)
        statuses=[str(s.status) for s in env.state]
        row['statuses']=statuses
        row['valid']=statuses==['DONE','DONE']
        if not row['valid']:row['error']=captured.getvalue()[-4000:]
        farms=env.state[0].observation.farms
        row['candidate_money']=float(farms[seat]['money']);row['opponent_money']=float(farms[1-seat]['money'])
        row['margin']=row['candidate_money']-row['opponent_money']
        row['rewards']=[s.reward for s in env.state]
        for key in ('candidate_money','opponent_money','margin'):
            if not math.isfinite(row[key]):raise ValueError('nonfinite outcome')
        # No invented zero on missing outcomes; failed games remain in denominator.
        row['efficiency']=counts[seat];row['opponent_efficiency']=counts[1-seat]
        private=env.state[seat].observation.private
        row['terminal_unsold_units']=sum(private['shed'].values())+sum(sum(i.values()) for i in private['inventories'])
    except Exception as exc:row['valid']=False;row['error']=f'{type(exc).__name__}: {exc}'
    finally:engine._apply_unit_action=original
    return row


def summary(rows):
    n=len(rows)
    if not n:return dict(games=0,valid_games=0,win_rate=0,mean_margin=None,p20_margin=None,worst_margin=None,objective=-1e9)
    valid=[r for r in rows if r['valid']]
    margins=sorted(r['margin'] for r in valid)
    wins=sum(r['margin']>0 for r in valid);ties=sum(r['margin']==0 for r in valid)
    if not margins:return dict(games=n,valid_games=0,win_rate=0,mean_margin=None,p20_margin=None,worst_margin=None,objective=-1e9)
    mean=statistics.mean(margins);p20=margins[int(.2*(len(margins)-1))];worst=margins[0]
    actions=sum(r['efficiency']['actions'] for r in valid)
    noop=sum(r['efficiency']['noops'] for r in valid)/max(1,actions)
    waste=sum(r['efficiency']['passes']+r['efficiency']['moves'] for r in valid)/max(1,actions)
    tail=sum(m < -5000 for m in margins)/n
    objective=600*(wins+.5*ties)/n+120*math.tanh(mean/5000)+100*math.tanh(p20/5000)+40*math.tanh(worst/5000)-2000*(n-len(valid))/n-150*noop-20*waste-150*tail
    return dict(games=n,valid_games=len(valid),wins=wins,ties=ties,win_rate=wins/n,
                mean_margin=mean,median_margin=statistics.median(margins),p20_margin=p20,worst_margin=worst,
                mean_money=statistics.mean(r['candidate_money'] for r in valid),noop_rate=noop,
                movement_idle_rate=waste,catastrophic_rate=tail,objective=objective)


def evaluate(params=None,seeds=(101,),families=SUITE,steps=720,workers=0,kind='v3',agent_path=None):
    params=validate_params(params)
    actual=provenance(params)['simulator_hash']
    if actual!=PINNED_SIMULATOR_HASH:raise ValueError('Simulator source mismatch: install pinned official wheel in a clean venv')
    seeds=tuple(seeds);families=tuple(families)
    if not seeds or len(set(seeds))!=len(seeds) or not families or len(set(families))!=len(families):raise ValueError('empty/duplicate evaluation axes')
    jobs=[(params,f,s,seat,steps,kind,str(agent_path) if agent_path else None) for f in families for s in seeds for seat in (0,1)]
    count=cpu_limit(workers)
    if count==1:rows=list(map(play,jobs))
    else:
        with ProcessPoolExecutor(max_workers=count) as pool:rows=list(pool.map(play,jobs))
    return dict(metrics=summary(rows),by_family={f:summary([r for r in rows if r['opponent']==f]) for f in families},
                by_seat={str(s):summary([r for r in rows if r['seat']==s]) for s in (0,1)},rows=rows,
                seeds=list(seeds),families=list(families),steps=steps,workers=count,params=params,kind=kind,
                provenance=provenance(params),timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))


def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n');tmp.replace(path)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--seeds',default='101,103');ap.add_argument('--families',default=','.join(SUITE));ap.add_argument('--steps',type=int,default=720);ap.add_argument('--workers',type=int,default=0);ap.add_argument('--params');ap.add_argument('--agent-path');ap.add_argument('--kind',choices=('v3','incumbent'),default='v3');ap.add_argument('--output',required=True)
    a=ap.parse_args();p=json.loads(Path(a.params).read_text()) if a.params else None
    if p and 'params' in p:p=p['params']
    r=evaluate(p,tuple(map(int,a.seeds.split(','))),tuple(a.families.split(',')),a.steps,a.workers,a.kind,a.agent_path)
    save(a.output,r);print(json.dumps(r['metrics'],indent=2))
    if r['metrics']['valid_games']!=r['metrics']['games']:raise SystemExit(1)
