#!/usr/bin/env python3
import json
p=json.load(open('data/v13_saved_diagnostic.json'))
out={}
keys=['byRegime','byProfile','bySide','byScoreBucket','byRangePosition','byChase','byRegimeSide','byProfileRegime','bySweep15']
for label,s in p['samples'].items():
    out[label]={k:s[k] for k in keys}
json.dump(out,open('data/v13_compact_summary.json','w'),indent=2)
print(json.dumps(out,indent=2))
