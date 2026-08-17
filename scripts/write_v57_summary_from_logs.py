#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
RID='32027306236'
p=subprocess.run(['gh','run','view',RID,'--repo','hanlinh227-ship-it/trading-api','--log'],capture_output=True,text=True,check=True)
seen={}
for line in p.stdout.splitlines():
    if 'FINAL ' not in line:continue
    try:d=json.loads(line.split('FINAL ',1)[1].strip())
    except:continue
    s=d.get('symbol')
    if s:seen[s]=d
passed=sorted(k for k,v in seen.items() if v.get('status')=='PASS');failed=sorted(k for k,v in seen.items() if v.get('status')!='PASS')
out={'version':'V57_COMPACT','runId':int(RID),'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'results':seen};Path('data').mkdir(exist_ok=True);json.dump(out,open('data/v57_compact_summary.json','w'),indent=2);print(json.dumps(out,indent=2))
