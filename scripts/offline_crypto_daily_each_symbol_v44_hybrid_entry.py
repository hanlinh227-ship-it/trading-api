#!/usr/bin/env python3
import scripts.offline_crypto_daily_each_symbol_v42_mgmtml as v

v.OUT='data/offline_crypto_daily_each_symbol_v44_hybrid_entry.json'
# rr, ATR risk floor, swing 4H bars, hold bars, limit offset ATR, expiry bars
v.EXECS=[
 (1.0,.55,3,6,.25,1),(1.0,.65,5,6,.50,1),(1.0,.65,5,9,.70,1),
 (1.0,.85,8,9,.90,1),(1.0,1.0,10,9,.50,1),
 (2.0,.65,5,9,.50,1),(2.0,.85,8,12,.70,1)
]
v.MGMT_THS=(.10,.20,.30,.40,.50,.60,.70,.80,.90)
v.MIN_AGES=(1,2,3,4)

def hybrid_exec(rows,i,side,cfg):
 rr,rf,sw,hold,off,expiry=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 sig=rows[i];atr=sig['atr'];entry=sig['close']-side*off*atr;ei=None;last=min(len(rows)-1,i+expiry)
 for j in range(i+1,last+1):
  if rows[j]['low']<=entry<=rows[j]['high']:ei=j;break
 if ei is None:
  ei=last;entry=rows[ei]['close']
 if ei<=i:return None
 recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr)
 if risk<=0:return None
 sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold);states=[];best=-9;worst=9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0,'states':states}
  if hs:return {'result':'SL','r':-1.0,'states':states}
  if ht:return {'result':'TP','r':rr,'states':states}
  fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;adv=(x['low']-entry)/risk if side==1 else (entry-x['high'])/risk;best=max(best,fav);worst=min(worst,adv);cur=(x['close']-entry)/risk*side
  em20=(x['close']-x['ema20'])/x['atr']*side if x.get('ema20') is not None and x.get('atr') else 0;em50=(x['close']-x['ema50'])/x['atr']*side if x.get('ema50') is not None and x.get('atr') else 0
  states.append({'age':j-ei+1,'r':cur,'best':best,'worst':worst,'ema20':em20,'ema50':em50,'rsi':(x.get('rsi') or 50)/100,'adx':(x.get('adx') or 0)/50,'mom':side*(x.get('mom24atr') or 0)/4,'d1':side*(x.get('d1') or 0)})
 lastc=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(lastc-entry)/risk*side)),'states':states}
v.execraw=hybrid_exec

def rank2(s):
 ok=s['missing']==0 and s['resolved']>=9 and s['cutRate']<=70 and s['meanR']>0
 return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],-s['cutRate'],s['resolved'])
v.rank=rank2
if __name__=='__main__':v.main()
