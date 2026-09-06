#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
EXEC_SRC=$APP/ops/meme-alpha/micro-live/micro-live-executor-v280.js
EXEC_DST=$APP/src/micro-live-executor.js
SIGNER_SRC=$APP/ops/meme-alpha/signer/ready_signer_v6.py
SIGNER_DST=/opt/meme-alpha-signer/ready_signer.py
SIGNER_UNIT=meme-alpha-signer.service
MICRO_UNIT=meme-alpha-micro-live.service
PAPER_UNIT=meme-alpha-paper.service
GATE=$APP/runtime-status/micro-live-gate.json
SIGNAL=$APP/runtime-status/signal-snapshot.json
[ "$(id -u)" -eq 0 ] || { echo ABORT_ROOT_REQUIRED; exit 1; }
cd "$APP"
echo '=== MEME ALPHA v2.8.0 OPPORTUNITY 9/10 APPLY ==='
[ -f "$EXEC_SRC" ] || { echo ABORT_EXECUTOR_V280_NOT_STAGED; exit 1; }
[ -f "$SIGNER_SRC" ] || { echo ABORT_SIGNER_V6_NOT_STAGED; exit 1; }
systemctl is-active --quiet "$PAPER_UNIT"
systemctl is-active --quiet "$SIGNER_UNIT"
systemctl is-active --quiet "$MICRO_UNIT"
[ -f /etc/meme-alpha/signer-enabled ] && grep -qx 'ARMED=YES' /etc/meme-alpha/signer-enabled || { echo ABORT_SIGNER_NOT_ARMED; exit 1; }
[ -f /etc/meme-alpha/execution-mode ] && grep -qx 'MICRO_LIVE' /etc/meme-alpha/execution-mode || { echo ABORT_NOT_MICRO_LIVE; exit 1; }

# Do not change live entry/hold semantics while a real position is open.
python3 - <<'PY'
import json,sys
p='/var/lib/meme-alpha/data/micro-live/state.json'
try:s=json.load(open(p))
except FileNotFoundError:s={}
if s.get('position'):
 print('ABORT_LIVE_POSITION_OPEN='+str(s['position'].get('symbol','UNKNOWN')))
 sys.exit(2)
print('LIVE_POSITION=NONE')
PY

node --check "$EXEC_SRC"
node "$EXEC_SRC" --self-test | tee /tmp/v280-exec.txt
grep -q 'MICRO_EXECUTOR_V280_SELF_TEST=PASS' /tmp/v280-exec.txt
rm -f /tmp/v280-exec.txt
python3 "$SIGNER_SRC" --self-test | tee /tmp/v280-signer.txt
grep -q 'READY_SIGNER_V6_SELF_TEST=PASS' /tmp/v280-signer.txt
grep -q 'ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED' /tmp/v280-signer.txt
rm -f /tmp/v280-signer.txt

grep -q "securityDecision==='PASS'" "$EXEC_SRC"
grep -q "holderClusterDecision==='PASS'" "$EXEC_SRC"
grep -q "sellRoute===true" "$EXEC_SRC"
grep -q '!c.token2022' "$EXEC_SRC"
grep -q 'chg>=0.15&&chg<=15' "$EXEC_SRC"

STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v280-$STAMP
mkdir -p "$BACKUP"
for f in scanner.js holder-cluster.js persistence.js micro-live-executor.js; do cp -a "$APP/src/$f" "$BACKUP/$f"; done
cp -a "$SIGNER_DST" "$BACKUP/ready_signer.py"
cp -a "$APP/run-paper.sh" "$BACKUP/run-paper.sh"

rollback(){
 rc=$?
 echo "V280_ROLLBACK rc=$rc" >&2
 cp -f "$BACKUP/scanner.js" "$APP/src/scanner.js" || true
 cp -f "$BACKUP/holder-cluster.js" "$APP/src/holder-cluster.js" || true
 cp -f "$BACKUP/persistence.js" "$APP/src/persistence.js" || true
 cp -f "$BACKUP/micro-live-executor.js" "$EXEC_DST" || true
 cp -f "$BACKUP/ready_signer.py" "$SIGNER_DST" || true
 cp -f "$BACKUP/run-paper.sh" "$APP/run-paper.sh" || true
 systemctl restart "$PAPER_UNIT" >/dev/null 2>&1 || true
 systemctl restart "$SIGNER_UNIT" >/dev/null 2>&1 || true
 systemctl restart "$MICRO_UNIT" >/dev/null 2>&1 || true
 exit "$rc"
}
trap rollback ERR

