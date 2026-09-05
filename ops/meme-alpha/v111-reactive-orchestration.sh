#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SERVICE=meme-alpha-paper.service
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v111-$STAMP

rollback(){
  rc=$?
  echo "ROLLBACK rc=$rc"
  if [ -d "$BACKUP" ]; then
    cp -f "$BACKUP/position.js" "$APP/src/position.js" 2>/dev/null || true
    cp -f "$BACKUP/run-paper.sh" "$APP/run-paper.sh" 2>/dev/null || true
    cp -f "$BACKUP/package.json" "$APP/package.json" 2>/dev/null || true
    chown meme-alpha:meme-alpha "$APP/src/position.js" "$APP/run-paper.sh" "$APP/package.json" 2>/dev/null || true
    chmod +x "$APP/run-paper.sh" 2>/dev/null || true
  fi
  systemctl restart "$SERVICE" || true
  exit "$rc"
}
trap rollback ERR

cd "$APP"
node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

mkdir -p "$BACKUP"
cp -a src/position.js "$BACKUP/position.js"
cp -a run-paper.sh "$BACKUP/run-paper.sh"
cp -a package.json "$BACKUP/package.json"

systemctl stop "$SERVICE"

python3 - <<'PY'
from pathlib import Path
p=Path('/opt/meme-alpha/app/src/position.js')
s=p.read_text()
if 'v1.1.1 REACTIVE ORCHESTRATED JUPITER' in s:
    print('POSITION_ALREADY_PATCHED')
    raise SystemExit(0)

# Banner.
s=s.replace('=== PAPER POSITION ENGINE v1.1 HARDENED JUPITER ===','=== PAPER POSITION ENGINE v1.1.1 REACTIVE ORCHESTRATED JUPITER ===',1)

# Add exit-quote fail-safe wrapper after closeFraction().
anchor='''  });\n}\n\nconsole.log(\n  "=== PAPER POSITION ENGINE v1.1.1 REACTIVE ORCHESTRATED JUPITER ==="\n);'''
if anchor not in s:
    raise SystemExit('SAFE_CLOSE_ANCHOR_NOT_FOUND')
wrapper='''  });\n}\n\nasync function safeCloseFraction(pos, fraction, reason, market, solUsd) {\n  try {\n    await closeFraction(pos, fraction, reason, market, solUsd);\n    return true;\n  } catch (e) {\n    recordTrade({\n      type: "PAPER_EXIT_QUOTE_FAIL",\n      positionId: pos.id || null,\n      symbol: pos.symbol,\n      mint: pos.mint,\n      reason,\n      error: e?.message || String(e)\n    });\n    console.log(`EXIT_QUOTE_FAIL ${pos.symbol} | ${reason} | ${e?.message || e}`);\n    return false;\n  }\n}\n\nconsole.log(\n  "=== PAPER POSITION ENGINE v1.1.1 REACTIVE ORCHESTRATED JUPITER ==="\n);'''
s=s.replace(anchor,wrapper,1)

# Insert reaction state immediately after MAE update.
anchor='''  pos.maePct =\n    Math.min(\n      n(pos.maePct),\n      returnPct\n    );\n\n  const entryVol ='''
if anchor not in s:
    raise SystemExit('REACTION_STATE_ANCHOR_NOT_FOUND')
