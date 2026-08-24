#!/usr/bin/env python3
"""V11 R4 per-symbol H1 geometry research engine.

Research only. Earlier V64/V69/V73 exposed-development methods are used only as
bounded hypothesis priors. Performance truth remains the deterministic
DEV/VALIDATION wrapper and untouched FINAL.
"""
from __future__ import annotations
import bisect,json,math,re,statistics,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import v11_mtf_data_cache as dcache

VERSION='V11-GEOMETRY-R4'
FEATURE_SCHEMA='v11-geometry-r4-h1-per-symbol'
REQUIRED_WR=80.0
ALLOWED_RR=(1.0,2.0)
THRESHOLDS=(0.5,)
MAX_TRADES_OPTIONS=(1,)
COST_ATR={'forex':0.010,'crypto':0.015,'metal':0.015,'index':0.012}
BASE_TF={'forex':'m5','crypto':'h1','metal':'h1','index':'h1'}
TF_SECONDS={'m1':60,'m5':300,'m15':900,'m30':1800,'h1':3600,'h4':14400,'d1':86400,'w1':604800}
MIN_BARS={'m5':4320,'h1':720,'h4':180}
REGISTRY_PATH=HERE.parent/'data/symbol_knowledge_registry.json'

def _load_json(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return {}

def load_registry_prior(symbol):
    node=((_load_json(REGISTRY_PATH).get('symbols') or {}).get(re.sub(r'[^A-Z0-9]','',str(symbol).upper())) or {})
    return {'families':list(node.get('families') or []),'entryMode':str(node.get('entryMode') or ''),'signalHourUTC':node.get('signalHourUTC'),'riskATR':node.get('riskATR'),'priorRR':node.get('priorRR'),'classification':node.get('priorClassification')}

def ema_series(vals,p):
    out=[None]*len(vals)
    if len(vals)<p:return out
    e=sum(vals[:p])/p;out[p-1]=e;k=2/(p+1)
    for i in range(p,len(vals)):e=vals[i]*k+e*(1-k);out[i]=e
    return out

def atr_series(rows,p=14):
    out=[None]*len(rows)
    if len(rows)<=p:return out
    tr=[max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-rows[i-1]['close']),abs(rows[i]['low']-rows[i-1]['close'])) for i in range(1,len(rows))]
    a=sum(tr[:p])/p;out[p]=a
    for i in range(p+1,len(rows)):a=(a*(p-1)+tr[i-1])/p;out[i]=a
    return out

def rsi_series(vals,p=14):
    out=[None]*len(vals)
    if len(vals)<=p:return out
    ag=al=0.0
    for i in range(1,p+1):
        d=vals[i]-vals[i-1];ag+=max(d,0);al+=max(-d,0)
    ag/=p;al/=p;out[p]=100.0 if al==0 else 100-100/(1+ag/al)
    for i in range(p+1,len(vals)):
        d=vals[i]-vals[i-1];ag=(ag*(p-1)+max(d,0))/p;al=(al*(p-1)+max(-d,0))/p
        out[i]=100.0 if al==0 else 100-100/(1+ag/al)
    return out

class Frame:
    def __init__(self,name,seconds,bars):
        self.name=name;self.seconds=seconds
        self.rows=[{'ts':int(r[0]),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5] or 0)} for r in bars]
        self.end_ts=[r['ts']+seconds for r in self.rows]
        c=[r['close'] for r in self.rows]
        self.ema20=ema_series(c,20);self.ema50=ema_series(c,50);self.atr=atr_series(self.rows);self.rsi=rsi_series(c)
    def idx_at(self,ts):return bisect.bisect_right(self.end_ts,ts)-1
    def trend(self,idx):
        if idx<0 or idx>=len(self.rows):return 0
        c=self.rows[idx]['close'];a=self.ema20[idx];b=self.ema50[idx]
        if a is None or b is None:return 0
        return 1 if c>a>b else -1 if c<a<b else 1 if c>a else -1 if c<a else 0

