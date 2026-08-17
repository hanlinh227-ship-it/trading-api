#!/usr/bin/env python3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import scripts.fetch_crypto_4h_snapshot_feb_jul_2026 as f

START=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp())
END=int(datetime(2026,8,9,tzinfo=timezone.utc).timestamp())-1
OUT='data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json'

# Rebind module globals used by the already-proven source fetch functions.
f.START=START
f.END=END


def main():
    results={};diag={};errors={}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures={ex.submit(f.fetch_one,s):s for s in f.SYMBOLS}
        for fut in as_completed(futures):
            s=futures[fut]
            try:
                sym,rows,src,pages=fut.result()
                if len(rows)<24:
                    raise RuntimeError(f'too few bars {len(rows)}')
                if rows[-1][0][:10]<'2026-08-07':
                    raise RuntimeError(f'stale last {rows[-1][0]}')
                results[sym]=rows
                diag[sym]={'source':src,'bars':len(rows),'first':rows[0][0],'last':rows[-1][0],'pages':pages}
                print('FINAL1_CRYPTO',sym,src,len(rows),rows[0][0],rows[-1][0],flush=True)
            except Exception as e:
                errors[s]=str(e);print('FINAL1_CRYPTO_FAIL',s,str(e),flush=True)
    if errors or set(results)!=set(f.SYMBOLS):
        raise RuntimeError('61-symbol final1 coverage failed: '+json.dumps(errors))
    doc={
        'version':'CRYPTO_4H_AUG1_8_FINAL1_V1',
        'interval':'4h',
        'requestedSymbols':f.SYMBOLS,
        'coverageCount':len(results),
        'signalHoldout':'2026-08-01..2026-08-07',
        'outcomeBufferThrough':'2026-08-08',
        'fetchedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'sources':{
            'OKX':sum(1 for s in f.SYMBOLS if diag[s]['source']=='OKX'),
            'GATE':sum(1 for s in f.SYMBOLS if diag[s]['source']=='GATE'),
            'KRAKEN':sum(1 for s in f.SYMBOLS if diag[s]['source']=='KRAKEN'),
        },
        'diagnostics':diag,
        'data':results,
    }
    Path(OUT).parent.mkdir(parents=True,exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as fh:json.dump(doc,fh,separators=(',',':'))
    print(json.dumps({'status':'OK','path':OUT,'coverage':61,'sources':doc['sources'],'signalHoldout':doc['signalHoldout']},indent=2),flush=True)

if __name__=='__main__':main()
