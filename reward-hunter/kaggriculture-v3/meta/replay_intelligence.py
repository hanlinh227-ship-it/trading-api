"""Offline public-replay intelligence for Kaggriculture.

Consumes public Kaggle replay archives in JSON/JSONL *or Parquet*. It never performs
network calls and is never imported by the submitted runtime agent. The output is a
compact meta prior that must still pass the local challenger league, unseen seeds,
incumbent duel, raw-exec and packaging gates before it can influence a submission.
"""
import argparse, collections, hashlib, json, math, statistics
from pathlib import Path

ANIMALS=('COW','SHEEP','GOOSE')
PRODUCTS=('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER')
JSON_KEYS=('replay','replay_json','episode','episode_json','steps','data','payload','content','json')


def _decode_jsonish(value):
    if isinstance(value,(bytes,bytearray,memoryview)):
        try:value=bytes(value).decode('utf-8')
        except Exception:return value
    for _ in range(2):
        if not isinstance(value,str):break
        text=value.strip()
        if not text or text[0] not in '[{"':break
        try:value=json.loads(text)
        except Exception:break
    return value


def _episodes(obj, depth=0):
    if depth>8:return
    obj=_decode_jsonish(obj)
    if isinstance(obj,dict):
        steps=_decode_jsonish(obj.get('steps'))
        if isinstance(steps,list) and steps:
            if steps is not obj.get('steps'):
                obj=dict(obj);obj['steps']=steps
            yield obj
            return
        seen=set()
        for key in JSON_KEYS:
            if key in obj:
                seen.add(key);yield from _episodes(obj[key],depth+1)
        for key,value in obj.items():
            if key not in seen and isinstance(value,(dict,list,str,bytes,bytearray,memoryview)):
                yield from _episodes(value,depth+1)
    elif isinstance(obj,list):
        for value in obj:
            if isinstance(value,(dict,list,str,bytes,bytearray,memoryview)):
                yield from _episodes(value,depth+1)


def _load_json(path):
    text=path.read_text(errors='ignore')
    try:return json.loads(text)
    except Exception:
        out=[]
        for line in text.splitlines():
            try:out.append(json.loads(line))
            except Exception:pass
        return out


def _parquet_rows(path,max_rows):
    try:
        import pyarrow.parquet as pq
    except Exception as exc:
        raise RuntimeError('Parquet input requires pyarrow; install pyarrow in the analysis workflow') from exc
    pf=pq.ParquetFile(path);emitted=0
    for batch in pf.iter_batches(batch_size=64):
        for row in batch.to_pylist():
            yield row;emitted+=1
            if emitted>=max_rows:return


def _parquet_schema(path):
    try:
        import pyarrow.parquet as pq
        pf=pq.ParquetFile(path)
        return {'rows':pf.metadata.num_rows,'columns':pf.schema_arrow.names}
    except Exception as exc:
        return {'error':f'{type(exc).__name__}: {exc}'}


def _ops(action):
    action=_decode_jsonish(action)
    if not isinstance(action,dict):return []
    out=[]
    for a in [action.get('farmer')]+list(action.get('hands') or []):
        a=_decode_jsonish(a)
        if isinstance(a,list) and a:out.append(tuple(a))
    for a in action.get('market') or []:
        a=_decode_jsonish(a)
        if isinstance(a,list) and a:out.append(tuple(a))
    return out


def _obs(state):
    if not isinstance(state,dict):return None
    o=_decode_jsonish(state.get('observation'))
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


def _seat_state(pair,seat):
    pair=_decode_jsonish(pair)
    if isinstance(pair,list) and seat<len(pair):
        st=_decode_jsonish(pair[seat]);return st if isinstance(st,dict) else None
    if isinstance(pair,dict):
        for key in (str(seat),seat,'agents','states'):
            try:
                value=pair[key]
                if isinstance(value,list) and seat<len(value):value=value[seat]
                value=_decode_jsonish(value)
                if isinstance(value,dict):return value
            except Exception:pass
    return None


