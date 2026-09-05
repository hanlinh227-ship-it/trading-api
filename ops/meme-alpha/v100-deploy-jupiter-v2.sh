#!/usr/bin/env bash
set -euo pipefail
cd /opt/actions-runner/actions-runner/_work/trading-api/trading-api
python3 - <<'PY'
from pathlib import Path
src=Path('ops/meme-alpha/v100-deploy-jupiter.sh').read_text()
needle="""echo '=== JUPITER BUY/SELL QUOTE PRETEST ==='\nnode - <<'NODE'\nconst fs=require('fs');"""
repl="""echo '=== JUPITER BUY/SELL QUOTE PRETEST ==='\nnode --input-type=module - <<'NODE'\nimport fs from 'node:fs';"""
if needle not in src:
    raise SystemExit('PRETEST_MODULE_FIX_TARGET_NOT_FOUND')
src=src.replace(needle,repl,1)
out=Path('/tmp/v100-deploy-jupiter-fixed.sh')
out.write_text(src)
out.chmod(0o755)
print('PRETEST_MODULE_FIX_READY')
PY
nice -n 15 bash /tmp/v100-deploy-jupiter-fixed.sh
