import fs from 'node:fs';

function patch(path, replacements){
  let s=fs.readFileSync(path,'utf8');
  for(const [from,to] of replacements){
    if(!s.includes(from)) throw new Error(`${path}: missing patch anchor: ${from.slice(0,120)}`);
    s=s.replace(from,to);
  }
  fs.writeFileSync(path,s);
}

patch('cloudflare-worker/bybit-runtime-contract.js',[
  ['BYBIT-AUTO-1.8.7','BYBIT-AUTO-1.8.8']
]);

patch('cloudflare-worker/bybit-auto-config.js',[
  ['// BYBIT-AUTO-1.8.7: universal equity-aware sizing across the full scan universe; no fixed USD entry floor.','// BYBIT-AUTO-1.8.8: continuous equity-curve sizing, full-capital portfolio allocation, no fixed position-count cap.'],
  ['maxOpenPositions:3,','maxOpenPositions:1000000,'],
  ['mode:"EQUITY_EXECUTION_COST_SCALED_ALLOCATOR",','mode:"CONTINUOUS_EQUITY_CURVE_FULL_CAPITAL_ALLOCATOR",'],
  ['minRewardUsd:0,\n    targetRiskPctOfEquity:6,','minRewardUsd:0,\n    minRiskUtilizationPct:60,\n    microAccountMinRiskUtilizationPct:35,\n    smallAccountMinRiskUtilizationPct:55,\n    riskCurveAnchorEquityUsd:25,\n    riskCurveSmallPct:6,\n    riskCurveLargeFloorPct:.75,\n    riskCurveDecayPerDecade:1.25,\n    targetRiskPctOfEquity:6,'],
  ['maxTotalOpenRiskPct:18,','maxTotalOpenRiskPct:24,'],
  ['maxMarginPerPositionPct:40,','maxMarginPerPositionPct:100,'],
  ['minFreeReservePct:18,','minFreeReservePct:0,'],
  ['maxPortfolioMarginPct:80,','maxPortfolioMarginPct:100,'],
  ['maxSameDirectionPositions:2,','maxSameDirectionPositions:1000000,'],
  ['c.risk.maxTotalOpenRiskPct=Math.max(6,Math.min(18,n(env,"BYBIT_MAX_TOTAL_OPEN_RISK_PCT",c.risk.maxTotalOpenRiskPct)));','c.risk.maxTotalOpenRiskPct=Math.max(4,Math.min(24,n(env,"BYBIT_MAX_TOTAL_OPEN_RISK_PCT",c.risk.maxTotalOpenRiskPct)));'],
  ['c.risk.maxMarginPerPositionPct=Math.max(10,Math.min(40,n(env,"BYBIT_MAX_MARGIN_PER_POSITION_PCT",c.risk.maxMarginPerPositionPct)));','c.risk.maxMarginPerPositionPct=Math.max(10,Math.min(100,n(env,"BYBIT_MAX_MARGIN_PER_POSITION_PCT",c.risk.maxMarginPerPositionPct)));'],
  ['c.risk.minFreeReservePct=Math.max(18,Math.min(40,n(env,"BYBIT_MIN_FREE_RESERVE_PCT",c.risk.minFreeReservePct)));','c.risk.minFreeReservePct=Math.max(0,Math.min(20,n(env,"BYBIT_MIN_FREE_RESERVE_PCT",c.risk.minFreeReservePct)));'],
  ['c.risk.maxPortfolioMarginPct=Math.max(40,Math.min(80,n(env,"BYBIT_MAX_PORTFOLIO_MARGIN_PCT",c.risk.maxPortfolioMarginPct)));','c.risk.maxPortfolioMarginPct=Math.max(50,Math.min(100,n(env,"BYBIT_MAX_PORTFOLIO_MARGIN_PCT",c.risk.maxPortfolioMarginPct)));'],
  ['c.maxOpenPositions=Math.max(1,Math.min(3,Math.round(n(env,"BYBIT_MAX_OPEN_POSITIONS",c.maxOpenPositions))));','c.maxOpenPositions=Math.max(1,Math.min(1000000,Math.round(n(env,"BYBIT_MAX_OPEN_POSITIONS",c.maxOpenPositions))));'],
  ['c.maxTradesPerDay=1000000000;','c.maxTradesPerDay=1000000000;\n  c.risk.minRiskUtilizationPct=Math.max(40,Math.min(80,n(env,"BYBIT_MIN_RISK_UTILIZATION_PCT",c.risk.minRiskUtilizationPct)));\n  c.risk.microAccountMinRiskUtilizationPct=Math.max(20,Math.min(c.risk.minRiskUtilizationPct,n(env,"BYBIT_MICRO_MIN_RISK_UTILIZATION_PCT",c.risk.microAccountMinRiskUtilizationPct)));\n  c.risk.smallAccountMinRiskUtilizationPct=Math.max(c.risk.microAccountMinRiskUtilizationPct,Math.min(c.risk.minRiskUtilizationPct,n(env,"BYBIT_SMALL_MIN_RISK_UTILIZATION_PCT",c.risk.smallAccountMinRiskUtilizationPct)));']
]);

