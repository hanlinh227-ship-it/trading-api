#!/usr/bin/env python3
import scripts.offline_forex_daily_each_symbol_v19_managed as v

# rr, risk floor, swing, hold, review age, hard current-R floor, minimum favorable progress by review, trail trigger, trail giveback floor
v.CFGS=[
 (1.0,.65,6,24,1,-.10,-9,.55,.10),
 (1.0,.65,6,24,1, .00,-9,.55,.15),
 (1.0,.65,6,24,2,-.20,.10,.60,.10),
 (1.0,.65,6,24,2,-.10,.20,.60,.15),
 (1.0,.65,6,24,3,-.20,.25,.65,.15),
 (1.0,.85,12,30,1,-.10,-9,.55,.10),
 (1.0,.85,12,30,2,-.20,.10,.60,.10),
 (1.0,.85,12,30,2,-.10,.20,.60,.15),
 (1.0,.85,12,30,3,-.20,.25,.65,.15),
]
v.OUT='data/offline_forex_daily_each_symbol_v20_progress.json'

def progress_exec(rows,i,side,cfg):
 rr,rf,sw,hold,ca,cur_floor,progress_min,trail_trigger,trail_floor=cfg
 if i+1>=len(rows) or not rows[i].get('atr'):return None
 atr=rows[i]['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr);sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold);best=-9
 for j in range(ei,end):
  x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
  if hs and ht:return {'result':'SL','r':-1.0}
  if hs:return {'result':'SL','r':-1.0}
  if ht:return {'result':'TP','r':rr}
  fav=((x['high']-entry)/risk if side==1 else (entry-x['low'])/risk);best=max(best,fav);age=j-ei+1;cur=(x['close']-entry)/risk*side
  if age>=ca:
   if cur<=cur_floor:return {'result':'CUT','r':max(-1,cur)}
   if progress_min>-8 and best<progress_min:return {'result':'CUT','r':max(-1,cur)}
   if best>=trail_trigger and cur<=trail_floor:return {'result':'CUT','r':max(-1,cur)}
 last=rows[end-1]['close'];return {'result':'CUT','r':max(-1,min(rr,(last-entry)/risk*side))}

v.execm=progress_exec
if __name__=='__main__':v.main()
