#!/usr/bin/env python3
import json, math, statistics, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT']
INTERVAL='1m'
DAYS=7
START_EQUITY=73.0
ROUNDTRIP_COST_RATE=0.00130  # 13 bps fee+slippage proxy
MAX_HOLD_BARS=7
MIN_PLANNED_NET_USD=1.00


def get_json(url, retries=5):
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'trading-api-v51-backtest'})
            with urllib.request.urlopen(req,timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            if i==retries-1: raise
            time.sleep(1.2*(i+1))


def fetch_klines(symbol):
    end_ms=int(time.time()*1000)
    start_ms=end_ms-DAYS*24*60*60*1000
    out=[]; cursor=start_ms
    while cursor<end_ms:
        q=urllib.parse.urlencode({'symbol':symbol,'interval':INTERVAL,'startTime':cursor,'endTime':end_ms,'limit':1000})
        rows=get_json('https://data-api.binance.vision/api/v3/klines?'+q)
        if not rows: break
        for x in rows:
            out.append({'t':int(x[0]),'o':float(x[1]),'h':float(x[2]),'l':float(x[3]),'c':float(x[4]),'v':float(x[5])})
        nxt=int(rows[-1][0])+60_000
        if nxt<=cursor: break
        cursor=nxt
        if len(rows)<1000: break
        time.sleep(.08)
    seen={}
    for r in out: seen[r['t']]=r
    return [seen[k] for k in sorted(seen)]


def ema(vals,n):
    a=2/(n+1); out=[]; e=None
    for x in vals:
        e=x if e is None else a*x+(1-a)*e
        out.append(e)
    return out


def atr(rows,n=14):
    tr=[]
    for i,r in enumerate(rows):
        pc=rows[i-1]['c'] if i else r['c']
        tr.append(max(r['h']-r['l'],abs(r['h']-pc),abs(r['l']-pc)))
    return ema(tr,n)


def rolling_mean(vals,n):
    out=[None]*len(vals); s=0.0
    for i,x in enumerate(vals):
        s+=x
        if i>=n: s-=vals[i-n]
        if i>=n-1: out[i]=s/n
    return out


def prior_extreme(rows,i,n,kind):
    if i<n: return None
    xs=rows[i-n:i]
    return max(x['h'] for x in xs) if kind=='high' else min(x['l'] for x in xs)


def lane_signal(rows,i,e20,e50,a14,v20):
    if i<60 or i+1>=len(rows) or not v20[i] or a14[i]<=0: return None
    r=rows[i]; prev=rows[i-1]; volr=r['v']/max(v20[i],1e-12); atrv=a14[i]
    hi20=prior_extreme(rows,i,20,'high'); lo20=prior_extreme(rows,i,20,'low')
    if hi20 is None: return None

    # 1) Liquidity sweep -> reclaim
    if r['l']<lo20 and r['c']>lo20 and r['c']>r['o'] and r['c']>prev['c'] and volr>=1.10:
        return ('LIQUIDITY_SWEEP_RECLAIM','Buy',1.45,volr)
    if r['h']>hi20 and r['c']<hi20 and r['c']<r['o'] and r['c']<prev['c'] and volr>=1.10:
        return ('LIQUIDITY_SWEEP_RECLAIM','Sell',1.45,volr)

    # 2) Breakout -> retest -> continuation. Find a recent breakout level, never chase current breakout candle.
    for j in range(max(25,i-5),i):
        jhi=prior_extreme(rows,j,20,'high'); jlo=prior_extreme(rows,j,20,'low')
        if jhi is None or not v20[j]: continue
        jvol=rows[j]['v']/max(v20[j],1e-12)
        if rows[j]['c']>jhi and jvol>=1.10 and e20[i]>e50[i]:
            level=jhi
            if r['l']<=level+0.16*atrv and r['c']>level and r['c']>r['o'] and r['c']>prev['c'] and volr>=.85:
                return ('BREAKOUT_RETEST_CONTINUATION','Buy',1.45 if volr<1.45 else 2.0,volr)
        if rows[j]['c']<jlo and jvol>=1.10 and e20[i]<e50[i]:
            level=jlo
            if r['h']>=level-0.16*atrv and r['c']<level and r['c']<r['o'] and r['c']<prev['c'] and volr>=.85:
                return ('BREAKOUT_RETEST_CONTINUATION','Sell',1.45 if volr<1.45 else 2.0,volr)

    # 3) Trend pullback -> micro re-acceleration
    recent=rows[i-3:i]
    if e20[i]>e50[i] and e20[i]>e20[i-3]:
        touched=any(x['l']<=e20[i]+0.20*atrv for x in recent)
        if touched and r['c']>prev['h'] and r['c']>e20[i] and r['c']>r['o'] and volr>=.90:
            return ('TREND_PULLBACK_REACCELERATION','Buy',1.45 if volr<1.50 else 2.0,volr)
    if e20[i]<e50[i] and e20[i]<e20[i-3]:
        touched=any(x['h']>=e20[i]-0.20*atrv for x in recent)
        if touched and r['c']<prev['l'] and r['c']<e20[i] and r['c']<r['o'] and volr>=.90:
            return ('TREND_PULLBACK_REACCELERATION','Sell',1.45 if volr<1.50 else 2.0,volr)
    return None


def stop_target(rows,i,lane,side,entry,a14):
    atrv=a14[i]
    if lane=='LIQUIDITY_SWEEP_RECLAIM':
        anchor=rows[i]['l'] if side=='Buy' else rows[i]['h']; rr=1.45
        raw=abs(entry-(anchor-0.08*atrv if side=='Buy' else anchor+0.08*atrv))
        minp,maxp=.0012,.0045
    elif lane=='BREAKOUT_RETEST_CONTINUATION':
        anchor=rows[i]['l'] if side=='Buy' else rows[i]['h']; rr=1.60
        raw=abs(entry-(anchor-0.07*atrv if side=='Buy' else anchor+0.07*atrv))
        minp,maxp=.0011,.0040
    else:
        recent=rows[max(0,i-2):i+1]
        anchor=min(x['l'] for x in recent) if side=='Buy' else max(x['h'] for x in recent); rr=1.50
        raw=abs(entry-(anchor-0.05*atrv if side=='Buy' else anchor+0.05*atrv))
        minp,maxp=.0010,.0036
    dist=min(max(raw,entry*minp),entry*maxp)
    sl=entry-dist if side=='Buy' else entry+dist
    tp=entry+dist*rr if side=='Buy' else entry-dist*rr
    return sl,tp,rr,dist


def backtest(symbol,rows):
    c=[x['c'] for x in rows]; v=[x['v'] for x in rows]
    e20=ema(c,20); e50=ema(c,50); a14=atr(rows,14); v20=rolling_mean(v,20)
    equity=START_EQUITY; peak=equity; maxdd=0; trades=[]; skips=0; next_free=0
    for i in range(60,len(rows)-MAX_HOLD_BARS-2):
        if i<next_free: continue
        sig=lane_signal(rows,i,e20,e50,a14,v20)
        if not sig: continue
        lane,side,risk_pct,volr=sig
        entry=rows[i+1]['o']
        sl,tp,rr,dist=stop_target(rows,i,lane,side,entry,a14)
        if not (entry>0 and dist>0): continue
        risk_usd=equity*risk_pct/100
        qty=risk_usd/dist
        notional=qty*entry
        cost=notional*ROUNDTRIP_COST_RATE
        planned_net=risk_usd*rr-cost
        if planned_net<MIN_PLANNED_NET_USD:
            skips+=1; continue
        exit_px=rows[i+MAX_HOLD_BARS+1]['c']; reason='TIME'; hold=MAX_HOLD_BARS
        for k in range(i+1,i+MAX_HOLD_BARS+1):
            b=rows[k]
            if side=='Buy':
                hit_sl=b['l']<=sl; hit_tp=b['h']>=tp
            else:
                hit_sl=b['h']>=sl; hit_tp=b['l']<=tp
            if hit_sl and hit_tp:
                exit_px=sl; reason='SL_SAME_BAR_CONSERVATIVE'; hold=k-i; break
            if hit_sl:
                exit_px=sl; reason='SL'; hold=k-i; break
            if hit_tp:
                exit_px=tp; reason='TP'; hold=k-i; break
        gross=(exit_px-entry)*qty*(1 if side=='Buy' else -1)
        net=gross-cost
        before=equity; equity=max(.01,equity+net); peak=max(peak,equity); dd=(peak-equity)/peak*100 if peak else 0; maxdd=max(maxdd,dd)
        mae=0.0; mfe=0.0
        for k in range(i+1,i+hold+1):
            b=rows[k]
            adverse=(entry-b['l']) if side=='Buy' else (b['h']-entry)
            favorable=(b['h']-entry) if side=='Buy' else (entry-b['l'])
            mae=max(mae,adverse/dist); mfe=max(mfe,favorable/dist)
        trades.append({'symbol':symbol,'t':rows[i]['t'],'lane':lane,'side':side,'riskPct':risk_pct,'entry':entry,'sl':sl,'tp':tp,'rr':rr,'plannedNet':planned_net,'net':net,'gross':gross,'cost':cost,'holdMin':hold,'reason':reason,'maeR':mae,'mfeR':mfe,'equityBefore':before,'equityAfter':equity,'volRatio':volr})
        next_free=i+hold+1
    return trades,skips,equity,maxdd


def stats(trades):
    if not trades:return {'trades':0,'wins':0,'losses':0,'winRate':0,'net':0,'pf':0,'expectancy':0,'avgWin':0,'avgLoss':0,'avgHoldMin':0,'avgMaeR':0,'avgMfeR':0}
    wins=[x['net'] for x in trades if x['net']>0]; losses=[x['net'] for x in trades if x['net']<0]
    win_sum=sum(wins); loss_sum=abs(sum(losses)); n=len(trades)
    return {'trades':n,'wins':len(wins),'losses':len(losses),'winRate':len(wins)/n,'net':sum(x['net'] for x in trades),'pf':win_sum/loss_sum if loss_sum>0 else (99 if win_sum>0 else 0),'expectancy':sum(x['net'] for x in trades)/n,'avgWin':statistics.mean(wins) if wins else 0,'avgLoss':abs(statistics.mean(losses)) if losses else 0,'avgHoldMin':statistics.mean(x['holdMin'] for x in trades),'avgMaeR':statistics.mean(x['maeR'] for x in trades),'avgMfeR':statistics.mean(x['mfeR'] for x in trades)}


def fmt(s):
    return {k:(round(v,4) if isinstance(v,float) else v) for k,v in s.items()}


def main():
    report={'generatedAt':datetime.now(timezone.utc).isoformat(),'source':'BINANCE_PUBLIC_SPOT_1M_PRICE_VOLUME_PROXY','days':DAYS,'symbols':{},'lanes':{},'assumptions':{'startEquityUsdPerSymbol':START_EQUITY,'roundTripCostRate':ROUNDTRIP_COST_RATE,'maxHoldMinutes':MAX_HOLD_BARS,'minPlannedNetUsd':MIN_PLANNED_NET_USD,'sameBarTpSl':'SL_FIRST_CONSERVATIVE','fullFidelityMicrostructure':False}}
    all_trades=[]
    for s in SYMBOLS:
        rows=fetch_klines(s)
        trades,skips,eq,dd=backtest(s,rows)
        all_trades.extend(trades)
        z=fmt(stats(trades)); z.update({'bars':len(rows),'skippedBelowOneUsd':skips,'endingEquityUsd':round(eq,4),'returnPct':round((eq/START_EQUITY-1)*100,3),'maxDrawdownPct':round(dd,3)})
        report['symbols'][s]=z
    by_lane=defaultdict(list)
    for x in all_trades: by_lane[x['lane']].append(x)
    for lane,xs in by_lane.items(): report['lanes'][lane]=fmt(stats(xs))
    report['aggregate']=fmt(stats(all_trades)); report['aggregate']['tradeCount']=len(all_trades)
    with open('v51-proxy-backtest-report.json','w') as f: json.dump(report,f,indent=2)
    with open('v51-proxy-backtest-trades.json','w') as f: json.dump(all_trades,f)
    print('V51_PROXY_BACKTEST_REPORT='+json.dumps(report,separators=(',',':')))
    print('\nSUMMARY')
    for s,z in report['symbols'].items(): print(s,z)
    print('LANES',report['lanes'])
    print('AGG',report['aggregate'])

if __name__=='__main__': main()
