#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
SERVICE=meme-alpha-paper.service
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v110-$STAMP
mkdir -p "$BACKUP"
cd "$APP"
cp -a src/risk.js src/validation.js src/position.js package.json "$BACKUP"/
cp -a "$DATA/scanner-source-health.json" "$BACKUP/" 2>/dev/null || true
rollback(){ rc=$?; echo "ROLLBACK rc=$rc"; cp -f "$BACKUP/risk.js" src/risk.js; cp -f "$BACKUP/validation.js" src/validation.js; cp -f "$BACKUP/position.js" src/position.js; cp -f "$BACKUP/package.json" package.json; systemctl start "$SERVICE" || true; exit "$rc"; }
trap rollback ERR

node - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE
systemctl stop "$SERVICE"

cat > src/risk.js <<'NODE'
import fs from "node:fs";
const CFG="/opt/meme-alpha/app/config/runtime.json";
const PAPER="/var/lib/meme-alpha/data/paper/state.json";
const SCANNER="/var/lib/meme-alpha/data/paper/scanner-latest.json";
const PERSIST="/var/lib/meme-alpha/data/paper/persistence-state.json";
const SOURCE="/var/lib/meme-alpha/data/paper/scanner-source-health.json";
const RISK="/var/lib/meme-alpha/data/paper/risk-state.json";
const cfg=JSON.parse(fs.readFileSync(CFG,"utf8"));
if(cfg.mode!=="PAPER") throw new Error("SAFETY BLOCK: NOT PAPER MODE");
const paper=JSON.parse(fs.readFileSync(PAPER,"utf8"));
const scanner=JSON.parse(fs.readFileSync(SCANNER,"utf8"));
const persistence=JSON.parse(fs.readFileSync(PERSIST,"utf8"));
let sourceHealth=null; try{sourceHealth=JSON.parse(fs.readFileSync(SOURCE,"utf8"));}catch{}
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const ageSec=v=>v?Math.max(0,(Date.now()-new Date(v).getTime())/1000):Infinity;
const equity=n(paper.equitySol,1);
const highWater=Math.max(equity,n(paper.highWaterEquitySol,equity));
const drawdownPct=highWater>0?(1-equity/highWater)*100:0;
const exposureSol=(paper.openPositions||[]).reduce((s,p)=>s+n(p.lastValueSol,p.remainingCostSol),0);
const exposurePct=equity>0?exposureSol/equity*100:0;
const openPositions=(paper.openPositions||[]).length;
const latestScanAgeSec=ageSec(scanner.timestamp);
const persistenceAgeSec=ageSec(persistence.updatedAt);
const sourceHealthAgeSec=ageSec(sourceHealth?.checkedAt);
const scannerHealthy=latestScanAgeSec<120;
const persistenceHealthy=persistenceAgeSec<120;
const discovered=n(scanner.discovered);
const discoveryHealthy=discovered>=20;
const sourceHealthHealthy=!!sourceHealth && sourceHealth.status==="HEALTHY" && sourceHealthAgeSec<180 && sourceHealth.allowNewEntries===true && sourceHealth.usingCache!==true && n(sourceHealth.successfulSources)>=2;
let riskMultiplier=1, regime="NORMAL";
if(drawdownPct>=20){riskMultiplier=0;regime="HALT";} else if(drawdownPct>=12){riskMultiplier=.25;regime="DEFENSIVE";} else if(drawdownPct>=7){riskMultiplier=.5;regime="REDUCED";} else if(drawdownPct>=3){riskMultiplier=.75;regime="CAUTIOUS";}
const maxExposurePct=n(cfg.maxPortfolioExposurePct,20), maxSinglePct=n(cfg.maxSinglePositionPct,5), maxPositions=3;
const reasons=[];
if(!scannerHealthy) reasons.push("SCANNER_STALE");
if(!persistenceHealthy) reasons.push("PERSISTENCE_STALE");
if(!discoveryHealthy) reasons.push("DISCOVERY_TOO_LOW");
if(!sourceHealth) reasons.push("SOURCE_HEALTH_MISSING");
else {
  if(sourceHealthAgeSec>=180) reasons.push("SOURCE_HEALTH_STALE");
  if(sourceHealth.status!=="HEALTHY" || sourceHealth.usingCache===true || n(sourceHealth.successfulSources)<2) reasons.push("SOURCE_HEALTH_DEGRADED");
  if(sourceHealth.allowNewEntries!==true) reasons.push("NEW_ENTRIES_DISABLED_BY_SOURCE_HEALTH");
}
if(exposurePct>=maxExposurePct) reasons.push("PORTFOLIO_EXPOSURE_LIMIT");
if(openPositions>=maxPositions) reasons.push("MAX_POSITIONS");
if(regime==="HALT") reasons.push("DRAWDOWN_HALT");
const candidates=[];
for(const t of Object.values(persistence.tokens||{})){
  if(t.persistenceDecision!=="PAPER_ENTRY_READY") continue;
  const c=(scanner.candidates||[]).find(x=>x.mint===t.mint); if(!c) continue;
  const local=[];
  if(c.decision!=="PROBE_CANDIDATE") local.push("NOT_PROBE_CANDIDATE");
  if(c.securityDecision!=="PASS") local.push("SECURITY_NOT_PASS");
  if(c.token2022) local.push("TOKEN2022_BLOCK");
  if((c.hardReject||[]).length) local.push("TOKEN_HARD_REJECT");
  if(c.sellRoute!==true) local.push("SELL_ROUTE_NOT_PROVEN");
  const liq=n(c.liquidityUsd); if(liq<n(cfg.minLiquidityUsd,25000)) local.push("LOW_LIQUIDITY");
  const impact=Number(c.sellPriceImpactPct); if(!Number.isFinite(impact)) local.push("SELL_IMPACT_UNKNOWN"); else if(impact>n(cfg.maxPriceImpactPct,2)) local.push("SELL_IMPACT_TOO_HIGH");
  const score=n(t.metrics?.avgScoreLast3); let pct=1.5; if(score>=75)pct+=1; if(score>=82)pct+=1; if(liq>=250000)pct+=.5; if(liq>=1000000)pct+=.5; pct*=riskMultiplier; pct=clamp(pct,riskMultiplier>0?.5:0,maxSinglePct); pct=Math.min(pct,Math.max(0,maxExposurePct-exposurePct));
  const allowed=reasons.length===0 && local.length===0 && pct>0;
  candidates.push({mint:t.mint,symbol:t.symbol,entryScore:score,liquidityUsd:liq,persistence:t.persistenceDecision,suggestedPositionPct:Number(pct.toFixed(3)),allowed,blockReasons:local});
}
const state={version:"1.1",timestamp:new Date().toISOString(),mode:"PAPER",equitySol:equity,highWaterEquitySol:highWater,drawdownPct:Number(drawdownPct.toFixed(3)),exposureSol:Number(exposureSol.toFixed(6)),exposurePct:Number(exposurePct.toFixed(3)),openPositions,limits:{maxPositions,maxExposurePct,maxSinglePositionPct:maxSinglePct},health:{scannerHealthy,persistenceHealthy,discoveryHealthy,sourceHealthHealthy,latestScanAgeSec:Number(latestScanAgeSec.toFixed(1)),persistenceAgeSec:Number(persistenceAgeSec.toFixed(1)),sourceHealthAgeSec:Number(sourceHealthAgeSec.toFixed(1)),discovered,successfulSources:n(sourceHealth?.successfulSources),failedSources:n(sourceHealth?.failedSources),usingCache:sourceHealth?.usingCache??null,allowNewEntries:sourceHealth?.allowNewEntries??false},riskRegime:regime,riskMultiplier,entryAllowed:reasons.length===0,globalBlockReasons:reasons,candidates};
const tmp=RISK+`.tmp-${process.pid}`; fs.writeFileSync(tmp,JSON.stringify(state,null,2)); fs.renameSync(tmp,RISK);
console.log("=== MEME ALPHA RISK v1.1 ==="); console.log(`RiskRegime=${regime}`); console.log(`RiskAgePolicy=120s SourceHealthPolicy=180s`); console.log(`SourceHealthHealthy=${sourceHealthHealthy}`); console.log(`ENTRY_ALLOWED=${state.entryAllowed}`); if(reasons.length) console.log("BLOCK="+reasons.join(",")); console.log("RISK_STATUS=PASS");
NODE

