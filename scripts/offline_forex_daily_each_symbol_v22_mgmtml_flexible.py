#!/usr/bin/env python3
import scripts.offline_forex_daily_each_symbol_v21_mgmtml as v

v.OUT='data/offline_forex_daily_each_symbol_v22_mgmtml_flexible.json'
v.MGMT_THS=(.10,.20,.30,.40,.50,.60,.70,.80,.90)
v.MIN_AGES=(1,2,3,4,6)
v.EXECS=[(1.0,.55,4,24),(1.0,.65,6,24),(1.0,.85,12,30),(1.0,1.05,18,36),(2.0,.65,6,36)]

def flexible_rank(s):
    ok=s['missing']==0 and s['resolved']>=7 and s['cutRate']<=70 and s['meanR']>0
    return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],-s['cutRate'],s['resolved'])
v.rank=flexible_rank

if __name__=='__main__':v.main()
