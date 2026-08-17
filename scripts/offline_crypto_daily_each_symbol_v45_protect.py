#!/usr/bin/env python3
import scripts.offline_crypto_daily_each_symbol_v42_mgmtml as v

v.OUT='data/offline_crypto_daily_each_symbol_v45_protect.json'
v.EXECS=[
 (1.0,1.00,5,9),(1.0,1.25,8,9),(1.0,1.50,8,12),(1.0,1.75,10,12),(1.0,2.00,12,12),
 (2.0,1.00,5,12),(2.0,1.50,8,18)
]
v.MGMT_THS=(.25,.35,.45,.55,.65,.75,.85,.92,.97)
v.MIN_AGES=(1,2,3)
v.ENTRY_THS=(.48,.52,.56,.60,.64,.68,.72)
v.ENTRY_MGS=(0,.02,.04,.08,.12)
v.FALLBACKS=(8,12,16,20)

def protective_rank(s):
    ok=s['missing']==0 and s['resolved']>=6 and s['cutRate']<=82 and s['meanR']>0
    return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
v.rank=protective_rank

if __name__=='__main__':v.main()