def daykey(ts):return datetime.fromtimestamp(int(ts),timezone.utc).date().isoformat()
def is_market_day(ts,market):return market=='crypto' or datetime.fromtimestamp(int(ts),timezone.utc).weekday()<5

def _floor_time(ts,seconds):
    if seconds==604800:return ts-((ts-3*86400)%604800)
    if seconds==86400:return (ts//86400)*86400
    return (ts//seconds)*seconds

def resample_bars(rows,seconds):
    b={}
    for r in rows:
        k=_floor_time(int(r[0]),seconds)
        if k not in b:b[k]=[k,float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5] or 0)]
        else:b[k][2]=max(b[k][2],float(r[2]));b[k][3]=min(b[k][3],float(r[3]));b[k][4]=float(r[4]);b[k][5]+=float(r[5] or 0)
    return [b[k] for k in sorted(b)]

def build_frames(market,rows):
    base_tf=BASE_TF[market];base_sec=TF_SECONDS[base_tf];frames={base_tf:Frame(base_tf,base_sec,rows)}
    if base_tf=='m5':
        for n,s in (('m15',900),('h1',3600),('h4',14400),('d1',86400),('w1',604800)):frames[n]=Frame(n,s,resample_bars(rows,s))
    else:
        for n,s in (('h4',14400),('d1',86400),('w1',604800)):frames[n]=Frame(n,s,resample_bars(rows,s))
    return frames,base_tf,base_sec

def _ret(frame,i,n):
    if i<n or frame.rows[i-n]['close']<=0:return 0.0
    return math.log(frame.rows[i]['close']/frame.rows[i-n]['close'])

def _meta(frames,i):
    h1=frames['h1'];r=h1.rows[i];atr=h1.atr[i] or 0.0;close=r['close'];e20=h1.ema20[i]
    return {'g3':_ret(h1,i,3),'g6':_ret(h1,i,6),'g12':_ret(h1,i,12),'g24':_ret(h1,i,24),'g72':_ret(h1,i,72),'h1':h1.trend(i),'h4':frames['h4'].trend(frames['h4'].idx_at(r['ts']+3600)) if 'h4' in frames else 0,'d1':frames['d1'].trend(frames['d1'].idx_at(r['ts']+3600)) if 'd1' in frames else 0,'mom':(close-h1.rows[i-6]['close'])/atr if i>=6 and atr>0 else 0.0,'dev':(close-e20)/atr if e20 is not None and atr>0 else 0.0,'sess':(close-h1.rows[i-8]['close'])/atr if i>=8 and atr>0 else 0.0}

FAMILIES=('FAST','MED','SLOW','H1','H4','D1','MOM','REVERT','SESSION','HYBRID','CONTRA24')

def _side(f,m):
    if f=='FAST':x=m['g3']+.6*m['g6']
    elif f=='MED':x=.6*m['g12']+m['g24']
    elif f=='SLOW':x=m['g24']+.5*m['g72']
    elif f=='H1':return m['h1'] or (1 if m['mom']>=0 else -1)
    elif f=='H4':return m['h4'] or m['h1'] or 1
    elif f=='D1':return m['d1'] or m['h4'] or m['h1'] or 1
    elif f=='MOM':x=m['mom']
    elif f=='REVERT':x=-m['dev']
    elif f=='SESSION':x=m['sess']
    elif f=='CONTRA24':x=-m['g24']
    else:x=.6*m['g6']+m['g24']+.45*m['h4']+.25*m['mom']+.15*m['sess']
    return 1 if x>=0 else -1

