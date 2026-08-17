#!/usr/bin/env python3
import scripts.offline_crypto_daily_each_symbol_v42_mgmtml as v

v.OUT='data/offline_crypto_daily_each_symbol_v43_mgmtml_flexible.json'
v.MGMT_THS=(.10,.20,.30,.40,.50,.60,.70,.80,.90)
v.MIN_AGES=(1,2,3,4)
v.EXECS=[(1.0,.55,3,6),(1.0,.65,5,6),(1.0,.85,8,9),(1.0,1.05,10,9),(2.0,.65,5,9)]

def flexible_rank(s):
    ok=s['missing']==0 and s['resolved']>=10 and s['cutRate']<=70 and s['meanR']>0
    return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 50),s['meanR'],-s['cutRate'],s['resolved'])
v.rank=flexible_rank

if __name__=='__main__':v.main()