# 1) Verify sellability for high-signal WATCH candidates too. This removes the
# WATCH -> no sell quote -> SECURITY_REVIEW circular bottleneck without weakening
# the mandatory sell-route gate.
python3 - <<'PY'
from pathlib import Path
import re
p=Path('/opt/meme-alpha/app/src/scanner.js');s=p.read_text()
if 'OPPORTUNITY_WATCH_SELLABILITY_V280' not in s:
 pat=r'''  if \(\n    enriched\.decision ===\n      "PROBE_CANDIDATE"\n  \) \{\n    const sell ='''
 repl='''  // OPPORTUNITY_WATCH_SELLABILITY_V280: verification only; never grants BUY by itself.\n  const opportunitySellCheck =\n    enriched.decision === "PROBE_CANDIDATE" ||\n    (\n      enriched.decision === "WATCH" &&\n      (enriched.hardReject||[]).length === 0 &&\n      Number(enriched.dexLiquidityUsd||enriched.liquidityUsd||0) >= cfg.minLiquidityUsd &&\n      Number(enriched.score||0) >= 55 &&\n      (Number(enriched.netBuyers5m||0) >= 1 || Number(enriched.priceChange5m||0) >= 0.15)\n    );\n  if (opportunitySellCheck) {\n    const sell ='''
 s,n=re.subn(pat,repl,s,count=1)
 if n!=1: raise SystemExit('SCANNER_SELLABILITY_PATTERN_NOT_FOUND')
p.write_text(s)
PY
node --check src/scanner.js

# 2) Audit more verified opportunity candidates for holder concentration, retry
# transient RPC failures, and only promote WATCH after security + holder + sellability pass.
python3 - <<'PY'
from pathlib import Path
import re
p=Path('/opt/meme-alpha/app/src/holder-cluster.js');s=p.read_text()
if 'OPPORTUNITY_HOLDER_TARGETS_V280' not in s:
 old='''const targets =\n  (scan.candidates||[])\n    .filter(c =>\n      c.universeClass !== "NON_MEME" &&\n      c.securityDecision === "PASS" &&\n      Number(c.score||0) >= 70\n    )\n    .slice(0,8);'''
 new='''// OPPORTUNITY_HOLDER_TARGETS_V280: expand expensive audits only after\n// security/sellability are already proven. Hard holder blocks remain unchanged.\nconst targets =\n  (scan.candidates||[])\n    .filter(c =>\n      c.universeClass !== "NON_MEME" &&\n      c.securityDecision === "PASS" &&\n      !c.token2022 &&\n      c.sellRoute === true &&\n      (c.hardReject||[]).length === 0 &&\n      Number(c.score||0) >= 55 &&\n      (Number(c.score||0) >= 62 || Number(c.netBuyers5m||0) >= 3 || Number(c.priceChange5m||0) >= 0.30)\n    )\n    .sort((a,b)=>(Number(b.score||0)*100+Number(b.netBuyers5m||0)*6+Math.log10(Math.max(1,Number(b.liquidityUsd||0)))*20)-(Number(a.score||0)*100+Number(a.netBuyers5m||0)*6+Math.log10(Math.max(1,Number(a.liquidityUsd||0)))*20))\n    .slice(0,16);'''
 if old not in s: raise SystemExit('HOLDER_TARGET_PATTERN_NOT_FOUND')
 s=s.replace(old,new,1)
 # Retry only transient holder-RPC failures; REVIEW remains fail-closed if retries fail.
 old2='''  const r =\n    await inspect(c);'''
 new2='''  let r =\n    await inspect(c);\n  for (let retry=0; retry<2 && (r.error || r.reviewReasons.includes("HOLDER_RPC_LARGEST_ACCOUNTS_FAILED") || r.reviewReasons.includes("HOLDER_OWNER_RESOLUTION_FAILED")); retry++) {\n    await new Promise(resolve=>setTimeout(resolve,250*(retry+1)));\n    r = await inspect(c);\n  }'''
 if old2 not in s: raise SystemExit('HOLDER_INSPECT_PATTERN_NOT_FOUND')
 s=s.replace(old2,new2,1)
 old3='''  } else {\n    pass++;\n  }\n}\n\n/*\n * Candidates >=70 that should have'''
 new3='''  } else {\n    pass++;\n    // OPPORTUNITY_PROMOTION_V280: promotion is allowed only after every hard\n    // pre-entry safety gate has already passed.\n    const opportunityVerified =\n      c.universeClass === "MEME_CONFIRMED" &&\n      c.securityDecision === "PASS" &&\n      c.holderClusterAudit?.decision === "PASS" &&\n      !c.token2022 &&\n      c.sellRoute === true &&\n      (c.hardReject||[]).length === 0 &&\n      Number(c.liquidityUsd||0) >= 50000 &&\n      Number(c.score||0) >= 62 &&\n      Number(c.priceChange5m||0) >= 0.10 &&\n      Number(c.priceChange5m||0) <= 15 &&\n      Number(c.netBuyers5m||0) >= 1;\n    if (opportunityVerified && c.decision === "WATCH") {\n      c.decision = "PROBE_CANDIDATE";\n      c.reasons = uniq([...(c.reasons||[]),"OPPORTUNITY_VERIFIED_FAST_TRACK"]);\n    }\n  }\n}\n\n/*\n * Candidates >=70 that should have'''
 if old3 not in s: raise SystemExit('HOLDER_PASS_PROMOTION_PATTERN_NOT_FOUND')
 s=s.replace(old3,new3,1)
