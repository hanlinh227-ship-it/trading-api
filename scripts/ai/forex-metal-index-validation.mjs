import fs from 'node:fs';
import assert from 'node:assert/strict';
const e=fs.readFileSync('cloudflare-worker/engine-v77168.js','utf8');
const C={
  metalPriors:e.includes('const METAL_PRIORS = {')&&e.includes('METAL_GOLD_ADAPTIVE')&&e.includes('METAL_SILVER_ADAPTIVE'),
  metalRouter:e.includes('METAL_RUNTIME_PRIORS_R1')&&e.includes('METAL_SIGNAL_RUNTIME_PRIOR'),
  forexOverride:e.includes('type==="forex"&&allowed.length===1&&allowed[0]==="MEAN_REVERSION"&&trendSide!=="NEUTRAL"&&trendStrength>=.67&&hAlign&&momOK'),
  routeEvidence:e.includes('longRev:!!longRev,shortRev:!!shortRev,mrSide'),
  mrLocation:e.includes('MEAN_REVERSION_RECLAIM_ZONE')&&e.includes('M15.bullishReclaim===true')&&e.includes('M15.bearishReclaim===true'),
  mrTrigger:e.includes('M5_MEAN_REVERSION_RECLAIM')&&e.includes('M5.bullishReclaim===true')&&e.includes('M5.bearishReclaim===true'),
  yahooSafe:e.includes('source:"Yahoo Finance Cash Index Fallback"')&&e.includes('instrumentIdentity:"CASH_INDEX"'),
  tdFallback:e.includes('source:"Twelve Data Index Quote Fallback"'),
  antiChase:e.includes('pass:chase<=.70&&notExtreme'),
  signalOnly:e.includes('executionAuthority:"SIGNAL_ONLY"')&&e.includes('signalOnly:true'),
  rr:e.includes('function minimumQualityRR')&&e.includes('function rrQuality'),
  structuralSL:e.includes('function buildTradePlan')&&e.includes('STRUCTURE_LIQUIDITY')
};
for(const [k,v] of Object.entries(C)){assert.equal(v,true,k);console.log('PASS',k)}
console.log(`V78-032 PASS ${Object.keys(C).length}/${Object.keys(C).length}`)
