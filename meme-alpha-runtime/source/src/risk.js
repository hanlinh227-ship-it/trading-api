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
