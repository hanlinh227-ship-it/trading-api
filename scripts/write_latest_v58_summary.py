#!/usr/bin/env python3
import json,subprocess,time
from pathlib import Path
repo='hanlinh227-ship-it/trading-api';wf='Offline Crypto V58 Online Protect 2Month'
runs=json.loads(subprocess.run(['gh','run','list','--repo',repo,'--workflow',wf,'--limit','1','--json','databaseId,status,conclusion'],capture_output=True,text=True,check=True).stdout)
if not runs:raise RuntimeError('V58 run not found')
rid=str(runs[0]['databaseId'])
for _ in range(90):
 d=json.loads(subprocess.run(['gh','run','view',rid,'--repo',repo,'--json','status,conclusion'],capture_output=True,text=True,check=True).stdout)
 if d['status']=='completed':break
 time.sleep(5)
else:raise RuntimeError('V58 still running')
p=subprocess.run(['gh','run','view',rid,'--repo',repo,'--log'],capture_output=True,text=True,check=True)
seen={}
for line in p.stdout.splitlines():
 if 'FINAL ' not in line:continue
 try:d=json.loads(line.split('FINAL ',1)[1].strip())
 except:continue
 s=d.get('symbol')
 if s:seen[s]=d
passed=sorted(k for k,v in seen.items() if v.get('status')=='PASS');failed=sorted(k for k,v in seen.items() if v.get('status')!='PASS')
out={'version':'V58_COMPACT','runId':int(rid),'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'results':seen};Path('data').mkdir(exist_ok=True);json.dump(out,open('data/v58_compact_summary.json','w'),indent=2);print(json.dumps(out,indent=2))
