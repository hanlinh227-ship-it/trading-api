import {INSTRUMENT_PROFILES,canonicalInstrument,getInstrumentProfile} from './instrument-profiles.js';
import {V11_CONFIG} from './config.js';

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const has=(p,needle)=>(p?.families||[]).some(x=>String(x).toUpperCase().includes(needle));
const majorFx=new Set(['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD']);
const coreCrypto=new Set(['BTC','ETH','SOL','XRP']);
const fastCrypto=new Set(['HYPE','SUI','INJ','TAO','WIF','BONK','PEPE','FLOKI','POPCAT','PENGU','TRUMP','FARTCOIN','PUMP','MOODENG','PNUT']);
const slowCrypto=new Set(['TRX','LTC','BCH','ETC','XLM']);

// V11.4 deliberately reuses the V77/V78 philosophy:
// - risk is driven by each symbol's historical riskATR prior,
// - room requirement is ~1R rather than swing-grade RR,
// - market context is mostly ranking/soft evidence,
// - only stale/invalid/hard-risk conditions block execution.
function derive(symbol,p){
 const m=p.market,b=V11_CONFIG.markets[m],riskPrior=Number(p.riskAtrPrior||.75),reg=String(p.regimePrior||'GENERIC').toUpperCase();
 let q=b.quality,rr=1.05,target=1.00,stop=clamp(riskPrior,.50,1.05),h=b.horizonMin,drift={crypto:.45,forex:.18,metal:.22,index:.22}[m]||.20,ai=52;
 if(reg==='TREND'){q-=2;target+=.08;ai-=1;}else if(reg==='RELATIVE'){q-=1;target+=.04;}else if(reg==='MEAN_REVERSION'){rr=1.00;target=.92;}else q+=1;
 if(m==='forex'){
  if(majorFx.has(symbol)){q-=2;rr=1.03;target=.95;drift=.16;h=55;}
  else {q-=1;rr=1.02;target=1.00;drift=.20;h=60;}
  if(symbol.endsWith('JPY')){target+=.05;stop+=.04;drift+=.02;}
  if(p.entryRouter==='PB'){q-=1;rr=1.00;}
 }
 if(m==='crypto'){
  rr=1.05;target=1.05;drift=.45;h=50;
  if(coreCrypto.has(symbol)){q-=2;rr=1.04;target=1.00;stop=Math.max(stop,.60);drift=.30;h=50;ai=50;}
  if(fastCrypto.has(symbol)){q-=1;rr=1.03;target=1.15;stop=Math.max(stop,.72);drift=.55;h=45;ai=51;}
  if(slowCrypto.has(symbol)){q-=2;rr=1.02;target=.95;stop=Math.max(stop,.58);drift=.35;h=55;}
  if(has(p,'MEME')){target+=.10;stop+=.08;drift=Math.max(drift,.55);}
  if(has(p,'BTCALIGN')||has(p,'RELATIVE'))q-=1;
 }
 if(m==='metal'){
  if(symbol==='XAUUSD'){q=54;rr=1.05;target=1.05;stop=.82;drift=.22;h=55;ai=51;}
  if(symbol==='XAGUSD'){q=56;rr=1.04;target=1.12;stop=.90;drift=.28;h=50;ai=52;}
 }
 if(m==='index'){
  const ov={NAS100:[53,1.05,1.08,.82,.24,55],SPX500:[52,1.03,.98,.74,.20,60],US30:[54,1.04,1.02,.80,.22,60],GER40:[54,1.04,1.04,.82,.24,60],UK100:[55,1.03,.98,.76,.22,60],JP225:[54,1.04,1.08,.84,.26,60]}[symbol];
  if(ov)[q,rr,target,stop,drift,h]=ov;
  ai=51;
 }
 return Object.freeze({
  symbol,market:m,qualityFloor:clamp(Math.round(q),50,60),minRR:Number(clamp(rr,1.00,1.10).toFixed(2)),
  targetAtr:Number(clamp(target,.85,1.30).toFixed(2)),stopAtr:Number(clamp(stop,.50,1.10).toFixed(2)),
  riskAtr:Number(clamp(riskPrior,.35,1.35).toFixed(2)),horizonMin:Math.round(clamp(h,45,75)),
  entryDriftMaxPct:Number(clamp(drift,.14,.60).toFixed(2)),aiMinConfidence:Math.round(clamp(ai,50,55)),
  minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:p.families,entryRouter:p.entryRouter,regimePrior:p.regimePrior,
  exitStyle:'V77_V78_STRUCTURE_ATR',hardBlocks:Object.freeze(['STALE_QUOTE','INVALID_GEOMETRY','HARD_NEWS_BLACKOUT','VOLATILITY_SHOCK','EXTREME_CHASE','PRICE_SOURCE_DIVERGENCE'])
 });
}

const policies=Object.fromEntries(Object.entries(INSTRUMENT_PROFILES).map(([s,p])=>[s,derive(s,p)]));
export const SYMBOL_SCALP_POLICIES=Object.freeze(policies);
export function getSymbolScalpPolicy(symbol,market=null){const s=canonicalInstrument(symbol),p=policies[s];if(p&&(!market||p.market===market))return p;const ip=getInstrumentProfile(s);if(ip&&(!market||ip.market===market))return derive(s,ip);const m=market||ip?.market||'crypto',b=V11_CONFIG.markets[m]||V11_CONFIG.markets.crypto;return Object.freeze({symbol:s,market:m,qualityFloor:b.quality,minRR:1.05,targetAtr:1.00,stopAtr:.75,riskAtr:.75,horizonMin:60,entryDriftMaxPct:{crypto:.45,forex:.18,metal:.22,index:.22}[m]||.20,aiMinConfidence:52,minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:[],entryRouter:'ROUTER',regimePrior:'GENERIC',exitStyle:'V77_V78_STRUCTURE_ATR',hardBlocks:[]});}
