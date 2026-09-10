"""Offline public-replay intelligence. No network access and no private episode APIs.

Consumes Kaggle public episode JSON/JSONL files (or notebook outputs) and extracts economy
shape, opening fingerprints, herd/land/labor timing, sales cadence and money curves. The
result can seed local search; it is never imported by the submitted runtime agent.
"""
import argparse,collections,hashlib,json,math,statistics
from pathlib import Path

ANIMALS=('COW','SHEEP','GOOSE'); PRODUCTS=('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER')


def _load(path):
    text=path.read_text(errors='ignore')
    try:return json.loads(text)
    except Exception:
        out=[]
        for line in text.splitlines():
            try:out.append(json.loads(line))
            except Exception:pass
        return out


def _episodes(obj):
    if isinstance(obj,dict):
        if isinstance(obj.get('steps'),list) and obj['steps']:yield obj
        else:
            for v in obj.values():yield from _episodes(v)
    elif isinstance(obj,list):
        for v in obj:yield from _episodes(v)


def _ops(action):
    if not isinstance(action,dict):return []
    out=[]
    for a in [action.get('farmer')]+list(action.get('hands') or []):
        if isinstance(a,list) and a:out.append(tuple(a))
    for a in action.get('market') or []:
        if isinstance(a,list) and a:out.append(tuple(a))
    return out


def _obs(state):
    if not isinstance(state,dict):return None
    o=state.get('observation')
    return o if isinstance(o,dict) else None


def _money(obs,seat):
    try:return float(obs['farms'][seat]['money'])
    except Exception:return None


def _farm_shape(obs,seat):
    try:
        farm=obs['farms'][seat];tiles=farm['tiles'];plants=collections.Counter();animals=collections.Counter();structures=0
        for row in tiles:
            for t in row:
                if isinstance(t,dict):
                    if t.get('kind')=='PLANT':plants[t.get('crop')]+=1
                    if 'animal' in t:animals[t.get('animal')]+=1
                    if t.get('kind') in ('COOP','PASTURE'):structures+=1
        return dict(crops=dict(plants),animals=dict(animals),hands=len(farm.get('hands',[])),land=len(farm.get('unlocked_quadrants',['NW'])),structures=structures)
    except Exception:return None


def analyze_seat(ep,seat):
    steps=ep.get('steps') or [];actions=[];first={};sell=collections.defaultdict(list);buy_seed=collections.Counter();curves={};peak_hands=0;peak_land=1;last_shape=None
    for i,pair in enumerate(steps):
        if not isinstance(pair,list) or seat>=len(pair) or not isinstance(pair[seat],dict):continue
        st=pair[seat];action=st.get('action');obs=_obs(st)
        ops=_ops(action);actions.append(ops)
        for op in ops:
            name=op[0]
            if name in ('BUY_LAND','HIRE') and name not in first:first[name]=i
            if name=='BUY_ANIMAL' and len(op)>1 and ('BUY_'+str(op[1])) not in first:first['BUY_'+str(op[1])]=i
            if name=='BUY_SEED' and len(op)>2:buy_seed[str(op[1])]+=int(op[2])
            if name=='SELL' and len(op)>2:sell[str(op[1])].append(int(op[2]))
        if obs:
            shape=_farm_shape(obs,seat)
            if shape:
                last_shape=shape;peak_hands=max(peak_hands,shape['hands']);peak_land=max(peak_land,shape['land'])
            day=int(obs.get('day',i//24))
            if day in (0,5,10,15,20,25,29) and day not in curves:
                m=_money(obs,seat)
                if m is not None:curves[str(day)]=m
    serial=json.dumps(actions[:120],sort_keys=True,separators=(',',':')).encode();fp=hashlib.sha256(serial).hexdigest()[:16]
    reward=None
    try:
        tail=steps[-1][seat];reward=tail.get('reward') if isinstance(tail,dict) else None
        if reward is None:
            o=_obs(tail);reward=_money(o,seat) if o else None
    except Exception:pass
    return dict(fingerprint=fp,reward=reward,first_day={k:round(v/24,3) for k,v in first.items()},sell_batches={k:dict(orders=len(v),median=statistics.median(v),mean=statistics.mean(v)) for k,v in sell.items()},
                seed_buys=dict(buy_seed),money_curve=curves,peak_hands=peak_hands,peak_land=peak_land,final_shape=last_shape)


def summarize(records):
    good=[r for r in records if isinstance(r.get('reward'),(int,float)) and math.isfinite(float(r['reward']))]
    ranked=sorted(good,key=lambda r:r['reward'],reverse=True);top=ranked[:max(4,len(ranked)//4)] if ranked else records
    fps=collections.Counter(r['fingerprint'] for r in records)
    def med(values,default=0):
        vals=[v for v in values if isinstance(v,(int,float))]
        return statistics.median(vals) if vals else default
    cows=med([(r.get('final_shape') or {}).get('animals',{}).get('COW',0) for r in top]);sheep=med([(r.get('final_shape') or {}).get('animals',{}).get('SHEEP',0) for r in top]);geese=med([(r.get('final_shape') or {}).get('animals',{}).get('GOOSE',0) for r in top])
    hands=med([r.get('peak_hands',0) for r in top]);land=med([r.get('peak_land',1) for r in top])
    batches=[]
    for r in top:
        for item,d in r.get('sell_batches',{}).items():
            if item!='FERTILIZER':batches.append(d.get('median'))
    recommendation=dict(herd_mode='dynamic',cow_max=int(round(cows)),sheep_max=int(round(sheep)),goose_max=int(round(geese)),target_hands=max(5,min(14,int(round(hands or 10)))),sell_batch=max(2,min(12,int(round(med(batches,6))))))
    return dict(records=len(records),ranked_records=len(good),top_sample=len(top),top_reward_median=med([r.get('reward') for r in top]),modal_openings=fps.most_common(12),
                top_shape_medians=dict(cows=cows,sheep=sheep,geese=geese,peak_hands=hands,land_quadrants=land),recommended_params=recommendation,
                methodology='public episode observations/actions only; top quartile by final reward when available')


def main(root,out):
    root=Path(root);records=[];files=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.suffix.lower() in ('.json','.jsonl'):
            files.append(str(p))
            for ep in _episodes(_load(p)):
                for seat in (0,1):records.append(analyze_seat(ep,seat))
    result=dict(source_root=str(root),files_scanned=len(files),summary=summarize(records),records=records)
    Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n');print(json.dumps(result['summary'],indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();main(a.input,a.output)
