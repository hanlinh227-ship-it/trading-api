#!/usr/bin/env bash
set -euo pipefail
RID="${RUN_ID:?RUN_ID required}"
gh run view "$RID" --repo hanlinh227-ship-it/trading-api --log 2>/dev/null \
| python -c 'import sys,re,json
seen={}
for line in sys.stdin:
    if " FINAL {" not in line: continue
    s=line.split(" FINAL ",1)[1].strip()
    try:
        d=json.loads(s)
    except Exception:
        continue
    key=d.get("symbol") or d.get("pair")
    if key: seen[key]={"status":d.get("status"),"frozen":d.get("frozen")}
print(json.dumps(seen,sort_keys=True))
print("PASS", " ".join(sorted(k for k,v in seen.items() if v.get("status")=="PASS")))
print("FAIL", " ".join(sorted(k for k,v in seen.items() if v.get("status")!="PASS")))'
