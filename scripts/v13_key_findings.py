#!/usr/bin/env python3
import json
p=json.load(open('data/v13_compact_summary.json'))
labels=list(p)
a,b=labels[0],labels[1]
keys=['byRegime','byProfile','bySide','byScoreBucket','byRangePosition','byChase','byRegimeSide','byProfileRegime','bySweep15']
lines=[f'A={a}',f'B={b}']
for key in keys:
    lines.append(f'[{key}]')
    cats=sorted(set(p[a][key])|set(p[b][key]))
    for c in cats:
        x=p[a][key].get(c,{});y=p[b][key].get(c,{})
        lines.append(f'{c}: A n={x.get("n",0)} WR={x.get("winRate")} RR={x.get("avgRR")} E={x.get("expectancyR")} | B n={y.get("n",0)} WR={y.get("winRate")} RR={y.get("avgRR")} E={y.get("expectancyR")}')
open('data/v13_key_findings.txt','w').write('\n'.join(lines)+'\n')
print('\n'.join(lines))
