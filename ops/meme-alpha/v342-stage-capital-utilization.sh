#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SRC="$APP/src/micro-live-executor.js"
STAGE="$APP/runtime-status/v342-stage"
OUT="$STAGE/micro-live-executor-v342-capital-utilization.js"
mkdir -p "$STAGE"
cp "$SRC" "$OUT"
python3 - "$OUT" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
old="""function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const quality=clamp(scoreQ*.31+netQ*.18+avgQ*.12+liqQ*.16+impactQ*.15+pulseQ*.08,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.25),.75,1.50);
  const exposure=clamp(portfolioInvested(st)/capitalBaseLamports,0,1),headroom=clamp(1-exposure*.55,.35,1);
  const basePct=3+27*Math.pow(quality,1.35),pct=clamp(basePct*growth*headroom,0,p.maxUtilizationPct);
  return{name:'AUTO',pct,quality,growth,exposure,score:opportunityScore(c)};
}"""
new="""function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const quality=clamp(scoreQ*.31+netQ*.18+avgQ*.12+liqQ*.16+impactQ*.15+pulseQ*.08,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.28),.80,2.00);
  const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1);
  // Capital-utilization-first: free capital increases conviction sizing instead of position-count/exposure suppressing it.
  const basePct=4+30*Math.pow(quality,1.25),cashBoost=1+0.35*freeRatio,pct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct);
  return{name:'AUTO_CAPITAL_FIRST',pct,quality,growth,exposure,freeRatio,cashBoost,score:opportunityScore(c)};
}"""
if old not in s: raise SystemExit('ALLOCATION_PROFILE_BASELINE_MISMATCH')
s=s.replace(old,new,1)
s=s.replace("st.version='3.36.0-autonomous'","st.version='3.42.0-capital-utilization'",1)
s=s.replace("MICRO_LIVE_EXECUTOR_V336_AUTONOMOUS_PORTFOLIO=STARTED","MICRO_LIVE_EXECUTOR_V342_CAPITAL_UTILIZATION=STARTED",1)
s=s.replace("MICRO_EXECUTOR_V336_AUTONOMOUS_SELF_TEST=PASS","MICRO_EXECUTOR_V342_CAPITAL_UTILIZATION_SELF_TEST=PASS",1)
s=s.replace("console.log('CONTINUOUS_ALLOCATION=TRUE');","console.log('CONTINUOUS_ALLOCATION=TRUE');console.log('CAPITAL_UTILIZATION_FIRST=TRUE');console.log('FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE');",1)
p.write_text(s)
PY
/usr/bin/node --check "$OUT"
TEST=$(/usr/bin/node "$OUT" --self-test)
echo "$TEST"
echo "$TEST" | grep -q 'MICRO_EXECUTOR_V342_CAPITAL_UTILIZATION_SELF_TEST=PASS'
echo "$TEST" | grep -q 'CAPITAL_UTILIZATION_FIRST=TRUE'
grep -q "st.version='3.42.0-capital-utilization'" "$OUT"
grep -q "freeRatio" "$OUT"
grep -q "cashBoost" "$OUT"
chmod 0644 "$OUT"
sha256sum "$OUT" | tee "$STAGE/executor.sha256"
cat > "$STAGE/install-v342.sh" <<'ROOT'
#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V342_INSTALL_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app
SRC="$APP/runtime-status/v342-stage/micro-live-executor-v342-capital-utilization.js"
DST="$APP/src/micro-live-executor.js"
STATE=/var/lib/meme-alpha/data/micro-live/state.json
ARM=/etc/meme-alpha/micro-live-armed
SERVICE=meme-alpha-micro-live.service
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
B="$APP/runtime-status/v342-backup-$STAMP"
mkdir -p "$B"
cp -a "$DST" "$B/micro-live-executor.js"
[ -f "$STATE" ] && cp -a "$STATE" "$B/state.json" || true
cp -a "$ARM" "$B/micro-live-armed"
BEFORE=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()))
NODE
)
rollback(){ rc=$?; if [ $rc -ne 0 ]; then echo V342_ROLLBACK_START=TRUE; cp -a "$B/micro-live-executor.js" "$DST" || true; [ -f "$B/state.json" ] && cp -a "$B/state.json" "$STATE" || true; cp -a "$B/micro-live-armed" "$ARM" || true; systemctl restart "$SERVICE" || true; echo V342_ROLLBACK_DONE=TRUE; fi; exit $rc; }
trap rollback EXIT
/usr/bin/node --check "$SRC"
/usr/bin/node "$SRC" --self-test | grep -q 'MICRO_EXECUTOR_V342_CAPITAL_UTILIZATION_SELF_TEST=PASS'
printf 'ARMED=NO\n' > "$ARM"
systemctl stop "$SERVICE"
install -o root -g root -m 0644 "$SRC" "$DST"
systemctl start "$SERVICE"
sleep 7
systemctl is-active --quiet "$SERVICE"
[ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]
AFTER=$(runuser -u meme-alpha -- /usr/bin/node - "$STATE" <<'NODE'
const fs=require('fs'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));if(s.version!=='3.42.0-capital-utilization')throw new Error('STATE_VERSION');console.log(JSON.stringify((s.positions||[]).map(x=>x.mint).sort()))
NODE
)
[ "$BEFORE" = "$AFTER" ] || { echo V342_POSITION_PRESERVATION_FAIL; exit 1; }
cp -a "$B/micro-live-armed" "$ARM"
echo PRESERVED_MINTS="$AFTER"
echo V342_CAPITAL_UTILIZATION_PRODUCTION_ACTIVE=TRUE
trap - EXIT
ROOT
chmod 0755 "$STAGE/install-v342.sh"
echo ROOT_INSTALL_COMMAND="$STAGE/install-v342.sh"
echo V342_STAGE_READY=TRUE