p.write_text(s)
PY
node --check src/holder-cluster.js

# 3) Let fully-safe lower-score opportunities accumulate persistence immediately.
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/meme-alpha/app/src/persistence.js');s=p.read_text()
if 'OPPORTUNITY_PERSISTENCE_V280' not in s:
 old='''    Number(c.score || 0) >=\n      70 &&'''
 new='''    // OPPORTUNITY_PERSISTENCE_V280: score is now a soft opportunity signal;\n    // all hard security/holder/sellability gates below remain mandatory.\n    Number(c.score || 0) >=\n      62 &&'''
 if old not in s: raise SystemExit('PERSIST_SCORE_PATTERN_NOT_FOUND')
 s=s.replace(old,new,1)
 old2='''  const liquidityStableLast2 = last2.length === 2 &&\n    Math.min(...liquidityLast2) >= 0.85*Math.max(...liquidityLast2);'''
 new2='''  const liquidityStableLast2 = last2.length < 2 ||\n    Math.min(...liquidityLast2) >= 0.85*Math.max(...liquidityLast2);'''
 if old2 not in s: raise SystemExit('PERSIST_LIQ_PATTERN_NOT_FOUND')
 s=s.replace(old2,new2,1)
p.write_text(s)
PY
node --check src/persistence.js

# Static invariants: opportunity is loosened only after hard safety is intact.
grep -q 'OPPORTUNITY_WATCH_SELLABILITY_V280' src/scanner.js
grep -q 'OPPORTUNITY_HOLDER_TARGETS_V280' src/holder-cluster.js
grep -q 'OPPORTUNITY_PROMOTION_V280' src/holder-cluster.js
grep -q 'OPPORTUNITY_PERSISTENCE_V280' src/persistence.js
grep -q 'HOLDER_CLUSTER_BLOCK' src/holder-cluster.js
grep -q 'TOP_HOLDERS_OVER_50' src/holder-cluster.js
grep -q 'MINT_AUTHORITY_ACTIVE' src/security.js
grep -q 'FREEZE_AUTHORITY_ACTIVE' src/security.js
grep -q 'NO_SELL_ROUTE' src/security.js

echo HARD_SECURITY_BLOCKS_PRESERVED=TRUE
echo HOLDER_CONCENTRATION_BLOCKS_PRESERVED=TRUE
echo SELLABILITY_REQUIRED=TRUE
echo TOKEN2022_LIVE_BLOCK_PRESERVED=TRUE

# Install signer/executor together after analysis logic is ready.
install -o root -g root -m 0555 "$SIGNER_SRC" "$SIGNER_DST"
install -o root -g root -m 0644 "$EXEC_SRC" "$EXEC_DST"
node --check "$EXEC_DST"

