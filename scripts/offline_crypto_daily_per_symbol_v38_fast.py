#!/usr/bin/env python3
import scripts.offline_crypto_daily_per_symbol_v38 as m

m.OUT='data/offline_crypto_daily_per_symbol_v38_fast.json'
# Focused high-precision neighborhood: RR1 first, plus a small RR2 confirmation set.
fast=[]
for rr in (1.0,2.0):
  rfs=(.75,1.0,1.5) if rr==1.0 else (1.0,1.5)
  for rf in rfs:
    for sw in (3,5):
      hold=6 if rr==1.0 else 10
      for ca,cr,cm in ((0,0,'NONE'),(1,.50,'R'),(1,.25,'R'),(1,0,'R'),(1,-.20,'EMA'),(2,.25,'R'),(2,0,'R'),(2,-.25,'EMA')):
        fast.append((rr,rf,sw,hold,ca,cr,cm))
m.CFGS=fast

if __name__=='__main__':m.main()
