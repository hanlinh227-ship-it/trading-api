#!/usr/bin/env python3
# Frozen engine body copied from validated V11 MTF R1; public wrapper overrides only BASE_TF/MIN_BARS.
from __future__ import annotations
import bisect,json,math,os,re,statistics,sys,time
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
_SCRIPT_DIR=Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:sys.path.insert(0,str(_SCRIPT_DIR))
import v11_mtf_data_cache as dcache
VERSION='V11-MTF-ENGINE-R1';FEATURE_SCHEMA='v11-mtf-features-v1';REQUIRED_WR=80.0;ALLOWED_RR=(1.0,2.0);THRESHOLDS=(0.45,0.55,0.65);MAX_TRADES_OPTIONS=(1,2,3);COST_ATR={'forex':0.015,'crypto':0.020,'metal':0.020,'index':0.015};BASE_TF={'forex':'m5','crypto':'h4','metal':'h1','index':'h1'};TF_SECONDS={'m1':60,'m5':300,'m15':900,'m30':1800,'h1':3600,'h4':14400,'d1':86400,'w1':604800};MIN_BARS={'m5':4320,'h4':900,'h1':1440};REGISTRY_PATH=_SCRIPT_DIR.parent/'data/symbol_knowledge_registry.json'
def _load_json(path):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except Exception:return {}
def load_registry_prior(symbol):
 d=_load_json(REGISTRY_PATH);node=((d.get('symbols') or {}).get(re.sub(r'[^A-Z0-9]','',str(symbol).upper())) or {});return {k:node[k] for k in ('priorRR','riskATR','signalHourUTC','timeframe') if k in node}
def ema_series(vals,p):
 out=[None]*len(vals)
 if len(vals)<p:return out
 e=sum(vals[:p])/p;out[p-1]=e;k=2/(p+1)
 for i in range(p,len(vals)):e=vals[i]*k+e*(1-k);out[i]=e
 return out
def atr_series(rows,p=14):
 out=[None]*len(rows)
 if len(rows)<=p:return out
 tr=[max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-rows[i-1]['close']),abs(rows[i]['low']-rows[i-1]['close'])) for i in range(1,len(rows))];a=sum(tr[:p])/p;out[p]=a
 for i in range(p+1,len(rows)):a=(a*(p-1)+tr[i-1])/p;out[i]=a
 return out
def rsi_series(vals,p=14):
 out=[None]*len(vals)
 if len(vals)<=p:return out
 ag=al=0.0
 for i in range(1,p+1):d=vals[i]-vals[i-1];ag+=max(d,0);al+=max(-d,0)
 ag/=p;al/=p;out[p]=100.0 if al==0 else 100-100/(1+ag/al)
 for i in range(p+1,len(vals)):
  d=vals[i]-vals[i-1];ag=(ag*(p-1)+max(d,0))/p;al=(al*(p-1)+max(-d,0))/p;out[i]=100.0 if al==0 else 100-100/(1+ag/al)
 return out
class Frame:
 def __init__(self,name,seconds,bars):
  self.name=name;self.seconds=seconds;self.rows=[{'ts':int(r[0]),'open':float(r[1]),'high':float(r[2]),'low':float(r[3]),'close':float(r[4]),'volume':float(r[5] or 0)} for r in bars];self.end_ts=[r['ts']+seconds for r in self.rows];c=[r['close'] for r in self.rows];self.ema20=ema_series(c,20);self.ema50=ema_series(c,50);self.atr=atr_series(self.rows);self.rsi=rsi_series(c)
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
 if base_tf=='m5': targets=(('m15',900),('m30',1800),('h1',3600),('h4',14400),('d1',86400),('w1',604800))
 elif base_tf=='h4':targets=(('d1',86400),('w1',604800))
 else:targets=(('h4',14400),('d1',86400),('w1',604800))
 for name,sec in targets:frames[name]=Frame(name,sec,resample_bars(rows,sec))
 return frames,base_tf,base_sec
def build_candidates(market,rows):
 frames,base_tf,base_sec=build_frames(market,rows);base=frames[base_tf];loc_name='m15' if base_tf=='m5' else base_tf;loc_f=frames[loc_name];cands=[]
 for i in range(60,len(base.rows)-1):
  ts=base.rows[i]['ts']+base_sec
  if not is_market_day(ts,market):continue
  for side in (1,-1):
   his=[tf for tf in ('w1','d1','h4','h1') if tf in frames];align=sum(1 if frames[tf].trend(frames[tf].idx_at(ts))==side else -1 if frames[tf].trend(frames[tf].idx_at(ts))==-side else 0 for tf in his);align_norm=max(0,align/max(1,len(his))) if align>0 else 0;lidx=loc_f.idx_at(ts);loc=0
   if lidx>=0:
    lt=loc_f.trend(lidx);e=loc_f.ema20[lidx];a=loc_f.atr[lidx]
    if lt==side and e is not None and a and a>0:
     dev=(loc_f.rows[lidx]['close']-e)/a
     if (side==1 and -1<=dev<=.8) or (side==-1 and -.8<=dev<=1):loc=max(0,1-abs(dev))
   highs=[base.rows[j]['high'] for j in range(i-5,i)];lows=[base.rows[j]['low'] for j in range(i-5,i)];trig=1.0 if (side==1 and base.rows[i]['close']>max(highs)) or (side==-1 and base.rows[i]['close']<min(lows)) else 0;rsi=base.rsi[i];rs=1.0 if rsi is not None and ((side==1 and 45<=rsi<=75) or (side==-1 and 25<=rsi<=55)) else 0;score=.35*align_norm+.30*loc+.25*trig+.10*rs
   if trig and align_norm>0 and loc>.2:
    atr=base.atr[i]
    if not atr or atr<=0:continue
    lo=min(base.rows[j]['low'] for j in range(max(0,i-8),i+1));hi=max(base.rows[j]['high'] for j in range(max(0,i-8),i+1));sd=max(.8*atr,base.rows[i]['close']-lo if side==1 else hi-base.rows[i]['close']);cands.append({'i':i,'ts':ts,'day':daykey(ts),'side':side,'score':round(score,6),'stop_dist':round(sd,8),'atr':round(atr,8)})
 return cands
