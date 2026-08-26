#!/usr/bin/env python3
import json, math, os, random, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

STATE=Path(os.getenv('CRYPTO_RESEARCH_STATE_DIR','/var/lib/trading/crypto-50d'))
BASE=os.getenv('BINANCE_FUTURES_BASE_URL','https://fapi.binance.com').rstrip('/')
TARGET=float(os.getenv('CRYPTO_TARGET_WR','80'))
MIN_TRADES=int(os.getenv('CRYPTO_MIN_TRADES','20'))
WINDOW_DAYS=int(os.getenv('CRYPTO_WINDOW_DAYS','50'))
PAUSE=float(os.getenv('CRYPTO_ROUND_PAUSE_SECONDS','2'))
DEFAULT='BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,LINKUSDT,AVAXUSDT,DOTUSDT,LTCUSDT,BCHUSDT,TRXUSDT,ATOMUSDT,NEARUSDT,APTUSDT,ARBUSDT,OPUSDT,SUIUSDT,INJUSDT,FILUSDT,ETCUSDT,UNIUSDT,AAVEUSDT,ALGOUSDT,XLMUSDT,ICPUSDT,HBARUSDT,TONUSDT,SEIUSDT,TIAUSDT,WIFUSDT,PEPEUSDT,SHIBUSDT'
SYMBOLS=[x.strip().upper() for x in os.getenv('BREAKOUT_CRYPTO_SYMBOLS',DEFAULT).split(',') if x.strip()]
for p in [STATE,STATE/'cache',STATE/'trades',STATE/'reports',STATE/'profiles']: p.mkdir(parents=True,exist_ok=True)

def now(): return datetime.now(timezone.utc).isoformat()
def atomic(path,obj):
    t=path.with_suffix(path.suffix+'.tmp'); t.write_text(json.dumps(obj,indent=2,sort_keys=True)); t.replace(path)
def append(path,obj):
    with path.open('a') as f: f.write(json.dumps(obj,separators=(',',':'))+'\n')
def get(path,params):
    u=BASE+path+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(u,headers={'User-Agent':'trading-api-research/1'})
    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
def exchange_symbols():
    d=get('/fapi/v1/exchangeInfo',{}); return {x['symbol'] for x in d['symbols'] if x.get('contractType')=='PERPETUAL' and x.get('quoteAsset')=='USDT' and x.get('status')=='TRADING'}
def klines(symbol,days=420):
    cp=STATE/'cache'/f'{symbol}-15m.json'; cutoff=int(time.time()*1000)-days*86400000
    if cp.exists() and time.time()-cp.stat().st_mtime<21600:
        d=json.loads(cp.read_text());
        if d and d[0][0]<=cutoff+86400000: return d
    out=[]; start=cutoff
    while True:
        batch=get('/fapi/v1/klines',{'symbol':symbol,'interval':'15m','startTime':start,'limit':1500})
        if not batch: break
        out.extend(batch); nxt=int(batch[-1][0])+900000
        if nxt<=start or len(batch)<1500 or nxt>=int(time.time()*1000): break
        start=nxt; time.sleep(.08)
    rows=[[int(x[0]),float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])] for x in out]
    atomic(cp,rows); return rows

def ema(vals,n):
    a=2/(n+1); out=[]; e=vals[0]
    for v in vals: e=v*a+e*(1-a); out.append(e)
    return out
def atr(rows,n=14):
    tr=[]
    for i,x in enumerate(rows): tr.append(x[2]-x[3] if i==0 else max(x[2]-x[3],abs(x[2]-rows[i-1][4]),abs(x[3]-rows[i-1][4])))
    return ema(tr,n)
def profile(seed):
    r=random.Random(seed)
    family=r.choice(['trend_breakout','pullback','mean_reclaim'])
    return {'family':family,'fast':r.choice([8,10,12,16,20]),'slow':r.choice([32,40,50,64,80]),'lookback':r.choice([8,12,16,20,24,32]),'atr_mult':r.choice([0.8,1.0,1.2,1.5,1.8]),'vol_mult':r.choice([0.8,1.0,1.2,1.5]),'side':r.choice(['both','long','short'])}