insert='''  pos.maePct =\n    Math.min(\n      n(pos.maePct),\n      returnPct\n    );\n\n  const previousReturnPct =\n    Number.isFinite(Number(pos.lastReturnPct))\n      ? Number(pos.lastReturnPct)\n      : returnPct;\n\n  const oneTickDropPct =\n    previousReturnPct - returnPct;\n\n  pos.peakReturnPct =\n    Math.max(\n      Number.isFinite(Number(pos.peakReturnPct))\n        ? Number(pos.peakReturnPct)\n        : returnPct,\n      returnPct\n    );\n\n  const givebackPct =\n    pos.peakReturnPct - returnPct;\n\n  const adversePulse =\n    oneTickDropPct >= 4 && returnPct < 0;\n\n  pos.fastAdverseCount =\n    adversePulse\n      ? Math.min(3, n(pos.fastAdverseCount) + 1)\n      : Math.max(0, n(pos.fastAdverseCount) - 1);\n\n  pos.lastReturnPct = returnPct;\n\n  const latestNetBuyers =\n    n(latestObs(token)?.netBuyers5m);\n\n  const liquidityCollapse =\n    n(pos.entryLiquidityUsd) > 0 &&\n    n(market.liquidityUsd) < n(pos.entryLiquidityUsd) * 0.55 &&\n    returnPct < -3;\n\n  const fastShock =\n    (oneTickDropPct >= 10 && returnPct < -2) ||\n    (pos.fastAdverseCount >= 2 && oneTickDropPct >= 4 && returnPct <= -6);\n\n  const profitGiveback =\n    !pos.profitProtectDone &&\n    pos.peakReturnPct >= 12 &&\n    givebackPct >= 8 &&\n    returnPct > 0 &&\n    latestNetBuyers <= 0;\n\n  const entryVol ='''
s=s.replace(anchor,insert,1)

# Replace management close calls only, preserving wrapper's internal closeFraction call.
manage_start=s.index('/*\n * 1. MANAGE EXISTING POSITIONS')
entry_start=s.index('/*\n * 3. OPEN NEW PAPER PROBE')
if manage_start<0 or entry_start<0 or entry_start<=manage_start:
    raise SystemExit('MANAGE_ENTRY_BOUNDARY_NOT_FOUND')
manage=s[manage_start:entry_start]
manage=manage.replace('await closeFraction(', 'await safeCloseFraction(')

# Add fast protection in safe order after emergency block.
emergency_tail='''    continue;\n  }\n\n  if (thesisBroken) {'''
if emergency_tail not in manage:
    raise SystemExit('EMERGENCY_TAIL_NOT_FOUND')
fast_block='''    continue;\n  }\n\n  if (liquidityCollapse) {\n    await safeCloseFraction(\n      pos,\n      1,\n      "FAST_LIQUIDITY_COLLAPSE",\n      market,\n      solUsd\n    );\n    continue;\n  }\n\n  if (fastShock) {\n    const shockFraction =\n      returnPct <= -12 ? 1 : 0.50;\n    await safeCloseFraction(\n      pos,\n      shockFraction,\n      "FAST_ADVERSE_SHOCK",\n      market,\n      solUsd\n    );\n    continue;\n  }\n\n  if (thesisBroken) {'''
manage=manage.replace(emergency_tail,fast_block,1)

# Profit giveback protection before TP blocks.
thesis_tail='''    continue;\n  }\n\n  if (\n    !pos.tp1Done &&'''
if thesis_tail not in manage:
    raise SystemExit('THESIS_TAIL_NOT_FOUND')
profit_block='''    continue;\n  }\n\n  if (profitGiveback) {\n    const protectedOk = await safeCloseFraction(\n      pos,\n      0.35,\n      "FAST_PROFIT_GIVEBACK",\n      market,\n      solUsd\n    );\n    if (protectedOk) pos.profitProtectDone = true;\n  }\n\n  if (\n    !pos.tp1Done &&'''
manage=manage.replace(thesis_tail,profit_block,1)

# Only mark TP flags when Jupiter exit quote succeeded.
old='''    await safeCloseFraction(\n      pos,\n      0.20,\n      "PARTIAL_TP1",\n      market,\n      solUsd\n    );\n\n    pos.tp1Done = true;'''
new='''    const tp1Ok = await safeCloseFraction(\n      pos,\n      0.20,\n      "PARTIAL_TP1",\n      market,\n      solUsd\n    );\n\n    if (tp1Ok) pos.tp1Done = true;'''
if old not in manage: raise SystemExit('TP1_TARGET_NOT_FOUND')
manage=manage.replace(old,new,1)
old='''    await safeCloseFraction(\n      pos,\n      0.25,\n      "PARTIAL_TP2",\n      market,\n      solUsd\n    );\n\n    pos.tp2Done = true;'''
new='''    const tp2Ok = await safeCloseFraction(\n      pos,\n      0.25,\n      "PARTIAL_TP2",\n      market,\n      solUsd\n    );\n\n    if (tp2Ok) pos.tp2Done = true;'''
if old not in manage: raise SystemExit('TP2_TARGET_NOT_FOUND')
manage=manage.replace(old,new,1)
s=s[:manage_start]+manage+s[entry_start:]

