#!/usr/bin/env python3
import json
import scripts.free_data_precision_evolver_v1 as m

def main():
    print(json.dumps({'version':'FREE_DATA_PRECISION_EVOLVER_V1_FAST','hiddenHoldout':'2026-08-01..2026-08-14 NOT EVALUATED','providerCreditsUsed':0}))
    fxdata={};fxerr={}
    for s in m.FX:
        try:
            fxdata[s]=m.indicators(m.fetch_fx(s));print('FX_FETCH',s,len(fxdata[s]))
        except Exception as e:
            fxerr[s]=str(e);print('FX_FAIL',s,str(e)[:100])
    m.add_context(fxdata,'FX')
    crdata={};crsrc={};crerr={}
    for s in m.CRYPTO:
        try:
            r,src=m.fetch_crypto(s);crdata[s]=m.indicators(r);crsrc[s]=src;print('CR_FETCH',s,src,len(r))
        except Exception as e:
            crerr[s]=str(e);print('CR_FAIL',s,str(e)[:100])
    m.add_context(crdata,'CRYPTO')
    print('COVERAGE',json.dumps({'fx':{'requested':len(m.FX),'loaded':len(fxdata),'failed':fxerr},'crypto':{'requested':len(m.CRYPTO),'loaded':len(crdata),'failed':crerr,'sources':crsrc}}))
    fxbest,fxtop,fxn=m.evolve(fxdata,'FX',750)
    crbest,crtop,crn=m.evolve(crdata,'CRYPTO',750)
    def pack(x):
        if not x:return None
        obj,p,ev=x
        return {'objective':obj,'params':p,'folds':{k:m.compact(v) for k,v in ev.items()},'qualified':bool(obj[0])}
    out={'version':'FREE_DATA_PRECISION_EVOLVER_V1_FAST','providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,
         'coverage':{'fxLoaded':len(fxdata),'fxRequested':len(m.FX),'cryptoLoaded':len(crdata),'cryptoRequested':len(m.CRYPTO)},
         'forex':pack(fxbest),'crypto':pack(crbest),'bothQualifiedForLock':bool(fxbest and crbest and fxbest[0][0] and crbest[0][0]),
         'iterations':{'forex':fxn,'crypto':crn}}
    print('FINAL_CANDIDATE',json.dumps(out,indent=2))
if __name__=='__main__':main()
