#!/usr/bin/env python3
import scripts.offline_crypto_v35_corrected_symbol_regime as m
m.PARAMS=[]
for mode in ('ANY','NO_BEAR_CAP','BULL_STRONG','ALIGN_EXTREME'):
 for al in (0,.6):
  for ht in (0,8):
   for dc in (1.5,99):
    for side in ('ANY','ALIGN','BUY'):
     for var in ('DRIVER','DRIVER_MICRO','HTF'):
      for fl in (.5,.8):
       for k in (3,5):
        for mic in (False,True):m.PARAMS.append((mode,al,ht,dc,side,var,fl,k,mic))
m.main()