patch('cloudflare-worker/bybit-scalp-engine.js',[
  ['function liquidityQualityBonus(metrics={}){const spread=Math.max(0,Number(metrics.spreadBps||0)),turnover=Math.max(1,Number(metrics.turnover24h||0)),spreadScore=clamp((8-spread)/8,0,1),turnoverScore=clamp(Math.log10(turnover/10_000_000)/3,0,1);return (spreadScore+turnoverScore)*.5;}','function liquidityQualityBonus(metrics={}){const spread=Math.max(0,Number(metrics.spreadBps||0)),turnover=Math.max(1,Number(metrics.turnover24h||0)),spreadScore=clamp((8-spread)/8,0,1),turnoverScore=clamp(Math.log10(turnover/10_000_000)/3,0,1);return (spreadScore+turnoverScore)*.5;}\nfunction equityRiskCurvePct(equity,cfg){const r=cfg?.risk||{},anchor=Math.max(.5,Number(r.riskCurveAnchorEquityUsd||25)),small=Math.max(.1,Number(r.riskCurveSmallPct||6)),floor=Math.max(.1,Number(r.riskCurveLargeFloorPct||.75)),decay=Math.max(.1,Number(r.riskCurveDecayPerDecade||1.25)),decades=Math.log10(Math.max(1,equity/anchor));return clamp(small-decay*decades,floor,small);}\nfunction minimumRiskUtilizationPct(equity,cfg){const r=cfg?.risk||{};if(equity<10)return Number(r.microAccountMinRiskUtilizationPct||35);if(equity<50)return Number(r.smallAccountMinRiskUtilizationPct||55);return Number(r.minRiskUtilizationPct||60); }'],
  ['env.BYBIT_MIN_TURNOVER_24H_USD||5000000','env.BYBIT_MIN_TURNOVER_24H_USD||1000000'],
  ['env.BYBIT_MAX_UNIVERSE_SPREAD_BPS||12','env.BYBIT_MAX_UNIVERSE_SPREAD_BPS||15'],
  ['sizingAuthority:"UNIVERSAL_EQUITY_EXECUTION_COST_V187"','sizingAuthority:"EQUITY_CURVE_FULL_CAPITAL_V188"'],
  ['const reservePct=clamp(Number(cfg.risk.minFreeReservePct||18),15,40),feeBufferPct=clamp(Number(cfg.risk.feeBufferPct||4),2,12),slotCeilingPct=Math.min(Number(cfg.risk.maxMarginPerPositionPct||40),100-reservePct);\n  const grossMarginBudgetUsd=equity*slotCeilingPct/100,marginBudgetUsd=grossMarginBudgetUsd*(1-feeBufferPct/100);','const reservePct=clamp(Number(cfg.risk.minFreeReservePct??0),0,20),feeBufferPct=clamp(Number(cfg.risk.feeBufferPct||4),2,12),slotCeilingPct=Math.min(Number(cfg.risk.maxMarginPerPositionPct||100),100-reservePct);\n  const grossMarginBudgetUsd=equity*slotCeilingPct/100,marginBudgetUsd=grossMarginBudgetUsd;'],
  ['const maxRiskPct=Math.max(.1,Number(cfg.risk.maxRiskPctOfEquity||8)),targetRiskPct=Math.min(maxRiskPct,Math.max(.1,Number(cfg.risk.targetRiskPctOfEquity||6)));\n  const equityRiskCapUsd=equity*maxRiskPct/100,targetRiskUsd=equity*targetRiskPct/100,riskBudgetUsd=Math.min(targetRiskUsd,equityRiskCapUsd);','const targetRiskPct=equityRiskCurvePct(equity,cfg),configuredMaxRiskPct=Math.max(.1,Number(cfg.risk.maxRiskPctOfEquity||8)),maxRiskPct=Math.min(configuredMaxRiskPct,Math.max(targetRiskPct,targetRiskPct*1.35));\n  const equityRiskCapUsd=equity*maxRiskPct/100,targetRiskUsd=equity*targetRiskPct/100,riskBudgetUsd=Math.min(targetRiskUsd,equityRiskCapUsd);'],
  ['const riskUsd=qty*dist,structureRewardUsd=structureTp>0?qty*Math.abs(structureTp-entry):Infinity,minRR=Math.max(1,Number(cfg.risk.minRR||1.5));','const riskUsd=qty*dist,structureRewardUsd=structureTp>0?qty*Math.abs(structureTp-entry):Infinity,minRR=Math.max(1,Number(cfg.risk.minRR||1.5)),minRiskUtilizationPct=minimumRiskUtilizationPct(equity,cfg),minAcceptedRiskUsd=targetRiskUsd*minRiskUtilizationPct/100;\n  if(riskUsd+1e-9<minAcceptedRiskUsd)return {ok:false,reason:"RISK_UTILIZATION_TOO_LOW_FOR_EQUITY_SCALE",qty,notional,riskUsd,targetRiskUsd,minAcceptedRiskUsd,minRiskUtilizationPct,equityUsd:equity,leverage,initialMarginUsd,marginBudgetUsd};'],
  ['capitalMode:"UNIVERSAL_EQUITY_EXECUTION_COST_V187"','capitalMode:"EQUITY_CURVE_FULL_CAPITAL_V188"'],
  ['riskBudgetUsd,targetRiskUsd,rewardUsd','riskBudgetUsd,targetRiskUsd,targetRiskPct,minRiskUtilizationPct,rewardUsd']
]);

