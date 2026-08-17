#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
RID='32026926958';remaining={'DOT','FLOKI','INJ','LDO','ONDO','POL','TAO','WLD'}
p=subprocess.run(['gh','run','view',RID,'--repo','hanlinh227-ship-it/trading-api','--log'],capture_output=True,text=True,check=True)
out={}
for line in p.stdout.splitlines():
    if 'FINAL ' not in line:continue
    try:d=json.loads(line.split('FINAL ',1)[1].strip())
    except:continue
    s=d.get('symbol')
    if s not in remaining:continue
    hist=[]
    for h in d.get('history') or []:
        if 'final' in h:hist.append({'stage':h.get('stage'),'params':h.get('params'),'development':h.get('development'),'final':h.get('final')})
    out[s]=hist
Path('data').mkdir(exist_ok=True);json.dump(out,open('data/v56_failed_stats.json','w'),indent=2);print(json.dumps(out,indent=2))