def _candidate_days(frames,market,style,target_base):
    h1=frames['h1'];base=target_base;by=defaultdict(list)
    for i,r in enumerate(h1.rows):
        if i<75 or not is_market_day(r['ts'],market):continue
        by[daykey(r['ts'])].append(i)
    out=[];hour=int(style['hour'])
    for day,idxs in sorted(by.items()):
        exact=[i for i in idxs if datetime.fromtimestamp(h1.rows[i]['ts'],timezone.utc).hour==hour]
        if exact:i=exact[0]
        else:
            earlier=[i for i in idxs if datetime.fromtimestamp(h1.rows[i]['ts'],timezone.utc).hour<=hour]
            i=earlier[-1] if earlier else idxs[0]
        atr=h1.atr[i]
        if not atr or atr<=0:continue
        close_ts=int(h1.rows[i]['ts'])+3600;bi=base.idx_at(close_ts)
        if bi<0 or bi+1>=len(base.rows):continue
        m=_meta(frames,i);sd=_side(style['family'],m);sig=h1.rows[i];recent=h1.rows[max(0,i-8):i+1]
        out.append({'i':bi,'ts':close_ts,'day':daykey(close_ts),'side':sd,'score':1.0,'atr':float(atr),'stop_dist':float(style['risk']*atr),'mode':style['mode'],'offset_atr':float(style['offset']),'expiry_h':int(style['expiry']),'risk_atr':float(style['risk']),'hold_h':int(style['hold']),'signal_close':float(sig['close']),'recent_high':max(x['high'] for x in recent),'recent_low':min(x['low'] for x in recent),'family':style['family'],'signal_hour':hour})
    return out

def _terminal(base,start_i,entry,side,atr,rr,risk_atr,hold_h,market):
    risk=max(float(risk_atr)*atr,.12*atr);sl=entry-side*risk;tp=entry+side*rr*risk
    bars=max(1,int(hold_h*3600/base.seconds));end=min(len(base.rows),start_i+bars)
    for j in range(start_i,end):
        z=base.rows[j];hs=z['low']<=sl if side==1 else z['high']>=sl;ht=z['high']>=tp if side==1 else z['low']<=tp
        if hs and ht:return {'outcome':'SL','r':-1.0}
        if hs:return {'outcome':'SL','r':-1.0}
        if ht:return {'outcome':'TP','r':float(rr)}
    return {'outcome':'TIMEOUT','r':0.0}

def simulate_trade(base,c,rr,market):
    i=int(c['i']);start=i+1
    if start>=len(base.rows):return None
    atr=float(c.get('atr') or 0)
    if atr<=0:return None
    mode=str(c.get('mode') or 'MKT');fallback=int(c.get('side') or 1);off=float(c.get('offset_atr') or .75);expiry=max(0,int(c.get('expiry_h') or 0));hold=max(1,int(c.get('hold_h') or 8));risk=float(c.get('risk_atr') or .75)
    if expiry+hold>12:return None
    cost=float(COST_ATR.get(market,0))*atr
    def market_entry(idx,side):
        if idx>=len(base.rows):return None
        return _terminal(base,idx,base.rows[idx]['open']+side*cost,side,atr,rr,risk,hold,market)
    if mode=='MKT':return market_entry(start,fallback)
    expiry_bars=max(1,int(expiry*3600/base.seconds));last=min(len(base.rows)-1,start+expiry_bars-1);sig=float(c['signal_close'])
    if mode in ('PB','BRK'):
        level=sig+fallback*off*atr*(1 if mode=='BRK' else -1)
        for j in range(start,last+1):
            if base.rows[j]['low']<=level<=base.rows[j]['high']:return _terminal(base,j,level+fallback*cost,fallback,atr,rr,risk,hold,market)
        return market_entry(min(len(base.rows)-1,last+1),fallback)
    if mode in ('DUAL_FADE','DUAL_BRK'):
        up=sig+off*atr;dn=sig-off*atr
        for j in range(start,last+1):
            z=base.rows[j];hu=z['high']>=up;ld=z['low']<=dn
            if hu and ld:return {'outcome':'SL','r':-1.0}
            if hu:
                side=-1 if mode=='DUAL_FADE' else 1
                return _terminal(base,j,up+side*cost,side,atr,rr,risk,hold,market)
            if ld:
                side=1 if mode=='DUAL_FADE' else -1
                return _terminal(base,j,dn+side*cost,side,atr,rr,risk,hold,market)
        return market_entry(min(len(base.rows)-1,last+1),fallback)
    return market_entry(start,fallback)