# Recompute fresh risk AFTER current positions/equity are marked, before entry.
entry_start=s.index('/*\n * 3. OPEN NEW PAPER PROBE')
pre=s[:entry_start]
tail=s[entry_start:]
prerisk='''const preRiskTmp = `${PAPER}.tmp-prerisk-${process.pid}`;\nfs.writeFileSync(preRiskTmp, JSON.stringify(paper, null, 2));\nfs.renameSync(preRiskTmp, PAPER);\n\nconst manageOnly = process.env.MEME_ALPHA_MANAGE_ONLY === "1";\nif (manageOnly) {\n  console.log("PHASE=FAST_MANAGE_ONLY");\n  console.log(`FAST_EQUITY=${paper.equitySol.toFixed(6)} SOL`);\n  console.log(`FAST_OPEN_POSITIONS=${paper.openPositions.length}`);\n  console.log("FAST_MANAGE_STATUS=PASS");\n  process.exit(0);\n}\n\nawait import(`./risk.js?refresh=${Date.now()}`);\nconst entryRisk = JSON.parse(fs.readFileSync(RISK, "utf8"));\nconsole.log("ORCHESTRATION=MARK_THEN_RISK_THEN_ENTRY");\n\n'''
s=pre+prerisk+tail

# Ensure entry reads the just-refreshed risk object rather than preloaded risk.
entry_start=s.index('/*\n * 3. OPEN NEW PAPER PROBE')
pre=s[:entry_start]
tail=s[entry_start:]
tail=tail.replace('risk.timestamp', 'entryRisk.timestamp')
tail=tail.replace('(risk.candidates || [])', '(entryRisk.candidates || [])')
tail=tail.replace('risk.entryAllowed', 'entryRisk.entryAllowed')
s=pre+tail

# Exact-size Jupiter entry impact hard gate.
anchor='''        const buyQuote =\n          await jupiterExactIn(\n            WSOL,\n            t.mint,\n            inputLamports\n          );\n\n        const tokenQty ='''
if anchor not in s:
    raise SystemExit('BUY_QUOTE_ANCHOR_NOT_FOUND')
impact='''        const buyQuote =\n          await jupiterExactIn(\n            WSOL,\n            t.mint,\n            inputLamports\n          );\n\n        const exactEntryImpactPct =\n          Number(buyQuote.priceImpactPct);\n\n        if (!Number.isFinite(exactEntryImpactPct)) {\n          throw new Error("JUPITER_BUY_IMPACT_UNKNOWN");\n        }\n\n        if (Math.max(0, exactEntryImpactPct) > n(cfg.maxPriceImpactPct, 2)) {\n          throw new Error(`JUPITER_BUY_IMPACT_TOO_HIGH_${exactEntryImpactPct}`);\n        }\n\n        const tokenQty ='''
s=s.replace(anchor,impact,1)

# Initialize reaction fields on new positions.
anchor='''          tp1Done: false,\n          tp2Done: false,\n\n          status:'''
if anchor not in s:
    raise SystemExit('REACTION_FIELDS_ANCHOR_NOT_FOUND')
fields='''          tp1Done: false,\n          tp2Done: false,\n          profitProtectDone: false,\n          peakReturnPct: 0,\n          lastReturnPct: 0,\n          fastAdverseCount: 0,\n\n          status:'''
s=s.replace(anchor,fields,1)

p.write_text(s)
print('POSITION_V111_PATCHED')
PY

