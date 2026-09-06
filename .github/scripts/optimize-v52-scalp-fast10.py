#!/usr/bin/env python3
import json, runpy
from copy import deepcopy
from datetime import datetime, timezone

M=runpy.run_path('.github/scripts/optimize-v52-scalp-10round.py',run_name='v52_optimizer_lib')
SYMBOLS=M['SYMBOLS']; DAYS=M['DAYS']; TRAIN_DAYS=M['TRAIN_DAYS']; VAL_DAYS=M['VAL_DAYS']
fetch=M['fetch']; mutate=M['mutate']; eval_params=M['eval_params']; score=M['score']; BASE=M['BASE']


def main():
    data={s:fetch(s) for s in SYMBOLS}
    current=deepcopy(BASE); rounds=[]; best_val=None; best_p=None; stopped=False
    for r in range(1,11):
        candidates=[deepcopy(current)]+[mutate(current,r) for _ in range(14)]
        ranked=[]
        for p in candidates:
            tr=eval_params(data,p,'train'); ranked.append((score(tr),p,tr))
        ranked.sort(key=lambda x:x[0],reverse=True)
        _,current,train=ranked[0]
        val=eval_params(data,current,'val')
        row={'round':r,'params':deepcopy(current),'train':train,'validation':val};rounds.append(row)
        print('ROUND',r,'TRAIN',json.dumps(train),'VAL',json.dumps(val),'PARAMS',json.dumps(current,separators=(',',':')),flush=True)
        if best_val is None or score(val)>score(best_val):best_val=deepcopy(val);best_p=deepcopy(current)
        if val['trades']>=25 and val['winRate']>=.80 and val['pf']>=1.20 and val['expectancy']>0 and val['maxDD']<=12:
            stopped=True; print('STOP_CRITERIA_REACHED',r,flush=True);break
    report={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'FAST_10_ROUND_WALK_FORWARD_PRECISION_SCALP','source':'BINANCE_PUBLIC_SPOT_1M_PROXY','symbols':SYMBOLS,'days':DAYS,'trainDays':TRAIN_DAYS,'validationDays':VAL_DAYS,'rounds':rounds,'bestValidation':best_val,'bestParams':best_p,'stoppedAtTarget':stopped,'stopCriteria':{'minTrades':25,'winRate':.80,'pf':1.20,'expectancyPositive':True,'maxDDPct':12},'fullFidelityMicrostructure':False}
    with open('v52-fast10-report.json','w') as f:json.dump(report,f,indent=2)
    print('FINAL_REPORT='+json.dumps(report,separators=(',',':')),flush=True)

if __name__=='__main__':main()
