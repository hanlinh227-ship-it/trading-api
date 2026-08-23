import {INSTRUMENT_PROFILES,canonicalInstrument,getInstrumentProfile} from './instrument-profiles.js';
import {V11_CONFIG} from './config.js';

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const has=(p,needle)=>(p?.families||[]).some(x=>String(x).toUpperCase().includes(needle));
const majorFx=new Set(['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD']);
const coreCrypto=new Set(['BTC','ETH','SOL','XRP']);
const fastCrypto=new Set(['HYPE','SUI','INJ','TAO','WIF','BONK','PEPE','FLOKI','POPCAT','PENGU','TRUMP','FARTCOIN','PUMP','MOODENG','PNUT']);
const slowCrypto=new Set(['TRX','LTC','BCH','ETC','XLM']);

function derive(symbol,p){
 const m=p.market,b=V11_CONFIG.markets[m],riskPrior=Number(p.riskAtrPrior||.75),reg=String(p.regimePrior||'GENERIC').toUpperCase();
 let q=b.quality,rr=b.minRR,target=.55,stop=.48,h=b.horizonMin,drift={crypto:.28,forex:.12,metal:.16,index:.16}[m]||.15,ai=54;
 if(reg==='TREND'){q-=2;target+=.05;stop+=.03;ai-=1;}else if(reg==='RELATIVE'){q-=1;target+=.03;}else if(reg==='MEAN_REVERSION'){q+=1;rr-=.04;target-=.04;stop-=.03;}else q+=2;
 if(riskPrior<=.55){q-=1;stop-=.05;drift-=.01;}else if(riskPrior>=1){q+=2;stop+=.08;target+=.08;drift+=.03;}
 if(m==='forex'){
  if(majorFx.has(symbol)){q-=2;rr=Math.min(rr,1.02);target=.42;stop=.38;drift=.10;h=35;}
  else {q+=1;rr=Math.min(rr,1.05);target=.48;stop=.43;drift=.13;h=40;}
  if(symbol.endsWith('JPY')){target+=.04;stop+=.03;drift+=.01;}
  if(p.entryRouter==='PB'){q-=1;rr-=.02;target-=.02;}
 }
 if(m==='crypto'){
  target=.58;stop=.50;rr=Math.min(rr,1.08);
  if(coreCrypto.has(symbol)){q-=2;target=.50;stop=.44;drift=.18;h=30;ai=52;}
  if(fastCrypto.has(symbol)){q+=1;target=.68;stop=.58;drift=.35;h=25;ai=53;}
  if(slowCrypto.has(symbol)){q-=1;target=.48;stop=.42;drift=.22;h=35;}
  if(has(p,'MEME')){q+=2;target+=.07;stop+=.06;drift=Math.max(drift,.35);}
  if(has(p,'BTCALIGN')||has(p,'RELATIVE'))q-=1;
 }
 if(m==='metal'){
  if(symbol==='XAUUSD'){q=57;rr=1.03;target=.46;stop=.40;drift=.14;h=35;ai=53;}
  if(symbol==='XAGUSD'){q=59;rr=1.04;target=.58;stop=.50;drift=.20;h=30;ai=54;}
 }
 if(m==='index'){
  const ov={NAS100:[56,1.02,.50,.44,.15,30],SPX500:[55,1.01,.40,.36,.12,35],US30:[57,1.02,.46,.40,.14,35],GER40:[57,1.02,.48,.42,.15,35],UK100:[58,1.02,.42,.38,.13,35],JP225:[57,1.02,.50,.44,.16,35]}[symbol];
  if(ov)[q,rr,target,stop,drift,h]=ov;
  ai=53;
 }
 return Object.freeze({
  symbol,market:m,qualityFloor:clamp(Math.round(q),50,64),minRR:Number(clamp(rr,.98,1.10).toFixed(2)),
  targetAtr:Number(clamp(target,.35,.85).toFixed(2)),stopAtr:Number(clamp(stop,.30,.75).toFixed(2)),
  riskAtr:Number(clamp(riskPrior,.35,1.35).toFixed(2)),horizonMin:Math.round(clamp(h,20,45)),
  entryDriftMaxPct:Number(clamp(drift,.08,.40).toFixed(2)),aiMinConfidence:Math.round(clamp(ai,50,58)),
  minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:p.families,entryRouter:p.entryRouter,regimePrior:p.regimePrior,
  exitStyle:'MICRO_SCALP_ATR_STRUCTURE',hardBlocks:Object.freeze(['STALE_QUOTE','INVALID_GEOMETRY','HARD_NEWS_BLACKOUT','VOLATILITY_SHOCK','EXTREME_CHASE','PRICE_SOURCE_DIVERGENCE'])
 });
}

const policies=Object.fromEntries(Object.entries(INSTRUMENT_PROFILES).map(([s,p])=>[s,derive(s,p)]));
export const SYMBOL_SCALP_POLICIES=Object.freeze(policies);
export function getSymbolScalpPolicy(symbol,market=null){const s=canonicalInstrument(symbol),p=policies[s];if(p&&(!market||p.market===market))return p;const ip=getInstrumentProfile(s);if(ip&&(!market||ip.market===market))return derive(s,ip);const m=market||ip?.market||'crypto',b=V11_CONFIG.markets[m]||V11_CONFIG.markets.crypto;return Object.freeze({symbol:s,market:m,qualityFloor:b.quality,minRR:1.02,targetAtr:.50,stopAtr:.44,riskAtr:.75,horizonMin:35,entryDriftMaxPct:{crypto:.25,forex:.12,metal:.16,index:.16}[m]||.15,aiMinConfidence:54,minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:[],entryRouter:'ROUTER',regimePrior:'GENERIC',exitStyle:'MICRO_SCALP_ATR_STRUCTURE',hardBlocks:[]});}
