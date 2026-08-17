#!/usr/bin/env python3
import json
p=json.load(open('data/v13_direction_diagnostic.json'))
keys=['byProfile','byRegime','bySide','byScoreBucket']
lines=[]
for label,s in p['samples'].items():
    lines += [f'[{label}] breadth4h={s["breadth4h"]} breadth12h={s["breadth12h"]}']
    for key in keys:
        lines.append(key)
        for c,z in s[key].items():
            lines.append(f'{c}: n={z["n"]} WR={z["winRate"]} OPP={z["oppositeWinRate"]} tp/sl/unr={z["tp"]}/{z["sl"]}/{z["unr"]}')
open('data/v13_opposite_findings.txt','w').write('\n'.join(lines)+'\n')
print('\n'.join(lines))