patch('cloudflare-worker/bybit-risk-guard.js',[
  ['const num=v=>Number.isFinite(Number(v))?Number(v):0;','const num=v=>Number.isFinite(Number(v))?Number(v):0;\nconst clamp=(x,a,b)=>Math.max(a,Math.min(b,x));\nfunction equityRiskCurvePct(equity,cfg){const r=cfg?.risk||{},anchor=Math.max(.5,num(r.riskCurveAnchorEquityUsd)||25),small=Math.max(.1,num(r.riskCurveSmallPct)||6),floor=Math.max(.1,num(r.riskCurveLargeFloorPct)||.75),decay=Math.max(.1,num(r.riskCurveDecayPerDecade)||1.25),decades=Math.log10(Math.max(1,equity/anchor));return clamp(small-decay*decades,floor,small); }'],
  ['const singleCapUsd=equity*Math.max(0,num(cfg?.risk?.maxRiskPctOfEquity))/100;','const targetRiskPct=equityRiskCurvePct(equity,cfg),configuredSinglePct=Math.max(.1,num(cfg?.risk?.maxRiskPctOfEquity)||8),singleRiskPct=Math.min(configuredSinglePct,Math.max(targetRiskPct,targetRiskPct*1.35)),singleCapUsd=equity*singleRiskPct/100;'],
  ['const capUsd=equity*Math.max(0,num(cfg?.risk?.maxTotalOpenRiskPct))/100;','const configuredTotalPct=Math.max(4,num(cfg?.risk?.maxTotalOpenRiskPct)||24),totalOpenRiskPct=Math.min(configuredTotalPct,Math.max(4,targetRiskPct*4)),capUsd=equity*totalOpenRiskPct/100;'],
  ['return {ok:true,realizedUsd:realized,openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,singleCapUsd,openInitialMarginUsd,candidateMarginUsd,portfolioMarginCapUsd,dailyLossStopEnabled:false,dailyTargetEnabled:false,continuousTrading:true,riskAccounting:"MANAGED_STOP_AWARE",marginAccounting:providedMarginUsd>0?"ACTUAL_CANDIDATE_INITIAL_MARGIN_V187":"FAIL_SAFE_SLOT_FALLBACK"};','return {ok:true,realizedUsd:realized,openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,singleCapUsd,targetRiskPct,singleRiskPct,totalOpenRiskPct,openInitialMarginUsd,candidateMarginUsd,portfolioMarginCapUsd,dailyLossStopEnabled:false,dailyTargetEnabled:false,continuousTrading:true,riskAccounting:"MANAGED_STOP_AWARE_EQUITY_CURVE_V188",marginAccounting:providedMarginUsd>0?"ACTUAL_CANDIDATE_INITIAL_MARGIN_V188":"FAIL_SAFE_SLOT_FALLBACK"};']
]);