cat > src/validation.js <<'NODE'
import fs from "node:fs";
const PAPER="/var/lib/meme-alpha/data/paper/state.json", OUT="/var/lib/meme-alpha/data/paper/validation.json";
const s=JSON.parse(fs.readFileSync(PAPER,"utf8")); const trades=s.trades||[], open=s.openPositions||[];
const buys=trades.filter(x=>x.type==="PAPER_BUY_PROBE"), sells=trades.filter(x=>x.type==="PAPER_SELL");
const byId=new Map();
for(const b of buys){if(!b.positionId) continue; byId.set(b.positionId,{positionId:b.positionId,mint:b.mint,symbol:b.symbol,openedAt:b.timestamp,buyEvents:1,sellEvents:0,realizedPnlSol:0});}
for(const x of sells){if(!x.positionId) continue; const r=byId.get(x.positionId)||{positionId:x.positionId,mint:x.mint,symbol:x.symbol,buyEvents:0,sellEvents:0,realizedPnlSol:0}; r.sellEvents++; r.realizedPnlSol+=Number(x.pnlSol||0); r.lastSellAt=x.timestamp; byId.set(x.positionId,r);}
const openIds=new Set(open.map(p=>p.id).filter(Boolean)); const lifecycles=[...byId.values()].map(r=>({...r,closed:!openIds.has(r.positionId)&&r.buyEvents>0,realizedPnlSol:Number(r.realizedPnlSol.toFixed(10))}));
const completed=lifecycles.filter(x=>x.closed); const pnls=completed.map(x=>x.realizedPnlSol); const wins=pnls.filter(x=>x>0), losses=pnls.filter(x=>x<0); const sum=a=>a.reduce((x,y)=>x+y,0); const gp=sum(wins), gl=Math.abs(sum(losses));
const equity=Number(s.equitySol||0), start=Number(s.startingEquitySol||1), high=Number(s.highWaterEquitySol||equity); const ret=start>0?(equity/start-1)*100:0, dd=high>0?(1-equity/high)*100:0;
const result={version:"1.1",timestamp:new Date().toISOString(),startingEquitySol:start,equitySol:equity,equityReturnPct:Number(ret.toFixed(4)),highWaterEquitySol:high,currentDrawdownPct:Number(dd.toFixed(4)),openPositions:open.length,probeEntries:buys.length,realizedSellEvents:sells.length,lifecycleTrades:lifecycles.length,completedLifecycleTrades:completed.length,winningLifecycleTrades:wins.length,losingLifecycleTrades:losses.length,winRatePct:completed.length?Number((wins.length/completed.length*100).toFixed(2)):0,grossProfitSol:Number(gp.toFixed(8)),grossLossSol:Number(gl.toFixed(8)),profitFactor:gl>0?Number((gp/gl).toFixed(4)):(gp>0?"INF_NO_LOSS_YET":0),expectancyPerLifecycleSol:completed.length?Number((sum(pnls)/completed.length).toFixed(8)):0,legacyBuyEventsWithoutPositionId:buys.filter(x=>!x.positionId).length,legacySellEventsWithoutPositionId:sells.filter(x=>!x.positionId).length,realizedPnlSol:Number(s.realizedPnlSol||0),unrealizedPnlSol:Number(s.unrealizedPnlSol||0),lifecycles};
const tmp=OUT+`.tmp-${process.pid}`; fs.writeFileSync(tmp,JSON.stringify(result,null,2)); fs.renameSync(tmp,OUT);
console.log("=== MEME ALPHA VALIDATION v1.1 LIFECYCLE ==="); console.log(`CompletedLifecycles=${completed.length}`); console.log(`SellEvents=${sells.length}`); console.log(`WinRateLifecycle=${result.winRatePct}%`); console.log(`ExpectancyLifecycle=${result.expectancyPerLifecycleSol} SOL`); console.log(`LegacySells=${result.legacySellEventsWithoutPositionId}`); console.log("LIVE_EXECUTION=DISABLED"); console.log("VALIDATION_STATUS=PASS");
NODE