def build_or_load_candidates(symbol,market,rows,cache_dir):
 h=dcache.compute_data_hash(rows);sh=dcache.feature_schema_hash(FEATURE_SCHEMA);x=dcache.load_feature(cache_dir,symbol,h,sh) if cache_dir else None
 if x is not None:return x
 x=build_candidates(market,rows)
 if cache_dir:dcache.save_feature(cache_dir,symbol,h,sh,x)
 return x
def simulate_trade(base,c,rr,market):
 i=c['i'];side=c['side'];atr=base.atr[i] or c['atr'];entry=base.rows[i+1]['open']+side*COST_ATR[market]*atr;sl=entry-side*c['stop_dist'];tp=entry+side*rr*c['stop_dist'];hold=max(6,int(12*3600/base.seconds))
 for j in range(i+1,min(len(base.rows),i+1+hold)):
  z=base.rows[j];hs=z['low']<=sl if side==1 else z['high']>=sl;ht=z['high']>=tp if side==1 else z['low']<=tp
  if hs:return {'outcome':'SL','r':-1.0}
  if ht:return {'outcome':'TP','r':rr}
 return {'outcome':'TIMEOUT','r':0.0}
def evaluate_candidates(candidates,base,rr,threshold,max_trades,market,start_ts,end_ts):
 by=defaultdict(list)
 for c in candidates:
  if start_ts<=c['ts']<end_ts and c['score']>=threshold:by[c['day']].append(c)
 trades=[];counts={}
 for day,arr in sorted(by.items()):
  for c in sorted(arr,key=lambda x:x['score'],reverse=True)[:max_trades]:
   r=simulate_trade(base,c,rr,market)
   if r:trades.append({**c,**r});counts[day]=counts.get(day,0)+1
 n=len(trades);tp=sum(t['outcome']=='TP' for t in trades);wr=100*tp/n if n else 0;mean=statistics.mean([t['r'] for t in trades]) if n else -9
 return {'trades':n,'daysTraded':len(counts),'eligibleDays':len(by),'coveragePct':100.0 if by and len(counts)==len(by) else 0.0,'tp':tp,'sl':sum(t['outcome']=='SL' for t in trades),'timeout':sum(t['outcome']=='TIMEOUT' for t in trades),'winRate':round(wr,2),'meanR':round(mean,4),'maxTradesInDay':max(counts.values(),default=0)}
def stats_ok(s):return bool(s) and s.get('trades',0)>0 and s.get('coveragePct')==100 and s.get('maxTradesInDay',99)<=3 and s.get('winRate',0)>=REQUIRED_WR and s.get('meanR',-9)>0
def _split(rows):
 n=len(rows);a=int(n*.60);b=int(n*.82);return rows[a]['ts'],rows[b]['ts'],rows[-1]['ts']+1
def select_profile(symbol,market,rows,cache_dir=None):
 if len(rows)<MIN_BARS[BASE_TF[market]]:return None,{'reason':'INSUFFICIENT_BARS','bars':len(rows)}
 frames,btf,_=build_frames(market,rows);base=frames[btf];c=build_or_load_candidates(symbol,market,rows,cache_dir);dev0,val0,end=_split(base.rows);best=None
 for rr in ALLOWED_RR:
  for th in THRESHOLDS:
   for mt in MAX_TRADES_OPTIONS:
    d=evaluate_candidates(c,base,rr,th,mt,market,dev0,val0);v=evaluate_candidates(c,base,rr,th,mt,market,val0,end);rank=(1 if stats_ok(v) else 0,v['winRate'],v['meanR'],d['winRate'],d['meanR'])
    if best is None or rank>best[0]:best=(rank,{'rr':rr,'threshold':th,'maxTrades':mt,'validationStart':val0,'end':end},d,v)
 return (best[1],{'dev':best[2],'validation':best[3]}) if best else (None,{'reason':'NO_CANDIDATE'})
def run_fast(symbol,market,rows,cache_dir=None):
 p,ev=select_profile(symbol,market,rows,cache_dir);v=ev.get('validation') or {};ok=bool(p) and stats_ok(v);return {'symbol':symbol,'market':market,'mode':'fast','pass':ok,'reasons':[] if ok else ['NO_DEV_PROFILE' if not p else 'VALIDATION_FAIL'],'profile':p,'dev':ev.get('dev'),'validation':v}
def run_final(symbol,market,rows,cache_dir,profile):
 frames,btf,_=build_frames(market,rows);base=frames[btf];c=build_or_load_candidates(symbol,market,rows,cache_dir);start=int(profile.get('validationStart',base.rows[int(len(base.rows)*.82)]['ts']));end=int(profile.get('end',base.rows[-1]['ts']+1));o=evaluate_candidates(c,base,float(profile['rr']),float(profile['threshold']),int(profile['maxTrades']),market,start,end);ok=stats_ok(o);return {'symbol':symbol,'market':market,'mode':'final','pass':ok,'reasons':[] if ok else ['OOS_FAIL'],'profile':profile,'oos':o}