patch('cloudflare-worker/bybit-auto-v1.js',[
  ['    if(positions.length>=cfg.maxOpenPositions)return {ok:true,executed:false,mode,reason:"MAX_OPEN_POSITIONS",positions:positions.length,equity,lifecycles,state};\n',''],
  ['  const sameDir=positions.filter(p=>String(p.side)===setup.side).length;if(sameDir>=cfg.risk.maxSameDirectionPositions)return {ok:true,executed:false,mode,reason:"SAME_DIRECTION_CAP",preparation,setup,scan,lifecycles,state};\n',''],
  ['const riskPreflight=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:sizing.riskUsd});','const riskPreflight=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:sizing.riskUsd,candidateInitialMarginUsd:sizing.initialMarginUsd});'],
  ['const actualRiskGuard=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:actualRisk});','const actualRiskGuard=bybitRiskPreflight({cfg,equityUsd:equity,state:riskState,candidateRiskUsd:actualRisk,candidateInitialMarginUsd:sizing.initialMarginUsd});']
]);

patch('cloudflare-worker/validate-worker.mjs',[
  ['BYBIT-AUTO-1.8.7','BYBIT-AUTO-1.8.8'],
  ['EQUITY_EXECUTION_COST_SCALED_ALLOCATOR','CONTINUOUS_EQUITY_CURVE_FULL_CAPITAL_ALLOCATOR'],
  ['UNIVERSAL_EQUITY_EXECUTION_COST_V187','EQUITY_CURVE_FULL_CAPITAL_V188'],
  ['maxTotalOpenRiskPct:18','maxTotalOpenRiskPct:24'],
  ['maxPortfolioMarginPct:80','maxPortfolioMarginPct:100'],
  ['maxMarginPerPositionPct:40','maxMarginPerPositionPct:100'],
  ['minFreeReservePct:18','minFreeReservePct:0'],
  ['Worker AUTO preflight PASS: Bybit 1.8.7 universal equity/fee-aware sizing','Worker AUTO preflight PASS: Bybit 1.8.8 continuous equity curve + full-capital allocation']
]);

patch('.github/workflows/deploy-cloudflare-worker.yml',[
  ["BYBIT-AUTO-1.8.7","BYBIT-AUTO-1.8.8"]
]);

// Temporary patch machinery must not land on main.
for(const p of ['scripts/apply-bybit-188.mjs','.github/workflows/bybit-188-patch.yml']){
  try{fs.rmSync(p);}catch{}
}
console.log('BYBIT_188_PATCH_APPLIED');
