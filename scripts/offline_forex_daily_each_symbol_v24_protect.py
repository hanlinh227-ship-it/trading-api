#!/usr/bin/env python3
import scripts.offline_forex_daily_each_symbol_v21_mgmtml as v

v.OUT='data/offline_forex_daily_each_symbol_v24_protect.json'
# Wider structural buffer lets H+1 management act before hard SL.
v.EXECS=[
 (1.0,1.00,12,30),(1.0,1.25,12,36),(1.0,1.50,18,36),(1.0,1.75,18,48),(1.0,2.00,24,48),
 (2.0,1.00,12,48),(2.0,1.50,18,60)
]
v.MGMT_THS=(.25,.35,.45,.55,.65,.75,.85,.92,.97)
v.MIN_AGES=(1,2,3)
v.ENTRY_THS=(.50,.54,.58,.62,.66,.70,.74)
v.ENTRY_MGS=(0,.02,.04,.08,.12)
v.FALLBACKS=(8,12,16,20)

def protective_rank(s):
    # User convention: CUT is separate from TP/SL WR. Daily coverage and full-month economics remain mandatory.
    ok=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=82 and s['meanR']>0
    return (int(ok and s['wr']>=80),s['wr']-(0 if ok else 60),s['meanR'],s['resolved'],-s['cutRate'])
v.rank=protective_rank

if __name__=='__main__':v.main()