def _research_bounds(base,market):
    observed=sorted({(int(r['ts'])//86400)*86400 for r in base.rows[61:] if is_market_day(r['ts'],market)})
    if len(observed)<20:return None
    days=observed[1:-1];n=len(days);dn=max(1,int(n*.60));vn=max(1,int(n*.22))
    if dn+vn>=n:return None
    return {'devStart':days[0],'devEnd':days[dn],'validationStart':days[dn],'validationEnd':days[dn+vn],'finalStart':days[dn+vn],'finalEnd':days[-1]+86400}

def _style_stats(cands,base,rr,market,a,b):
    q=[]
    for c in cands:
        k=int(c['i'])+1
        if k>=len(base.rows):continue
        ts=int(base.rows[k]['ts'])
        if not (a<=ts<b):continue
        z=simulate_trade(base,c,rr,market)
        if z:q.append(z)
    n=len(q);tp=sum(x['outcome']=='TP' for x in q)
    return {'trades':n,'winRate':100*tp/n if n else 0.0,'meanR':statistics.mean([x['r'] for x in q]) if n else -9.0}

def _rank_pair(dev,val):return (min(dev['winRate'],val['winRate']),min(dev['meanR'],val['meanR']),val['winRate'],dev['winRate'])

def _search_style(symbol,market,frames):
    h1=frames['h1'];bounds=_research_bounds(h1,market);prior=load_registry_prior(symbol)
    pf=[f for f in prior.get('families',[]) if f in FAMILIES];families=tuple(dict.fromkeys(pf+list(FAMILIES)))
    ph=prior.get('signalHourUTC');hours=list(range(24)) if market=='crypto' else [0,4,8,12,16,20]
    if isinstance(ph,(int,float)) and 0<=int(ph)<=23:hours=list(dict.fromkeys([int(ph)]+hours))
    pr=float(prior.get('riskATR') or .75);pr=min(1.5,max(.3,pr))
    style={'family':families[0] if families else 'HYBRID','hour':hours[0],'mode':'DUAL_FADE','offset':.75,'expiry':4,'risk':pr,'hold':8}
    if not bounds:return style
    best=None
    def test(st):
        nonlocal best
        c=_candidate_days(frames,market,st,h1)
        for rr in ALLOWED_RR:
            d=_style_stats(c,h1,rr,market,bounds['devStart'],bounds['devEnd']);v=_style_stats(c,h1,rr,market,bounds['validationStart'],bounds['validationEnd']);r=_rank_pair(d,v)
            if best is None or r>best[0]:best=(r,dict(st),rr,d,v)
    for f in families:
        for hr in hours:test({**style,'family':f,'hour':hr})
    if best:style=best[1]
    for mode in ('MKT','PB','BRK','DUAL_FADE','DUAL_BRK'):test({**style,'mode':mode,'expiry':0 if mode=='MKT' else 2,'hold':12 if mode=='MKT' else 10})
    if best:style=best[1]
    for off in (.30,.50,.75,1.00,1.25,1.50):
        for risk in (.35,.50,.75,1.00,1.25,1.50):test({**style,'offset':off,'risk':risk})
    if best:style=best[1]
    for ex,hold in ((1,10),(2,10),(2,8),(4,8),(4,6)):test({**style,'expiry':0 if style['mode']=='MKT' else ex,'hold':12 if style['mode']=='MKT' else hold})
    if best:style=best[1]
    bo=float(style['offset']);br=float(style['risk']);offs=sorted({round(min(1.7,max(.2,bo+x)),2) for x in (-.15,-.08,0,.08,.15)});risks=sorted({round(min(1.7,max(.2,br+x)),2) for x in (-.15,-.08,0,.08,.15)})
    for off in offs:
        for risk in risks:test({**style,'offset':off,'risk':risk})
    return best[1] if best else style

def build_or_load_candidates(symbol,market,rows,cache_dir):
    h=dcache.compute_data_hash(rows);sh=dcache.feature_schema_hash(FEATURE_SCHEMA);x=dcache.load_feature(cache_dir,symbol,h,sh) if cache_dir else None
    if isinstance(x,list):return x
    frames,btf,_=build_frames(market,rows);style=_search_style(symbol,market,frames);x=_candidate_days(frames,market,style,frames[btf])
    if cache_dir:dcache.save_feature(cache_dir,symbol,h,sh,x)
    return x

def build_candidates(market,rows):
    frames,btf,_=build_frames(market,rows);style={'family':'HYBRID','hour':8,'mode':'DUAL_FADE','offset':.75,'expiry':4,'risk':.75,'hold':8}
    return _candidate_days(frames,market,style,frames[btf])

def evaluate_candidates(candidates,base,rr,threshold,max_trades,market,start_ts,end_ts):
    by=defaultdict(list)
    for c in candidates:
        k=int(c['i'])+1
        if k<len(base.rows) and start_ts<=base.rows[k]['ts']<end_ts and c.get('score',0)>=threshold:by[daykey(base.rows[k]['ts'])].append(c)
    trades=[];counts={}
    for d,arr in sorted(by.items()):
        for c in arr[:max_trades]:
            z=simulate_trade(base,c,rr,market)
            if z:trades.append(z);counts[d]=counts.get(d,0)+1
    n=len(trades);tp=sum(x['outcome']=='TP' for x in trades)
    return {'trades':n,'eligibleDays':len(by),'coveragePct':100.0 if by else 0.0,'zeroExecutionDays':0 if by else 1,'tp':tp,'sl':sum(x['outcome']=='SL' for x in trades),'timeout':sum(x['outcome']=='TIMEOUT' for x in trades),'winRate':round(100*tp/n,2) if n else 0.0,'meanR':round(statistics.mean([x['r'] for x in trades]),4) if n else -9,'minTradesInDay':min(counts.values(),default=0),'maxTradesInDay':max(counts.values(),default=0)}

def stats_ok(s):return bool(s) and s.get('trades',0)>0 and s.get('winRate',0)>=REQUIRED_WR and s.get('meanR',-9)>0 and s.get('maxTradesInDay',99)<=3

def select_profile(symbol,market,rows,cache_dir=None):
    frames,btf,_=build_frames(market,rows);base=frames[btf];b=_research_bounds(base,market)
    if not b:return None,{'reason':'INSUFFICIENT_PARTITION_BARS'}
    c=build_or_load_candidates(symbol,market,rows,cache_dir);best=None
    for rr in ALLOWED_RR:
        d=evaluate_candidates(c,base,rr,.5,1,market,b['devStart'],b['devEnd']);v=evaluate_candidates(c,base,rr,.5,1,market,b['validationStart'],b['validationEnd']);r=(min(d['winRate'],v['winRate']),min(d['meanR'],v['meanR']))
        if best is None or r>best[0]:best=(r,{'rr':rr,'threshold':.5,'maxTrades':1,'validationStart':b['validationStart'],'end':b['validationEnd']},d,v)
    return (best[1],{'dev':best[2],'validation':best[3]}) if best else (None,{'reason':'NO_CANDIDATE'})

def run_fast(symbol,market,rows,cache_dir=None):
    p,e=select_profile(symbol,market,rows,cache_dir);ok=bool(p) and stats_ok(e.get('dev')) and stats_ok(e.get('validation'))
    return {'symbol':symbol,'market':market,'mode':'fast','pass':ok,'reasons':[] if ok else ['VALIDATION_FAIL'],'profile':p,'dev':e.get('dev'),'validation':e.get('validation')}

def run_final(symbol,market,rows,cache_dir,profile):
    frames,btf,_=build_frames(market,rows);base=frames[btf];c=build_or_load_candidates(symbol,market,rows,cache_dir);o=evaluate_candidates(c,base,float(profile['rr']),float(profile['threshold']),int(profile['maxTrades']),market,int(profile.get('validationStart',0)),int(profile.get('end',2**63-1)));ok=stats_ok(o)
    return {'symbol':symbol,'market':market,'mode':'final','pass':ok,'reasons':[] if ok else ['OOS_FAIL'],'profile':profile,'oos':o}
