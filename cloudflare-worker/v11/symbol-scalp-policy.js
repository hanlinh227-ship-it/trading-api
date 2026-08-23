import {INSTRUMENT_PROFILES,canonicalInstrument,getInstrumentProfile} from './instrument-profiles.js';
import {V11_CONFIG} from './config.js';

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const has=(p,needle)=>(p?.families||[]).some(x=>String(x).toUpperCase().includes(needle));
const majorFx=new Set(['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD']);
const coreCrypto=new Set(['BTC','ETH','SOL','XRP']);
const fastCrypto=new Set(['HYPE','SUI','INJ','TAO','WIF','BONK','PEPE','FLOKI','POPCAT','PENGU','TRUMP','FARTCOIN','PUMP','MOODENG','PNUT']);
const slowCrypto=new Set(['TRX','LTC','BCH','ETC','XLM']);

function derive(symbol,p){
 const m=p.market,b=V11_CONFIG.markets[m],risk=Number(p.riskAtrPrior||.75),reg=String(p.regimePrior||'GENERIC').toUpperCase();
 let q=b.quality,rr=b.minRR,target=b.scalpTargetAtr,h=b.horizonMin,drift={crypto:.28,forex:.12,metal:.16,index:.16}[m]||.15,ai=54;
 if(reg==='TREND'){q-=2;target+=.05;ai-=1;}else if(reg==='RELATIVE'){q-=1;}else if(reg==='MEAN_REVERSION'){q+=1;rr-=.03;target-=.05;}else q+=2;
 if(risk<=.55){q-=1;rr-=.02;drift-=.01;}else if(risk>=1){q+=2;rr+=.03;drift+=.03;target+=.05;}
 if(m==='forex'){
  if(majorFx.has(symbol)){q-=2;drift=.10;h=50;}
  else {q+=1;drift=.13;h=55;}
  if(symbol.endsWith('JPY')){target+=.03;drift+=.01;}
  if(p.entryRouter==='PB'){q-=1;rr-=.02;}
 }
 if(m==='crypto'){
  if(coreCrypto.has(symbol)){q-=2;drift=.18;h=40;ai=52;}
  if(fastCrypto.has(symbol)){q+=1;drift=.35;target+=.10;h=35;ai=53;}
  if(slowCrypto.has(symbol)){q-=1;drift=.22;target-=.05;h=45;}
  if(has(p,'MEME')){q+=2;rr+=.02;drift=Math.max(drift,.35);target+=.08;}
  if(has(p,'BTCALIGN')||has(p,'RELATIVE'))q-=1;
 }
 if(m==='metal'){
  if(symbol==='XAUUSD'){q=57;rr=1.05;target=.72;drift=.14;h=50;ai=53;}
  if(symbol==='XAGUSD'){q=59;rr=1.08;target=.78;drift=.20;h=45;ai=54;}
 }
 if(m==='index'){
  const ov={NAS100:[56,1.04,.72,.15,45],SPX500:[55,1.03,.62,.12,50],US30:[57,1.05,.68,.14,50],GER40:[57,1.05,.70,.15,50],UK100:[58,1.05,.64,.13,50],JP225:[57,1.05,.70,.16,50]}[symbol];
  if(ov)[q,rr,target,drift,h]=ov;
  ai=53;
 }
 return Object.freeze({
  symbol,market:m,qualityFloor:clamp(Math.round(q),50,64),minRR:Number(clamp(rr,.95,1.15).toFixed(2)),
  targetAtr:Number(clamp(target,.50,.95).toFixed(2)),riskAtr:Number(clamp(risk,.35,1.35).toFixed(2)),
  horizonMin:Math.round(clamp(h,30,60)),entryDriftMaxPct:Number(clamp(drift,.08,.40).toFixed(2)),
  aiMinConfidence:Math.round(clamp(ai,50,58)),minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,
  preferredSetups:p.families,entryRouter:p.entryRouter,regimePrior:p.regimePrior,
  hardBlocks:Object.freeze(['STALE_QUOTE','INVALID_GEOMETRY','HARD_NEWS_BLACKOUT','VOLATILITY_SHOCK','EXTREME_CHASE','PRICE_SOURCE_DIVERGENCE'])
 });
}

const policies=Object.fromEntries(Object.entries(INSTRUMENT_PROFILES).map(([s,p])=>[s,derive(s,p)]));
export const SYMBOL_SCALP_POLICIES=Object.freeze(policies);
export function getSymbolScalpPolicy(symbol,market=null){const s=canonicalInstrument(symbol),p=policies[s];if(p&&(!market||p.market===market))return p;const ip=getInstrumentProfile(s);if(ip&&(!market||ip.market===market))return derive(s,ip);const m=market||ip?.market||'crypto',b=V11_CONFIG.markets[m]||V11_CONFIG.markets.crypto;return Object.freeze({symbol:s,market:m,qualityFloor:b.quality,minRR:b.minRR,targetAtr:b.scalpTargetAtr,riskAtr:.75,horizonMin:b.horizonMin,entryDriftMaxPct:{crypto:.25,forex:.12,metal:.16,index:.16}[m]||.15,aiMinConfidence:54,minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:[],entryRouter:'ROUTER',regimePrior:'GENERIC',hardBlocks:[]});}
