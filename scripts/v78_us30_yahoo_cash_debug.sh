#!/usr/bin/env bash
set -euo pipefail
out=docs/ai-coengineer/V78_US30_YAHOO_DEBUG.txt
mkdir -p /tmp/v78-us30 docs/ai-coengineer
code=$(curl -sS -A 'Mozilla/5.0' -o /tmp/v78-us30/yahoo.json -w '%{http_code}' 'https://query1.finance.yahoo.com/v8/finance/chart/%5EDJI?interval=1m&range=1d' || true)
python3 - <<'PY' > "$out"
import json
from pathlib import Path
raw=Path('/tmp/v78-us30/yahoo.json').read_text(errors='replace')
print('US30 YAHOO CASH INDEX DIAGNOSTIC')
try:
    j=json.loads(raw)
    r=(j.get('chart',{}).get('result') or [None])[0]
    m=(r or {}).get('meta',{})
    ts=(r or {}).get('timestamp') or []
    q=((r or {}).get('indicators',{}).get('quote') or [{}])[0]
    closes=q.get('close') or []
    pairs=[(t,c) for t,c in zip(ts,closes) if c is not None]
    print('symbol='+str(m.get('symbol')))
    print('instrumentType='+str(m.get('instrumentType')))
    print('exchangeName='+str(m.get('exchangeName')))
    print('regularMarketPrice='+str(m.get('regularMarketPrice')))
    print('regularMarketTime='+str(m.get('regularMarketTime')))
    if pairs: print('lastBarTimestamp='+str(pairs[-1][0])+' lastBarClose='+str(pairs[-1][1]))
    print('chartError='+str(j.get('chart',{}).get('error')))
except Exception as e:
    print('parse_error='+repr(e)); print(raw[:1000])
PY
printf 'HTTP=%s\n' "$code" >> "$out"
git config user.name 'V78 Provider Inspector'
git config user.email 'actions@users.noreply.github.com'
git add "$out"
git commit -m 'Record US30 Yahoo cash-index fallback evidence'
git push origin HEAD:main
