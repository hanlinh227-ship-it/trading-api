import {INSTRUMENT_PROFILES,canonicalInstrument,getInstrumentProfile} from './instrument-profiles.js';
import {V11_CONFIG} from './config.js';
import {getV11BacktestProfile,V11_BACKTEST_META} from './generated-backtest-profiles.js';

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const has=(p,needle)=>(p?.families||[]).some(x=>String(x).toUpperCase().includes(needle));
const majorFx=new Set(['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD']);
const coreCrypto=new Set(['BTC','ETH','SOL','XRP']);
const fastCrypto=new Set(['HYPE','SUI','INJ','TAO','WIF','BONK','PEPE','FLOKI','POPCAT','PENGU','TRUMP','FARTCOIN','PUMP','MOODENG','PNUT']);
const slowCrypto=new Set(['TRX','LTC','BCH','ETC','XLM']);

// Baseline V77/V78-style policy. Four-month symbol backtests may override only
// execution geometry / setup preference after that symbol independently passes.
function derive(symbol,p){
 const m=p.market,b=V11_CONFIG.markets[m],riskPrior=Number(p.riskAtrPrior||.75),reg=String(p.regimePrior||'GENERIC').toUpperCase();
 let q=b.quality,rr=1.12,target=1.35,stop=Math.max(.85,clamp(riskPrior,.60,1.20)),h=b.horizonMin,drift={crypto:.45,forex:.18,metal:.22,index:.22}[m]||.20,ai=52;
 if(reg==='TREND'){q-=2;target+=.12;stop+=.05;ai-=1;}else if(reg==='RELATIVE'){q-=1;target+=.08;}else if(reg==='MEAN_REVERSION'){rr=1.08;target-=.10;stop-=.05;}else q+=1;
 if(m==='forex'){
  if(majorFx.has(symbol)){q-=2;rr=1.10;target=1.30;stop=.90;drift=.16;h=80;}
  else {q-=1;rr=1.08;target=1.45;stop=1.00;drift=.20;h=90;}
  if(symbol.endsWith('JPY')){target+=.10;stop+=.08;drift+=.02;}
  if(p.entryRouter==='PB'){q-=1;rr=1.05;}
 }
 if(m==='crypto'){
  rr=1.12;target=1.45;stop=.95;drift=.45;h=75;
  if(coreCrypto.has(symbol)){q-=2;rr=1.10;target=1.35;stop=.88;drift=.30;h=75;ai=50;}
  if(fastCrypto.has(symbol)){q-=1;rr=1.08;target=1.70;stop=1.10;drift=.55;h=65;ai=51;}
  if(slowCrypto.has(symbol)){q-=2;rr=1.08;target=1.25;stop=.82;drift=.35;h=80;}
  if(has(p,'MEME')){target+=.20;stop+=.15;drift=Math.max(drift,.55);}
  if(has(p,'BTCALIGN')||has(p,'RELATIVE'))q-=1;
 }
 if(m==='metal'){
  if(symbol==='XAUUSD'){q=54;rr=1.12;target=1.50;stop=1.00;drift=.22;h=85;ai=51;}
  if(symbol==='XAGUSD'){q=56;rr=1.10;target=1.70;stop=1.15;drift=.28;h=80;ai=52;}
 }
 if(m==='index'){
  const ov={NAS100:[53,1.12,1.50,1.00,.24,80],SPX500:[52,1.10,1.25,.85,.20,90],US30:[54,1.10,1.45,1.00,.22,90],GER40:[54,1.10,1.50,1.00,.24,90],UK100:[55,1.08,1.30,.90,.22,90],JP225:[54,1.10,1.55,1.05,.26,90]}[symbol];
  if(ov)[q,rr,target,stop,drift,h]=ov;
  ai=51;
 }
 return Object.freeze({
  symbol,market:m,qualityFloor:clamp(Math.round(q),50,60),minRR:Number(clamp(rr,1.00,1.18).toFixed(2)),targetRR:null,
  targetAtr:Number(clamp(target,1.10,2.00).toFixed(2)),stopAtr:Number(clamp(stop,.75,1.35).toFixed(2)),
  riskAtr:Number(clamp(riskPrior,.35,1.35).toFixed(2)),horizonMin:Math.round(clamp(h,60,120)),
  entryDriftMaxPct:Number(clamp(drift,.14,.60).toFixed(2)),aiMinConfidence:Math.round(clamp(ai,50,55)),
  minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:p.families,entryRouter:p.entryRouter,regimePrior:p.regimePrior,
  backtestEligible:false,backtestFamily:null,backtestSession:'ANY',backtestRequireAlignment:false,backtestMinStrength:0,
  backtestMeta:V11_BACKTEST_META,exitStyle:'V77_V78_WIDE_SCALP_STRUCTURE_ATR',hardBlocks:Object.freeze(['STALE_QUOTE','INVALID_GEOMETRY','HARD_NEWS_BLACKOUT','VOLATILITY_SHOCK','EXTREME_CHASE','PRICE_SOURCE_DIVERGENCE'])
 });
}