python3 - <<'PY'
from pathlib import Path
p=Path('src/position.js'); s=p.read_text()
if 'RISK_STATE_MAX_AGE_SEC' not in s:
    s=s.replace('const WSOL =\n  "So11111111111111111111111111111111111111112";', 'const WSOL =\n  "So11111111111111111111111111111111111111112";\n\nconst SOURCE_HEALTH =\n  "/var/lib/meme-alpha/data/paper/scanner-source-health.json";\nconst RISK_STATE_MAX_AGE_SEC = 120;\nconst SOURCE_HEALTH_MAX_AGE_SEC = 180;')
    s=s.replace('const riskCandidates =\n  new Map(', 'const riskAgeSec = risk.timestamp ? (Date.now() - new Date(risk.timestamp).getTime()) / 1000 : Infinity;\nlet sourceHealth = null;\ntry { sourceHealth = JSON.parse(fs.readFileSync(SOURCE_HEALTH, "utf8")); } catch {}\nconst sourceHealthAgeSec = sourceHealth?.checkedAt ? (Date.now() - new Date(sourceHealth.checkedAt).getTime()) / 1000 : Infinity;\nconst riskStateFresh = Number.isFinite(riskAgeSec) && riskAgeSec >= 0 && riskAgeSec < RISK_STATE_MAX_AGE_SEC;\nconst sourceHealthAllowsEntries = Boolean(sourceHealth && sourceHealth.status === "HEALTHY" && sourceHealth.allowNewEntries === true && sourceHealth.usingCache !== true && sourceHealthAgeSec >= 0 && sourceHealthAgeSec < SOURCE_HEALTH_MAX_AGE_SEC);\nconsole.log(`RISK_STATE_FRESH=${riskStateFresh} age=${Number.isFinite(riskAgeSec)?riskAgeSec.toFixed(1):"INF"}s`);\nconsole.log(`SOURCE_HEALTH_ENTRY_GATE=${sourceHealthAllowsEntries}`);\n\nconst riskCandidates =\n  new Map(')
    s=s.replace('risk.entryAllowed === true &&\n        r?.allowed === true &&', 'riskStateFresh &&\n        sourceHealthAllowsEntries &&\n        risk.entryAllowed === true &&\n        r?.allowed === true &&')
    s=s.replace('paper.openPositions.length <\n    maxPositions &&\n  ready.length > 0 &&', 'riskStateFresh &&\n  sourceHealthAllowsEntries &&\n  paper.openPositions.length <\n    maxPositions &&\n  ready.length > 0 &&')
    s=s.replace('type: "PAPER_SELL",\n    symbol:', 'type: "PAPER_SELL",\n    positionId: pos.id || null,\n    symbol:', 1)
    s=s.replace('type:\n            "PAPER_BUY_PROBE",\n\n          symbol:', 'type:\n            "PAPER_BUY_PROBE",\n\n          positionId:\n            pos.id,\n\n          symbol:', 1)
    s=s.replace('=== PAPER POSITION ENGINE v1.0 JUPITER SIZE-SPECIFIC ===','=== PAPER POSITION ENGINE v1.1 HARDENED JUPITER ===',1)
