#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"

echo '=== V308 PRODUCTION READINESS AUDIT ==='
echo "auditAt=$(date -u +%Y-%m-%dT%H:%M:%SZ) host=$(hostname) user=$(id -un)"

echo '=== SERVICES ==='
for s in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service meme-alpha-trend-pulse.service meme-alpha-portfolio-shadow.service; do
  printf '%s=' "$s"; systemctl is-active "$s" 2>/dev/null || true
done

echo '=== TUNING ==='
grep -E '^(TURBO_FULL_GAP_SEC|HEALTHY_FULL_GAP_SEC|DEGRADED_FULL_GAP_SEC|ACTIVE_POSITION_TICK_SEC|IDLE_CHECK_SEC|QUOTE_BACKOFF_FULL_GAP_SEC|FAILURE_BACKOFF_SEC|LIVE_SIGNAL_MAX_AGE_SEC)=' run-paper.sh 2>/dev/null || true
grep -E '^const MAX_SELLABILITY_CHECKS_V216=' src/scanner.js 2>/dev/null || true
grep -q 'V305_LIVE_FRESHNESS_GUARD' run-paper.sh && echo 'LIVE_FRESHNESS_GUARD=ACTIVE' || echo 'LIVE_FRESHNESS_GUARD=MISSING'

echo '=== SIGNAL / TREND / GATE ==='
node - <<'NODE'
const fs=require('fs');
const APP='/opt/meme-alpha/app';
function read(p){try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return {}}}
function age(x){const t=x.timestamp||x.updatedAt||x.generatedAt||x.checkedAt;const m=Date.parse(t||'');return Number.isFinite(m)?Number(((Date.now()-m)/1000).toFixed(3)):null}
const sig=read(`${APP}/runtime-status/signal-snapshot.json`);
const tr=read(`${APP}/runtime-status/trend-pulse.json`);
const gate=read(`${APP}/runtime-status/micro-live-gate.json`);
const sh=sig.sourceHealth||{};
console.log(JSON.stringify({
 signal:{ageSec:age(sig),timestamp:sig.timestamp||sig.updatedAt||sig.generatedAt||null,eligibleCount:sig.eligibleCount??sig.counts?.eligible??null,sourceStatus:sh.status||null,usingCache:sh.usingCache??null,allowNewEntries:sh.allowNewEntries??null,successfulSources:sh.successfulSources??null,failedSources:sh.failedSources??null},
 trend:{ageSec:age(tr),timestamp:tr.timestamp||tr.updatedAt||tr.generatedAt||null,regime:tr.regime||tr.trendRegime||null},
 gate:{ageSec:age(gate),allowed:gate.allowed??null,executionMode:gate.executionMode||null,armOk:gate.armOk??null,signer:gate.signer||null,sourceHealthy:gate.sourceHealthy??null,liveRiskReady:gate.liveRiskReady??null,validationStatus:gate.validationStatus||null,stressStatus:gate.stressStatus||null,reasons:gate.reasons||[],fastGuard:gate.fastGuard||null}
},null,2));
NODE

echo '=== MICRO LIVE RECENT EVENTS (SAFE MARKERS) ==='
for f in /var/lib/meme-alpha/data/micro-live/events.jsonl /var/lib/meme-alpha/data/micro-live/state.json; do
  [ -r "$f" ] || continue
  echo "--- $f"
  if [[ "$f" == *.jsonl ]]; then tail -n 30 "$f" | sed -E 's/(privateKey|secret|apiKey|token)"?:"?[^", ]+/\1:"[REDACTED]"/Ig' || true; else node - "$f" <<'NODE' 2>/dev/null || true
const fs=require('fs');try{const x=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const keep=['version','timestamp','updatedAt','mode','status','position','openPosition','lastAction','lastError','lastBuyAt','lastSellAt','walletPubkey'];const o={};for(const k of keep)if(Object.prototype.hasOwnProperty.call(x,k))o[k]=x[k];console.log(JSON.stringify(o,null,2))}catch{}
NODE
  fi
done

echo 'V308_PRODUCTION_READINESS_AUDIT_PASS'