def run(rows,start,end,p,rr):
    c=[x[4] for x in rows]; v=[x[5] for x in rows]; ef=ema(c,p['fast']); es=ema(c,p['slow']); at=atr(rows); trades=[]; i=max(p['slow'],p['lookback'],20)
    while i<len(rows)-2:
        ts=rows[i][0]
        if ts<start: i+=1; continue
        if ts>=end: break
        hi=max(x[2] for x in rows[i-p['lookback']:i]); lo=min(x[3] for x in rows[i-p['lookback']:i]); av=sum(v[i-20:i])/20
        long=short=False
        if p['family']=='trend_breakout': long=c[i]>hi and ef[i]>es[i]; short=c[i]<lo and ef[i]<es[i]
        elif p['family']=='pullback': long=ef[i]>es[i] and rows[i][3]<=ef[i] and c[i]>ef[i]; short=ef[i]<es[i] and rows[i][2]>=ef[i] and c[i]<ef[i]
        else: long=c[i]>ef[i] and c[i-1]<=ef[i-1] and ef[i]>es[i]; short=c[i]<ef[i] and c[i-1]>=ef[i-1] and ef[i]<es[i]
        if v[i]<av*p['vol_mult']: long=short=False
        if p['side']=='long': short=False
        if p['side']=='short': long=False
        side=1 if long else (-1 if short else 0)
        if not side: i+=1; continue
        entry=rows[i+1][1]; risk=max(at[i]*p['atr_mult'],entry*0.0015); sl=entry-side*risk; tp=entry+side*risk*rr; outcome=None; exit_i=None
        for j in range(i+1,min(len(rows),i+1+96)):
            h,l=rows[j][2],rows[j][3]
            hit_sl=l<=sl if side==1 else h>=sl; hit_tp=h>=tp if side==1 else l<=tp
            if hit_sl and hit_tp: outcome=-1; exit_i=j; break
            if hit_tp: outcome=rr; exit_i=j; break
            if hit_sl: outcome=-1; exit_i=j; break
        if outcome is None: outcome=0; exit_i=min(len(rows)-1,i+96)
        # conservative round-trip cost: 10 bps, expressed in R
        net=outcome-(entry*0.001/risk)
        trades.append({'t':rows[i+1][0],'side':'LONG' if side==1 else 'SHORT','entry':entry,'sl':sl,'tp':tp,'grossR':outcome,'netR':net})
        i=exit_i+1
    wins=sum(1 for x in trades if x['grossR']>0); losses=sum(1 for x in trades if x['grossR']<0); n=wins+losses
    return {'trades':trades,'n':n,'wins':wins,'losses':losses,'wr':100*wins/n if n else 0,'netR':sum(x['netR'] for x in trades),'expectancy':sum(x['netR'] for x in trades)/len(trades) if trades else 0}
def main():
    valid=exchange_symbols(); universe=[s for s in SYMBOLS if s in valid]; unavailable=[s for s in SYMBOLS if s not in valid]
    statep=STATE/'state.json'; state=json.loads(statep.read_text()) if statep.exists() else {'version':'CRYPTO-50D-V1','round':0,'qualified':{},'history':[]}
    atomic(STATE/'universe.json',{'configured':SYMBOLS,'active':universe,'unavailable':unavailable,'checkedAt':now()})
    while True:
        unresolved=[s for s in universe if s not in state['qualified']]
        if not unresolved:
            state['status']='TARGET_ACHIEVED_ALL_SYMBOLS'; state['updatedAt']=now(); atomic(statep,state); atomic(STATE/'reports'/'final.json',state); time.sleep(3600); continue
        symbol=unresolved[state['round']%len(unresolved)]; state['round']+=1; seed=random.SystemRandom().randrange(1,2**31); p=profile(seed)
        try:
            rows=klines(symbol); first,last=rows[0][0],rows[-1][0]; span=WINDOW_DAYS*86400000
            # reserve newest 25% of history for unseen validation
            split=first+int((last-first)*.75); maxdev=split-span
            if maxdev<=first: raise RuntimeError('insufficient history')
            rng=random.Random(seed); dev_start=rng.randrange(first,maxdev,900000); dev_end=dev_start+span
            candidates=[]
            for rr in (1,2):
                z=run(rows,dev_start,dev_end,p,rr); candidates.append((z['wr'],z['expectancy'],rr,z))
            _,_,rr,dev=max(candidates,key=lambda x:(x[0]>=TARGET and x[3]['n']>=MIN_TRADES,x[1],x[0]))
            frozen=dev['n']>=MIN_TRADES and dev['wr']>=TARGET and dev['expectancy']>0
            val=None; passed=False
            if frozen:
                vmax=last-span; vs=random.Random(seed^0x5A5A5A5A).randrange(split,vmax,900000) if vmax>split else split
                val=run(rows,vs,vs+span,p,rr); passed=val['n']>=MIN_TRADES and val['wr']>=TARGET and val['expectancy']>0
            rec={'round':state['round'],'at':now(),'symbol':symbol,'seed':seed,'windowDays':WINDOW_DAYS,'profile':p,'rr':rr,'dev':{k:v for k,v in dev.items() if k!='trades'},'validation':({k:v for k,v in val.items() if k!='trades'} if val else None),'pass':passed}
            append(STATE/'trials.jsonl',rec); atomic(STATE/'trades'/f"{symbol}-{state['round']}-dev.json",dev['trades'])
            if val: atomic(STATE/'trades'/f"{symbol}-{state['round']}-val.json",val['trades'])
            if passed:
                prof={'symbol':symbol,'lockedAt':now(),'seed':seed,'profile':p,'rr':rr,'validation':rec['validation']}; state['qualified'][symbol]=prof; atomic(STATE/'profiles'/f'{symbol}.json',prof)
            state['history']=(state.get('history',[])+[rec])[-500:]; state['status']='RESEARCH_RUNNING'; state['currentSymbol']=symbol; state['updatedAt']=now(); state['targetWR']=TARGET; state['windowDays']=WINDOW_DAYS; state['rrAllowed']=[1,2]; atomic(statep,state); atomic(STATE/'reports'/'current.json',state)
        except Exception as e:
            rec={'round':state['round'],'at':now(),'symbol':symbol,'error':repr(e),'pass':False}; append(STATE/'trials.jsonl',rec); state['lastError']=rec; state['updatedAt']=now(); atomic(statep,state); time.sleep(10)
        time.sleep(PAUSE)
if __name__=='__main__': main()
