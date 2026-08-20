#!/usr/bin/env bash
set -euo pipefail
: "${TWELVEDATA_API_KEY:?TWELVEDATA_API_KEY missing}"
out=docs/ai-coengineer/V78_US30_PROVIDER_DEBUG.txt
mkdir -p docs/ai-coengineer /tmp/v78-us30
fetch_td(){
  local name="$1" endpoint="$2"; shift 2
  local code
  code=$(curl -sS -o "/tmp/v78-us30/${name}.json" -w '%{http_code}' --get "https://api.twelvedata.com/${endpoint}" "$@" --data-urlencode "apikey=${TWELVEDATA_API_KEY}" || true)
  printf '%s' "$code" > "/tmp/v78-us30/${name}.status"
}
fetch_td quote_DJI quote --data-urlencode 'symbol=DJI' --data-urlencode 'type=Index'
fetch_td daily_DJI time_series --data-urlencode 'symbol=DJI' --data-urlencode 'type=Index' --data-urlencode 'interval=1day' --data-urlencode 'outputsize=2' --data-urlencode 'order=DESC' --data-urlencode 'timezone=UTC'
fetch_td search_Dow symbol_search --data-urlencode 'symbol=Dow Jones Industrial Average' --data-urlencode 'outputsize=20'
fetch_td search_DJI symbol_search --data-urlencode 'symbol=DJI' --data-urlencode 'outputsize=20'
python3 - <<'PY' > "$out"
import json, pathlib
base=pathlib.Path('/tmp/v78-us30')
print('V78 US30 PROVIDER DIAGNOSTIC — SANITIZED')
for n in ['quote_DJI','daily_DJI','search_Dow','search_DJI']:
    status=(base/f'{n}.status').read_text().strip()
    raw=(base/f'{n}.json').read_text(errors='replace')
    try:
        obj=json.loads(raw)
        # emit response only; request API key is never printed
        body=json.dumps(obj,ensure_ascii=False,separators=(',',':'))
    except Exception:
        body=raw[:4000]
    print(f'=== {n} HTTP={status} ===')
    print(body)
PY
git config user.name 'V78 Provider Inspector'
git config user.email 'actions@users.noreply.github.com'
git add "$out"
git commit -m 'Record sanitized US30 Twelve Data provider evidence'
git push origin HEAD:main