p.write_text(s)
PY

node - <<'NODE'
import fs from 'node:fs';
const p='package.json'; const j=JSON.parse(fs.readFileSync(p,'utf8'));
j.scripts.cycle5='node src/scanner.js && node src/universe.js && node src/security.js && node src/token2022-audit.js && node src/holder-cluster.js && node src/persistence.js && node src/risk.js && node src/position.js && node src/validation.js';
fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n');
NODE

node --check src/risk.js
node --check src/validation.js
node --check src/position.js

echo '=== FAIL-CLOSED SOURCE HEALTH TEST ==='
cp -f "$DATA/scanner-source-health.json" "$BACKUP/source-health-live.json"
node - <<'NODE'
import fs from 'node:fs'; const p='/var/lib/meme-alpha/data/paper/scanner-source-health.json'; const j=JSON.parse(fs.readFileSync(p,'utf8')); j.checkedAt='2000-01-01T00:00:00.000Z'; fs.writeFileSync(p,JSON.stringify(j,null,2));
NODE
node src/risk.js
node - <<'NODE'
import fs from 'node:fs'; const r=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/risk-state.json','utf8')); if(r.entryAllowed!==false || !r.globalBlockReasons.includes('SOURCE_HEALTH_STALE')) throw new Error('FAIL_CLOSED_TEST_FAILED'); console.log('FAIL_CLOSED_TEST_PASS');
NODE
cp -f "$BACKUP/source-health-live.json" "$DATA/scanner-source-health.json"
node src/risk.js
node src/validation.js

systemctl start "$SERVICE"
sleep 70
systemctl is-active --quiet "$SERVICE"
systemctl is-enabled --quiet "$SERVICE"

echo '=== VERIFY ==='
node - <<'NODE'
import fs from 'node:fs';
const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8')); if(cfg.mode!=='PAPER') throw new Error('MODE_CHANGED');
const risk=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/risk-state.json','utf8')); const val=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/validation.json','utf8'));
if(risk.version!=='1.1') throw new Error('RISK_VERSION_BAD'); if(val.version!=='1.1') throw new Error('VALIDATION_VERSION_BAD'); if(!('sourceHealthHealthy' in risk.health)) throw new Error('SOURCE_HEALTH_GATE_MISSING');
const pos=fs.readFileSync('/opt/meme-alpha/app/src/position.js','utf8'); if(!pos.includes('RISK_STATE_MAX_AGE_SEC = 120')) throw new Error('RISK_FRESHNESS_GATE_MISSING'); if(!pos.includes('positionId: pos.id || null')) throw new Error('SELL_POSITION_ID_MISSING'); if(!pos.includes('positionId:\n            pos.id')) throw new Error('BUY_POSITION_ID_MISSING');
console.log('MODE=PAPER'); console.log('LIVE_EXECUTION=DISABLED'); console.log('RISK_VERSION='+risk.version); console.log('SOURCE_HEALTH='+risk.health.sourceHealthHealthy); console.log('ENTRY_ALLOWED='+risk.entryAllowed); console.log('VALIDATION_VERSION='+val.version); console.log('V110_INVARIANT_PASS');
NODE

tail -100 /var/log/meme-alpha/paper.log | grep -E 'RISK v1.1|RISK_STATE_FRESH|SOURCE_HEALTH_ENTRY_GATE|POSITION ENGINE v1.1|VALIDATION v1.1|CYCLE_COMPLETE|ENTRY_FAIL|OPEN_PROBE' || true
free -h
uptime
echo "V110_DEPLOY_COMPLETE"
echo "BACKUP=$BACKUP"
trap - ERR