def analyze_seat(ep,seat):
    steps=_decode_jsonish(ep.get('steps')) or []
    actions=[];first={};sell=collections.defaultdict(list);buy_seed=collections.Counter();curves={};peak_hands=0;peak_land=1;last_shape=None
    for i,pair in enumerate(steps):
        st=_seat_state(pair,seat)
        if not st:continue
        action=_decode_jsonish(st.get('action'));obs=_obs(st);ops=_ops(action);actions.append(ops)
        for op in ops:
            name=op[0]
            if name in ('BUY_LAND','HIRE') and name not in first:first[name]=i
            if name=='BUY_ANIMAL' and len(op)>1 and ('BUY_'+str(op[1])) not in first:first['BUY_'+str(op[1])]=i
            if name=='BUY_SEED' and len(op)>2:
                try:buy_seed[str(op[1])]+=int(op[2])
                except Exception:pass
            if name=='SELL' and len(op)>2:
                try:sell[str(op[1])].append(int(op[2]))
                except Exception:pass
        if obs:
            shape=_farm_shape(obs,seat)
            if shape:
                last_shape=shape;peak_hands=max(peak_hands,shape['hands']);peak_land=max(peak_land,shape['land'])
            day=int(obs.get('day',i//24) or i//24)
            if day in (0,5,10,15,20,25,29) and str(day) not in curves:
                m=_money(obs,seat)
                if m is not None:curves[str(day)]=m
    serial=json.dumps(actions[:120],sort_keys=True,separators=(',',':'),default=str).encode();fp=hashlib.sha256(serial).hexdigest()[:16]
    reward=None
    try:
        tail=_seat_state(steps[-1],seat);reward=tail.get('reward') if tail else None
        if reward is None:
            o=_obs(tail) if tail else None;reward=_money(o,seat) if o else None
    except Exception:pass
    engine=None
    for key in ('engine_version','module_version','version'):
        if key in ep and ep.get(key) is not None:engine=str(ep.get(key));break
    return dict(fingerprint=fp,reward=reward,engine_version=engine,first_day={k:round(v/24,3) for k,v in first.items()},
                sell_batches={k:dict(orders=len(v),median=statistics.median(v),mean=statistics.mean(v)) for k,v in sell.items()},seed_buys=dict(buy_seed),
                money_curve=curves,peak_hands=peak_hands,peak_land=peak_land,final_shape=last_shape)


def _safe_median(values,default=0):
    vals=[float(v) for v in values if isinstance(v,(int,float)) and math.isfinite(float(v))]
    return statistics.median(vals) if vals else default


def summarize(records):
    good=[r for r in records if isinstance(r.get('reward'),(int,float)) and math.isfinite(float(r['reward']))]
    ranked=sorted(good,key=lambda r:r['reward'],reverse=True);top=ranked[:max(4,len(ranked)//4)] if ranked else records[:max(4,len(records)//4)]
    fps=collections.Counter(r['fingerprint'] for r in records)
    cows=_safe_median([(r.get('final_shape') or {}).get('animals',{}).get('COW',0) for r in top]);sheep=_safe_median([(r.get('final_shape') or {}).get('animals',{}).get('SHEEP',0) for r in top]);geese=_safe_median([(r.get('final_shape') or {}).get('animals',{}).get('GOOSE',0) for r in top])
    hands=_safe_median([r.get('peak_hands',0) for r in top]);land=_safe_median([r.get('peak_land',1) for r in top],1);batches=[]
    for r in top:
        for item,d in r.get('sell_batches',{}).items():
            if item!='FERTILIZER' and isinstance(d.get('median'),(int,float)):batches.append(d['median'])
    versions=collections.Counter(r.get('engine_version') or 'unknown' for r in records)
    recommendation=dict(herd_mode='dynamic',cow_max=max(0,min(14,int(round(cows)))),sheep_max=max(0,min(14,int(round(sheep)))),goose_max=max(0,min(12,int(round(geese)))),
                        target_hands=max(5,min(14,int(round(hands or 10)))),sell_batch=max(2,min(12,int(round(_safe_median(batches,6))))))
    return dict(records=len(records),ranked_records=len(good),top_sample=len(top),top_reward_median=_safe_median([r.get('reward') for r in top]),modal_openings=fps.most_common(12),
                top_shape_medians=dict(cows=cows,sheep=sheep,geese=geese,peak_hands=hands,land_quadrants=land),recommended_params=recommendation,
                engine_versions=dict(versions),methodology='public replay observations/actions only; top quartile by final reward when available')


def _select_files(root,max_parquet_files):
    json_files=sorted([p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ('.json','.jsonl')])
    pq_all=[p for p in root.rglob('*.parquet') if p.is_file()]
    aggregate=[p for p in pq_all if p.name in ('episodes.parquet','top10_history.parquet')]
    dated=sorted([p for p in pq_all if p.name.startswith('replays_')],key=lambda p:p.name,reverse=True)
    other=sorted([p for p in pq_all if p not in aggregate and p not in dated],key=lambda p:p.name,reverse=True)
    parquet=[]
    for p in aggregate+dated+other:
        if p not in parquet:parquet.append(p)
        if len(parquet)>=max_parquet_files:break
    return json_files,parquet


def main(root,out,max_parquet_files=12,max_rows_per_file=2500,max_records=5000):
    root=Path(root);records=[];diagnostics=[];seen=set();json_files,parquet_files=_select_files(root,max_parquet_files)
    def accept(ep,source):
        if len(records)>=max_records:return False
        try:key=hashlib.sha256(json.dumps(ep.get('steps',[]),sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
        except Exception:key=None
        if key and key in seen:return False
        if key:seen.add(key)
        before=len(records)
        for seat in (0,1):
            rec=analyze_seat(ep,seat);rec['source']=source;records.append(rec)
            if len(records)>=max_records:break
        return len(records)>before
    for p in json_files:
        found=0
        try:
            for ep in _episodes(_load_json(p)):
                found+=int(accept(ep,str(p.relative_to(root))))
                if len(records)>=max_records:break
            diagnostics.append({'file':str(p.relative_to(root)),'format':'json','episodes_found':found})
        except Exception as exc:diagnostics.append({'file':str(p.relative_to(root)),'format':'json','error':f'{type(exc).__name__}: {exc}'})
        if len(records)>=max_records:break
    if len(records)<max_records:
        for p in parquet_files:
            found=0;schema=_parquet_schema(p)
            try:
                for row in _parquet_rows(p,max_rows_per_file):
                    for ep in _episodes(row):
                        found+=int(accept(ep,str(p.relative_to(root))))
                        if len(records)>=max_records:break
                    if len(records)>=max_records:break
                diagnostics.append({'file':str(p.relative_to(root)),'format':'parquet','episodes_found':found,'schema':schema})
            except Exception as exc:diagnostics.append({'file':str(p.relative_to(root)),'format':'parquet','error':f'{type(exc).__name__}: {exc}','schema':schema})
            if len(records)>=max_records:break
    result=dict(source_root=str(root),json_files=len(json_files),parquet_files=len(parquet_files),files_scanned=len(diagnostics),summary=summarize(records),diagnostics=diagnostics,records=records)
    Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'summary':result['summary'],'diagnostics':diagnostics},indent=2,sort_keys=True))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--max-parquet-files',type=int,default=12);ap.add_argument('--max-rows-per-file',type=int,default=2500);ap.add_argument('--max-records',type=int,default=5000)
    a=ap.parse_args();main(a.input,a.output,a.max_parquet_files,a.max_rows_per_file,a.max_records)