systemctl restart "$PAPER_UNIT"
sleep 3
systemctl is-active --quiet "$PAPER_UNIT"
systemctl restart "$SIGNER_UNIT"
sleep 2
systemctl is-active --quiet "$SIGNER_UNIT"
HEALTH=$(sudo -u meme-alpha python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/meme-alpha-signer/signer.sock');s.sendall(b'{"op":"health"}\n');r=json.loads(s.recv(8192));s.close();print(json.dumps(r,separators=(',',':')))
PY
)
python3 - "$HEALTH" <<'PY'
import json,sys
r=json.loads(sys.argv[1]);assert r.get('ok') is True;assert r.get('version')=='6.0';assert r.get('walletLoaded') is True;assert r.get('signingEnabled') is True;assert r.get('arbitraryRawSign') is False;assert float(r.get('maxPortfolioUtilizationPct',0))==94
print('SIGNER_V6_ACTIVE=TRUE');print('SIGNER_ARMED=TRUE');print('ARBITRARY_RAW_SIGN=FALSE')
PY
systemctl restart "$MICRO_UNIT"
sleep 4
systemctl is-active --quiet "$MICRO_UNIT"
echo MICRO_EXECUTOR_V280_ACTIVE=TRUE

# Wait for at least one post-restart signal snapshot.
START=$(date +%s)
for _ in $(seq 1 18); do
 sleep 5
 if [ -f "$SIGNAL" ]; then
   TS=$(stat -c %Y "$SIGNAL" 2>/dev/null || echo 0)
   [ "$TS" -ge "$START" ] && break
 fi
done

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const r=p=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}};
const s=r('/opt/meme-alpha/app/runtime-status/signal-snapshot.json'),g=r('/opt/meme-alpha/app/runtime-status/micro-live-gate.json'),cs=s.candidates||[];
const routed=cs.filter(c=>c.universeClass==='MEME_CONFIRMED'&&c.sellRoute===true&&Number(c.score||0)>=55);
const hardSafe=cs.filter(c=>c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&!c.token2022&&c.sellRoute===true&&(c.hardReject||[]).length===0&&Number(c.liquidityUsd||0)>=50000&&Math.abs(Number(c.sellPriceImpactPct??99))<=1.25);
const entry=hardSafe.filter(c=>{const score=Number(c.score||0),liq=Number(c.liquidityUsd||0),imp=Math.abs(Number(c.sellPriceImpactPct??99)),chg=Number(c.priceChange5m),net=Number(c.netBuyers5m),avg=Number(c.avgNetBuyersLast2??net),slope=Number(c.scoreSlopeLast2??0),con=Number(c.consecutiveEligible||0),stable=c.liquidityStableLast2!==false;const lane=score>=72||(score>=66&&liq>=500000&&net>=2&&imp<=.8)||(score>=62&&liq>=100000&&net>=8&&avg>=5&&chg>=.5&&imp<=.8);return c.decision==='PROBE_CANDIDATE'&&con>=1&&chg>=.15&&chg<=15&&net>=2&&avg>=1.5&&slope>=-4&&stable&&lane});
console.log(`SIGNAL_TS=${s.timestamp||'-'}`);console.log(`GATE_ALLOWED=${g.allowed===true} GATE_REASONS=${(g.reasons||[]).join(',')||'NONE'} EXEC=${g.executionMode||'-'}`);console.log(`MEME=${cs.filter(c=>c.universeClass==='MEME_CONFIRMED').length} SELL_ROUTE_VERIFIED_SCORE55=${routed.length} HARD_SAFE=${hardSafe.length} V280_ENTRY_READY=${entry.length}`);
for(const c of entry.slice(0,6))console.log(`READY ${c.symbol} score=${c.score} chg5m=${Number(c.priceChange5m).toFixed(2)} buyers=${c.netBuyers5m} liq=${Math.round(Number(c.liquidityUsd||0))} elig=${c.consecutiveEligible}`);
NODE

echo OPPORTUNITY_TARGET=9_10
echo DYNAMIC_ENTRY_SCORE_LANES=62_66_72
echo ENTRY_MOMENTUM_FLOOR_5M_PCT=0.15
echo ENTRY_NET_BUYERS_MIN=2
echo FIRST_SAFE_OBSERVATION_CAN_PROBE=TRUE
echo CAPITAL_STAGES=15_35_65_94
echo MAX_PORTFOLIO_UTILIZATION_PCT=94
echo ABSOLUTE_RESERVE_SOL=0.010
echo V280_OPPORTUNITY_9_10_APPLY_PASS
echo "BACKUP=$BACKUP"
trap - ERR
