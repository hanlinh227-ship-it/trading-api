import fs from "node:fs";

const CFG = "/opt/meme-alpha/app/config/runtime.json";
const SCAN = "/var/lib/meme-alpha/data/paper/scanner-latest.json";
const PERSIST = "/var/lib/meme-alpha/data/paper/persistence-state.json";
const SOURCE = "/var/lib/meme-alpha/data/paper/scanner-source-health.json";
const PAPER = "/var/lib/meme-alpha/data/paper/state.json";
const OUT = "/var/lib/meme-alpha/data/paper/reaction-telemetry.json";
const HISTORY = "/var/lib/meme-alpha/data/paper/reaction-history.jsonl";

const read = p => JSON.parse(fs.readFileSync(p, "utf8"));
const n = (v, d = 0) => Number.isFinite(Number(v)) ? Number(v) : d;
const avg = a => a.length ? a.reduce((x,y)=>x+y,0)/a.length : 0;

const cfg = read(CFG);
if (cfg.mode !== "PAPER") throw new Error("SAFETY_BLOCK_NOT_PAPER");
const scan = read(SCAN);
const persist = read(PERSIST);
const source = read(SOURCE);
const paper = read(PAPER);
const nowMs = Date.now();
const sourceAgeSec = source.checkedAt ? (nowMs - new Date(source.checkedAt).getTime()) / 1000 : Infinity;
const sourceHealthy = source.status === "HEALTHY" && source.allowNewEntries === true && source.usingCache !== true && n(source.successfulSources) >= 2 && sourceAgeSec >= 0 && sourceAgeSec < 180;
const byMint = new Map((scan.candidates || []).filter(x=>x?.mint).map(x=>[x.mint,x]));
const rows = [];

for (const t of Object.values(persist.tokens || {})) {
  const c = byMint.get(t.mint);
  if (!c) continue;
  const obs = Array.isArray(t.observations) ? t.observations : [];
  const last2 = obs.slice(-2);
  const last3 = obs.slice(-3);
  const scores2 = last2.map(x=>n(x.score));
  const buyers2 = last2.map(x=>n(x.netBuyers5m));
  const liq2 = last2.map(x=>n(x.liquidityUsd)).filter(x=>x>0);
  const scoreSlope = last2.length === 2 ? scores2[1] - scores2[0] : 0;
  const buyerSlope = last2.length === 2 ? buyers2[1] - buyers2[0] : 0;
  const liquidityStability = liq2.length === 2 && Math.max(...liq2)>0 ? Math.min(...liq2)/Math.max(...liq2) : 1;
  const impact = Number(c.sellPriceImpactPct);
  const impactKnownGood = Number.isFinite(impact) && impact <= n(cfg.maxPriceImpactPct,2);
  const hardSafe = c.decision === "PROBE_CANDIDATE" && c.securityDecision === "PASS" && c.universeClass !== "NON_MEME" && !c.token2022 && (c.hardReject || []).length === 0 && c.sellRoute === true && n(c.liquidityUsd) >= n(cfg.minLiquidityUsd,25000) && impactKnownGood;
  const currentScore = n(c.score);
  const currentMove5m = n(c.priceChange5m);
  const twoPositiveBuyerObs = last2.length === 2 && buyers2.every(x=>x>0);
  const shadowFastTrack = sourceHealthy && hardSafe && n(t.consecutiveEligible) >= 2 && currentScore >= 80 && avg(scores2) >= 78 && twoPositiveBuyerObs && liquidityStability >= 0.85 && currentMove5m >= -4 && currentMove5m <= 18;
  const actualReady = t.persistenceDecision === "PAPER_ENTRY_READY";
  const firstSeenMs = t.firstSeenAt ? new Date(t.firstSeenAt).getTime() : NaN;
  const ageSec = Number.isFinite(firstSeenMs) ? Math.max(0,(nowMs-firstSeenMs)/1000) : null;
  const reasons=[];
  if(!sourceHealthy) reasons.push("SOURCE_NOT_HEALTHY");
  if(!hardSafe) reasons.push("HARD_SAFETY_NOT_READY");
  if(n(t.consecutiveEligible)<2) reasons.push("NEEDS_TWO_ELIGIBLE");
  if(currentScore<80) reasons.push("SCORE_LT_80");
  if(avg(scores2)<78) reasons.push("AVG2_LT_78");
  if(!twoPositiveBuyerObs) reasons.push("BUYERS_NOT_PERSISTENT");
  if(liquidityStability<0.85) reasons.push("LIQUIDITY_UNSTABLE");
  if(currentMove5m < -4 || currentMove5m > 18) reasons.push("MOVE5M_OUTSIDE_SHADOW_BAND");
  rows.push({
    mint:t.mint,
    symbol:t.symbol,
    actualReady,
    shadowFastTrack,
    persistenceDecision:t.persistenceDecision,
    consecutiveEligible:n(t.consecutiveEligible),
    currentScore,
    avgScore2:Number(avg(scores2).toFixed(3)),
    avgScore3:Number(avg(last3.map(x=>n(x.score))).toFixed(3)),
    scoreSlope:Number(scoreSlope.toFixed(3)),
    avgNetBuyers2:Number(avg(buyers2).toFixed(3)),
    buyerSlope:Number(buyerSlope.toFixed(3)),
    liquidityStability2:Number(liquidityStability.toFixed(4)),
    currentMove5m:Number(currentMove5m.toFixed(3)),
    sellImpactPct:Number.isFinite(impact)?impact:null,
    sourceCount:Array.isArray(c.sources)?c.sources.length:null,
    ageSec:ageSec===null?null:Number(ageSec.toFixed(1)),
    blockers:shadowFastTrack?[]:reasons
  });
}

