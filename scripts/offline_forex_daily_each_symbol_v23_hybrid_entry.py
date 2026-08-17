#!/usr/bin/env python3
import scripts.offline_forex_daily_each_symbol_v21_mgmtml as v

v.OUT='data/offline_forex_daily_each_symbol_v23_hybrid_entry.json'
# rr, ATR risk floor, swing lookback H1, hold H1, limit offset ATR, expiry H1
v.EXECS=[
 (1.0,.55,6,24,.20,1),(1.0,.65,6,24,.35,2),(1.0,.65,12,30,.50,2),
 (1.0,.85,12,30,.70,3),(1.0,1.0,18,36,.35,2),
 (2.0,.65,6,36,.35,2),(2.0,.85,12,48,.50,3)
]
v.MGMT_THS=(.10,.20,.30,.40,.50,.60,.70,.80,.90)
v.MIN_AGES=(1,2,3,4,6)

def hybrid_exec(rows,i,side,cfg):
 rr,rf,sw,hold,off,expiry=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];entry=sig['close']-side*off*atr;ei=None
 # Limit first; if it never fills, compulsory market fallback at expiry.
 last=min(len(rows)-1,i+expiry)
 for j in range(i+1,last+1):
  if rows[j]['low']<=entry<=rows[j]['high']:ei=j;break
 if ei is None:
  ei=last
  entry=rows[ei]['close']
 if ei<=i:return None
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr)
 if risk<=0:return None
 sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold);states=[];best=-9;worst=9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0,'states':states,'entry':entry,'risk':risk}
  if hs:return {'result':'SL','r':-1.0,'states':states,'entry':entry,'risk':risk}
  if ht:return {'result':'TP','r':rr,'states':states,'entry':entry,'risk':risk}
  fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;adv=(x['low']-entry)/risk if side==1 else (entry-x['high'])/risk;best=max(best,fav);worst=min(worst,adv);cur=(x['close']-entry)/risk*side
  em20=(x['close']-x['ema20'])/x['atr']*side if x.get('ema20') is not None and x.get('atr') else 0;em50=(x['close']-x['ema50'])/x['atr']*side if x.get('ema50') is not None and x.get('atr') else 0
  states.append({'age':j-ei+1,'r':cur,'best':best,'worst':worst,'ema20':em20,'ema50':em50,'rsi':(x.get('rsi') or 50)/100,'adx':(x.get('adx') or 0)/50,'mom':side*(x.get('mom6atr') or 0)/3,'h4':side*(x.get('h4') or 0)})
 lastc=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(lastc-entry)/risk*side)),'states':states,'entry':entry,'risk':risk}
v.execraw=hybrid_exec

def rank2(s):
 ok=s['missing']==0 and s['resolved']>=8 and s['cutRate']<=65 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],-s['cutRate'],s['resolved'])
v.rank=rank2
if __name__=='__main__':v.main()
