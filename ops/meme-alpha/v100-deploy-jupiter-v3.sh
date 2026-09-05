#!/usr/bin/env bash
set -euo pipefail
cd /opt/actions-runner/actions-runner/_work/trading-api/trading-api
python3 - <<'PY'
from pathlib import Path
src=Path('ops/meme-alpha/v100-deploy-jupiter.sh').read_text()
src=src.replace("""echo '=== JUPITER BUY/SELL QUOTE PRETEST ==='\nnode - <<'NODE'\nconst fs=require('fs');""","""echo '=== JUPITER BUY/SELL QUOTE PRETEST ==='\nnode --input-type=module - <<'NODE'\nimport fs from 'node:fs';""",1)
old="""const st=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));\nconst pos=(st.openPositions||[])[0];\nif(!pos?.mint) throw new Error('NO_OPEN_POSITION_FOR_QUOTE_TEST');"""
new="""const st=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));\nconst scan=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-latest.json','utf8'));\nconst open=(st.openPositions||[])[0];\nconst cand=(scan.candidates||[]).find(x=>x?.mint && x.sellRoute===true) || (scan.candidates||[]).find(x=>x?.mint);\nconst pos=open || (cand ? {mint:cand.mint, qty:1} : null);\nif(!pos?.mint) throw new Error('NO_MINT_FOR_QUOTE_TEST');"""
if old not in src:
    raise SystemExit('PRETEST_MINT_SELECTION_TARGET_NOT_FOUND')
src=src.replace(old,new,1)
# When no open position exists, use a small raw sell size based on decimals instead of qty=1% semantics.
old2="""const qtyRaw=BigInt(Math.max(1,Math.floor(Number(pos.qty||0)*10**d*0.01)));"""
new2="""const qtyRaw=(open && Number(open.qty)>0)\n  ? BigInt(Math.max(1,Math.floor(Number(open.qty)*10**d*0.01)))\n  : BigInt(Math.max(1,Math.floor(0.01*10**d)));"""
if old2 not in src:
    raise SystemExit('PRETEST_QTY_TARGET_NOT_FOUND')
src=src.replace(old2,new2,1)
out=Path('/tmp/v100-deploy-jupiter-fixed-v3.sh')
out.write_text(src)
out.chmod(0o755)
print('PRETEST_V3_READY')
PY
nice -n 15 bash /tmp/v100-deploy-jupiter-fixed-v3.sh