rows.sort((a,b)=>Number(b.shadowFastTrack)-Number(a.shadowFastTrack) || b.currentScore-a.currentScore);
const result={
  version:"1.1.3-shadow",
  timestamp:new Date().toISOString(),
  mode:"PAPER",
  behaviorChange:false,
  sourceHealthy,
  sourceAgeSec:Number.isFinite(sourceAgeSec)?Number(sourceAgeSec.toFixed(1)):null,
  equitySol:n(paper.equitySol),
  openPositions:(paper.openPositions||[]).length,
  candidatesObserved:rows.length,
  actualReadyCount:rows.filter(x=>x.actualReady).length,
  shadowFastTrackCount:rows.filter(x=>x.shadowFastTrack).length,
  shadowFastTrack:rows.filter(x=>x.shadowFastTrack).slice(0,20),
  topReactionCandidates:rows.slice(0,30)
};

const tmp=`${OUT}.tmp-${process.pid}`;
fs.writeFileSync(tmp,JSON.stringify(result,null,2));
fs.renameSync(tmp,OUT);
fs.appendFileSync(HISTORY,JSON.stringify({timestamp:result.timestamp,sourceHealthy:result.sourceHealthy,candidatesObserved:result.candidatesObserved,actualReadyCount:result.actualReadyCount,shadowFastTrackCount:result.shadowFastTrackCount,shadowFastTrack:result.shadowFastTrack.map(x=>({mint:x.mint,symbol:x.symbol,currentScore:x.currentScore,avgScore2:x.avgScore2,scoreSlope:x.scoreSlope,avgNetBuyers2:x.avgNetBuyers2,buyerSlope:x.buyerSlope,liquidityStability2:x.liquidityStability2,currentMove5m:x.currentMove5m,ageSec:x.ageSec}))})+"\n");
try {
  const st=fs.statSync(HISTORY);
  if(st.size>5*1024*1024){
    const lines=fs.readFileSync(HISTORY,"utf8").trim().split("\n").slice(-2000);
    fs.writeFileSync(HISTORY,lines.join("\n")+"\n");
  }
} catch {}

console.log("=== MEME ALPHA REACTION TELEMETRY v1.1.3 SHADOW ===");
console.log(`SOURCE_HEALTHY=${sourceHealthy}`);
console.log(`CANDIDATES_OBSERVED=${result.candidatesObserved}`);
console.log(`ACTUAL_READY=${result.actualReadyCount}`);
console.log(`SHADOW_FAST_TRACK=${result.shadowFastTrackCount}`);
for(const x of result.shadowFastTrack.slice(0,5)) console.log(`SHADOW ${x.symbol} score=${x.currentScore} avg2=${x.avgScore2} slope=${x.scoreSlope} buyers2=${x.avgNetBuyers2} liqStable=${x.liquidityStability2}`);
console.log("BEHAVIOR_CHANGE=false");
console.log("REACTION_TELEMETRY_STATUS=PASS");
