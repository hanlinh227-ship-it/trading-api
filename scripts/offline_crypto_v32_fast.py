#!/usr/bin/env python3
import scripts.offline_crypto_v32_market_symbol_gate as m

def fast_choose(train_dates,rows,states,perf):
    best=None
    for k in (2,3):
     for rec in (False,True):
      for dwr in (45,50,55,60):
       for dr in (0,.1,.2):
        for topk in (3,4,5):
         for floor in (.5,.65,.8):
          for side in ('ANY','BREADTH_ALIGN','PREDICT_BEST'):
           for wi in range(len(m.WEIGHTS)):
            p=(k,rec,dwr,dr,topk,floor,side,wi);s=m.inner_eval(train_dates,rows,states,perf,p)
            if s['n']<15 or s['dates']<3:continue
            score=(1 if s['wr']>=80 else 0,s['wr'],s['meanR'],min(s['n'],35))
            if best is None or score>best[0]:best=(score,p,s)
    return best

m.choose=fast_choose
m.main()