function calibrated(base){
 const bp=getV11BacktestProfile(base.symbol);
 if(!bp||bp.eligible!==true)return base;
 const rr=Number(bp.rr)===2?2:1,stop=Number(bp.stopAtr),h=Number(bp.horizonMin);
 const setups=[String(bp.family||'').toUpperCase(),...(base.preferredSetups||[])].filter(Boolean);
 return Object.freeze({...base,
  minRR:rr,targetRR:rr,
  stopAtr:Number.isFinite(stop)?clamp(stop,.75,1.50):base.stopAtr,
  riskAtr:Number.isFinite(stop)?Math.min(base.riskAtr,clamp(stop,.75,1.50)):base.riskAtr,
  horizonMin:Number.isFinite(h)?Math.round(clamp(h,60,180)):base.horizonMin,
  preferredSetups:Object.freeze([...new Set(setups)]),
  backtestEligible:true,backtestFamily:String(bp.family||''),backtestSession:String(bp.session||'ANY'),
  backtestRequireAlignment:bp.requireAlignment===true,backtestMinStrength:Number(bp.minStrength||0),backtestProfile:bp,
  exitStyle:'BACKTEST_LOCKED_RR_STRUCTURE_ATR'
 });
}

const policies=Object.fromEntries(Object.entries(INSTRUMENT_PROFILES).map(([s,p])=>[s,calibrated(derive(s,p))]));
export const SYMBOL_SCALP_POLICIES=Object.freeze(policies);
export function getSymbolScalpPolicy(symbol,market=null){
 const s=canonicalInstrument(symbol),p=policies[s];
 if(p&&(!market||p.market===market))return p;
 const ip=getInstrumentProfile(s);
 if(ip&&(!market||ip.market===market))return calibrated(derive(s,ip));
 const m=market||ip?.market||'crypto',b=V11_CONFIG.markets[m]||V11_CONFIG.markets.crypto;
 return Object.freeze({symbol:s,market:m,qualityFloor:b.quality,minRR:1,targetRR:null,targetAtr:1.40,stopAtr:.95,riskAtr:.75,horizonMin:80,entryDriftMaxPct:{crypto:.45,forex:.18,metal:.22,index:.22}[m]||.20,aiMinConfidence:52,minValidAi:4,minAlignedAi:3,maxHardRiskVotes:1,preferredSetups:[],entryRouter:'ROUTER',regimePrior:'GENERIC',backtestEligible:false,backtestFamily:null,backtestSession:'ANY',backtestRequireAlignment:false,backtestMinStrength:0,backtestMeta:V11_BACKTEST_META,exitStyle:'V77_V78_WIDE_SCALP_STRUCTURE_ATR',hardBlocks:[]});
}