# Faster market reaction without hammering discovery/Jupiter: full discovery cycle stays separated;
# position-only mark/exit checks run every 10 seconds between full cycles.
cat > run-paper.sh <<'SH'
#!/bin/bash
set -u
cd /opt/meme-alpha/app || exit 1
FAST_INTERVAL_SEC=10
FAST_RUNS_BETWEEN_FULL=3
while true; do
  echo
  echo "=========================================="
  echo "MEME ALPHA FULL CYCLE $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "=========================================="
  /usr/bin/npm run cycle5
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "FULL_CYCLE_FAILED rc=$rc"
  else
    echo "FULL_CYCLE_COMPLETE"
  fi

  i=1
  while [ "$i" -le "$FAST_RUNS_BETWEEN_FULL" ]; do
    sleep "$FAST_INTERVAL_SEC"
    echo "FAST_POSITION_TICK=$i $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    MEME_ALPHA_MANAGE_ONLY=1 /usr/bin/node src/position.js || echo "FAST_POSITION_TICK_FAILED=$i"
    i=$((i+1))
  done
done
SH

chown meme-alpha:meme-alpha src/position.js run-paper.sh package.json
chmod +x run-paper.sh
node --check src/position.js

echo '=== STATIC ASSERTS ==='
grep -nE 'v1.1.1 REACTIVE|FAST_MANAGE_ONLY|MARK_THEN_RISK_THEN_ENTRY|FAST_LIQUIDITY_COLLAPSE|FAST_ADVERSE_SHOCK|FAST_PROFIT_GIVEBACK|PAPER_EXIT_QUOTE_FAIL|JUPITER_BUY_IMPACT_TOO_HIGH' src/position.js
grep -nE 'FAST_INTERVAL_SEC=10|FAST_RUNS_BETWEEN_FULL=3|MEME_ALPHA_MANAGE_ONLY=1' run-paper.sh

# Manage-only must not create a new entry. Capture trade count before/after.
BEFORE=$(node -e "const fs=require('fs');const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json'));console.log((s.trades||[]).length)")
MEME_ALPHA_MANAGE_ONLY=1 node src/position.js
AFTER=$(node -e "const fs=require('fs');const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json'));console.log((s.trades||[]).length)")
# Trade count may increase only if a genuine exit fires while managing; never a BUY.
RECENT_BUY=$(node - <<'NODE'
const fs=require('fs');const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
const a=(s.trades||[]).slice(-5).filter(x=>x.type==='PAPER_BUY_PROBE' && Date.now()-new Date(x.timestamp).getTime()<5000);
console.log(a.length);
NODE
)
if [ "$RECENT_BUY" != "0" ]; then echo 'MANAGE_ONLY_OPENED_BUY'; exit 1; fi
echo "MANAGE_ONLY_ASSERT_PASS before=$BEFORE after=$AFTER"

systemctl start "$SERVICE"
sleep 45

echo '=== SERVICE ==='
systemctl --no-pager is-active "$SERVICE"
systemctl --no-pager is-enabled "$SERVICE"

echo '=== REACTIVE LOG ASSERT ==='
tail -180 /var/log/meme-alpha/paper.log | grep -E 'v1.1.1 REACTIVE|ORCHESTRATION=MARK_THEN_RISK_THEN_ENTRY|FAST_POSITION_TICK|PHASE=FAST_MANAGE_ONLY|RISK_STATE_FRESH|SOURCE_HEALTH_ENTRY_GATE|POSITION_ENGINE_STATUS|FULL_CYCLE_COMPLETE|CYCLE_COMPLETE' || true

node - <<'NODE'
import fs from 'node:fs';
const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
if(cfg.mode!=='PAPER') throw new Error('MODE_CHANGED');
const src=fs.readFileSync('/opt/meme-alpha/app/src/position.js','utf8');
const loop=fs.readFileSync('/opt/meme-alpha/app/run-paper.sh','utf8');
for(const x of ['v1.1.1 REACTIVE ORCHESTRATED JUPITER','MARK_THEN_RISK_THEN_ENTRY','FAST_LIQUIDITY_COLLAPSE','FAST_ADVERSE_SHOCK','PAPER_EXIT_QUOTE_FAIL']) if(!src.includes(x)) throw new Error('MISSING_'+x);
if(!loop.includes('FAST_INTERVAL_SEC=10')) throw new Error('FAST_LOOP_MISSING');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
console.log('REACTION_CADENCE_TARGET=10s');
console.log('V111_INVARIANT_PASS');
NODE

free -h
uptime
echo "V111_DEPLOY_COMPLETE"
echo "BACKUP=$BACKUP"
trap - ERR
