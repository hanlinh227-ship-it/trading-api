#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo '=== MEME ALPHA v2.15 HOLDER FAST-FAIL STAGE ==='
SRC="$APP/src/holder-cluster.js"
DST="$APP/ops/meme-alpha/holder-cluster-v215.js"
ROOT_APPLY_REPO="$ROOT/ops/meme-alpha/v215-root-apply-holder-fastfail.sh"
ROOT_APPLY_DST="$APP/ops/meme-alpha/v215-root-apply-holder-fastfail.sh"
[ -f "$SRC" ] || { echo ABORT_HOLDER_RUNTIME_MISSING; exit 1; }
[ -f "$ROOT_APPLY_REPO" ] || { echo ABORT_ROOT_APPLY_REPO_MISSING; exit 1; }
cp "$SRC" "$DST"
python3 - "$DST" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
if 'HOLDER_FAST_FAIL_V215' in s:
 print('ALREADY_PATCHED_V215=TRUE');sys.exit(0)
s=s.replace('      12000\n    );','      2500\n    );',1)
pat=r'''async function rpc\(method, params\) \{.*?\n\}\n\nasync function largestAccounts'''
new='''async function rpc(method, params) {
  const attempts = UNIQUE_RPCS.map(async endpoint => {
    try {
      return await rpcOne(endpoint, method, params);
    } catch (e) {
      throw new Error(`${endpoint}:${String(e?.message||e).slice(0,120)}`);
    }
  });
  try {
    return await Promise.any(attempts);
  } catch (e) {
    const errs=(e?.errors||[]).map(x=>String(x?.message||x).slice(0,140));
    throw new Error(`ALL_RPC_FAILED | ${errs.join(' | ')}`);
  }
}

async function largestAccounts'''
s,nsub=re.subn(pat,new,s,count=1,flags=re.S)
if nsub!=1:raise SystemExit('RPC_FUNCTION_PATTERN_NOT_FOUND')
needle='''let pass=0;
let review=0;
let block=0;
let failed=0;
'''
insert='''// HOLDER_FAST_FAIL_V215
const HOLDER_AUDIT_CONCURRENCY=4;
async function mapLimit(items, limit, fn) {
  let cursor=0;
  const workers=Array.from({length:Math.min(limit,items.length)},async()=>{
    while(true){
      const i=cursor++;
      if(i>=items.length)return;
      await fn(items[i],i);
    }
  });
  await Promise.all(workers);
}
let pass=0;
let review=0;
let block=0;
let failed=0;
'''
if needle not in s:raise SystemExit('COUNTER_PATTERN_NOT_FOUND')
s=s.replace(needle,insert,1)
marker='for (const c of targets) {'
pos=s.find(marker,s.find('HOLDER_AUDIT_CONCURRENCY'))
if pos<0:raise SystemExit('TARGET_LOOP_NOT_FOUND')
s=s[:pos]+'await mapLimit(targets,HOLDER_AUDIT_CONCURRENCY,async (c) => {'+s[pos+len(marker):]
end_marker='''}

/*
 * Candidates >=70 that should have'''
end_pos=s.find(end_marker,pos)
if end_pos<0:raise SystemExit('TARGET_LOOP_END_NOT_FOUND')
s=s[:end_pos]+'});\n\n/*\n * Candidates >=70 that should have'+s[end_pos+len(end_marker):]
s=re.sub(r'for \(let retry=0; retry<2 && \(r\.error \|\| r\.reviewReasons\.includes\("HOLDER_RPC_LARGEST_ACCOUNTS_FAILED"\) \|\| r\.reviewReasons\.includes\("HOLDER_OWNER_RESOLUTION_FAILED"\)\); retry\+\+\)',
         'for (let retry=0; retry<0; retry++)',s,count=1)
s=s.replace('.slice(0,16);','.slice(0,12);',1)
s=s.replace('version:"0.9.2"','version:"0.9.3-fast"')
p.write_text(s)
PY
node --check "$DST"
grep -q 'HOLDER_FAST_FAIL_V215' "$DST"
grep -q 'Promise.any' "$DST"
grep -q 'HOLDER_AUDIT_CONCURRENCY=4' "$DST"
grep -q '.slice(0,12)' "$DST"
install -m 0755 "$0" "$APP/ops/meme-alpha/v215-stage-holder-fastfail.sh" 2>/dev/null || true
install -m 0755 "$ROOT_APPLY_REPO" "$ROOT_APPLY_DST"
[ -x "$ROOT_APPLY_DST" ] || { echo ABORT_ROOT_APPLY_INSTALL_FAILED; exit 1; }

echo HOLDER_RPC_TIMEOUT_MS=2500
echo HOLDER_RPC_ENDPOINTS_RACED=TRUE
echo HOLDER_CANDIDATE_CONCURRENCY=4
echo HOLDER_TARGETS_PER_CYCLE_MAX=12
echo HOLDER_RETRY_NEXT_CYCLE_INSTEAD_OF_BLOCKING=TRUE
echo HOLDER_FAILURE_STAYS_REVIEW_FAIL_CLOSED=TRUE
echo ROOT_APPLY_SCRIPT_INSTALLED=TRUE
echo ROOT_APPLY_PATH=$ROOT_APPLY_DST
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo V215_HOLDER_FAST_FAIL_STAGE_PASS
