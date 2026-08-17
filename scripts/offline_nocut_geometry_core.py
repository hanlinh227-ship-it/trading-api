#!/usr/bin/env python3
"""Offline OHLC backtest helpers only. No broker/exchange routing."""

def terminal(rows,ei,entry,side,atr,rr,rf,hold):
    if ei is None or ei>=len(rows): return ('TIMEOUT',0.0,0)
    risk=max(rf*atr,.12*atr); sl=entry-side*risk; tp=entry+side*rr*risk
    end=min(len(rows),ei+hold); last=ei
    for j in range(ei,end):
        last=j; x=rows[j]
        hs=x['low']<=sl if side==1 else x['high']>=sl
        ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0,j-ei+1)
        if hs:return ('SL',-1.0,j-ei+1)
        if ht:return ('TP',rr,j-ei+1)
    return ('TIMEOUT',0.0,last-ei+1)

def simulate(rows,i,base_side,cfg):
    mode,p1,p2,rr,rf,hold=cfg
    if i+1>=len(rows) or rows[i].get('atr') is None:return ('TIMEOUT',0.0,0)
    sig=rows[i]; atr=sig['atr']
    if mode=='MKT':return terminal(rows,i+1,rows[i+1]['open'],base_side,atr,rr,rf,hold)
    expiry=int(p2); last=min(len(rows)-2,i+expiry)
    if mode in ('PB','BRK'):
        target=sig['close']+base_side*p1*atr*(1 if mode=='BRK' else -1); ei=None
        for j in range(i+1,last+1):
            if rows[j]['low']<=target<=rows[j]['high']:ei=j;break
        if ei is not None:return terminal(rows,ei,target,base_side,atr,rr,rf,hold)
        fi=last+1;return terminal(rows,fi,rows[fi]['open'],base_side,atr,rr,rf,hold)
    if mode=='DUAL_BRK':
        lb=int(p1); recent=rows[max(0,i-lb+1):i+1]
        up=max(x['high'] for x in recent)+.10*atr; dn=min(x['low'] for x in recent)-.10*atr
        for j in range(i+1,last+1):
            hu=rows[j]['high']>=up; ld=rows[j]['low']<=dn
            if hu and ld:return ('SL',-1.0,1)
            if hu:return terminal(rows,j,up,1,atr,rr,rf,hold)
            if ld:return terminal(rows,j,dn,-1,atr,rr,rf,hold)
        fi=last+1;return terminal(rows,fi,rows[fi]['open'],base_side,atr,rr,rf,hold)
    if mode=='DUAL_FADE':
        up=sig['close']+p1*atr; dn=sig['close']-p1*atr
        for j in range(i+1,last+1):
            hu=rows[j]['high']>=up; ld=rows[j]['low']<=dn
            if hu and ld:return ('SL',-1.0,1)
            if hu:return terminal(rows,j,up,-1,atr,rr,rf,hold)
            if ld:return terminal(rows,j,dn,1,atr,rr,rf,hold)
        fi=last+1;return terminal(rows,fi,rows[fi]['open'],base_side,atr,rr,rf,hold)
    return ('TIMEOUT',0.0,0)

def cfgs():
    out=[]
    for rr in (1.0,2.0):
      for rf in (.35,.50,.75,1.0):
       for hold in (12,18,24):
        out.append(('MKT',0,0,rr,rf,hold))
        for off in (.25,.50,.75,1.0):
         for ex in (1,2,3):out.append(('PB',off,ex,rr,rf,hold))
        for off in (.15,.30,.50):
         for ex in (1,2,3):out.append(('BRK',off,ex,rr,rf,hold))
        for lb in (4,8):
         for ex in (2,4):out.append(('DUAL_BRK',lb,ex,rr,rf,hold))
        for off in (.50,.75,1.0):
         for ex in (2,4):out.append(('DUAL_FADE',off,ex,rr,rf,hold))
    return out

def stats(z,expected):
    tp=sum(x[0]=='TP' for x in z); sl=sum(x[0]=='SL' for x in z); to=sum(x[0]=='TIMEOUT' for x in z); n=len(z)
    return {'trades':n,'expectedDays':expected,'tp':tp,'sl':sl,'timeout':to,
            'wrAllTrades':round(100*tp/n,2) if n else 0,
            'meanRAllTrades':round(sum(x[1] for x in z)/n,3) if n else -9}
