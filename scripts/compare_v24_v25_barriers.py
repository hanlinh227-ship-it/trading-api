#!/usr/bin/env python3
import json
from collections import Counter, defaultdict

with open('data/blind_backtest_v24_validation.json') as f:
    v24=json.load(f)
with open('data/v25_development.json') as f:
    v25=json.load(f)

pairs=[('BLIND_JUN30','DEV_JUN30'),('BLIND_JUN27','DEV_JUN27')]
for a,b in pairs:
    r24={x['symbol']:x for x in v24['samples'][a]['tests']}
    r25={x['symbol']:x for x in v25['samples'][b]['tests']}
    common=sorted(set(r24)&set(r25))
    combo=Counter()
    changed=[]
    same=[]
    by_profile=defaultdict(Counter)
    for sym in common:
        x,y=r24[sym],r25[sym]
        o24=x.get('outcome',{}).get('result','?');o25=y.get('outcome',{}).get('result','?')
        k=(x.get('decision'),o24,y.get('decision'),o25)
        combo[k]+=1
        profile=(x.get('model') or {}).get('profile','unknown')
        by_profile[profile][k]+=1
        row={'symbol':sym,'v24Side':x.get('decision'),'v24':o24,'v25Side':y.get('decision'),'v25':o25,'profile':profile}
        (changed if x.get('decision')!=y.get('decision') else same).append(row)
    both_sl=[z for z in changed if z['v24']=='SL' and z['v25']=='SL']
    v24_sl_v25_tp=[z for z in changed if z['v24']=='SL' and z['v25']=='TP']
    v24_tp_v25_sl=[z for z in changed if z['v24']=='TP' and z['v25']=='SL']
    print(json.dumps({
        'pair':f'{a} vs {b}',
        'common':len(common),
        'sideChanged':len(changed),
        'sideSame':len(same),
        'changedBothSL':len(both_sl),
        'changedV24slV25tp':len(v24_sl_v25_tp),
        'changedV24tpV25sl':len(v24_tp_v25_sl),
        'changedOther':len(changed)-len(both_sl)-len(v24_sl_v25_tp)-len(v24_tp_v25_sl),
        'combos':{'|'.join(k):v for k,v in combo.items()},
        'bothSLSymbols':[z['symbol'] for z in both_sl],
        'v24SlV25TpSymbols':[z['symbol'] for z in v24_sl_v25_tp],
        'v24TpV25SlSymbols':[z['symbol'] for z in v24_tp_v25_sl],
    },indent=2))
