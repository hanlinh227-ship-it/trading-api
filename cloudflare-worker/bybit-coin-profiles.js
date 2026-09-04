// Explicit per-symbol cognition for the major/liquid Bybit USDT perpetual universe.
// These profiles are NOT win probabilities. They shape sensitivity, risk, target distance,
// holding tolerance and regime preference for each coin while portfolio risk remains global.
const freeze=x=>Object.freeze(x);

export const BYBIT_TRADE_UNIVERSE=freeze([
  'BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT','SOLUSDT','TRXUSDT','DOGEUSDT','ADAUSDT','LINKUSDT',
  'AVAXUSDT','LTCUSDT','BCHUSDT','XLMUSDT','DOTUSDT','NEARUSDT','UNIUSDT','AAVEUSDT','HBARUSDT'
]);

const base={
  enabled:true,marketCapClass:'MAJOR',riskMult:.70,targetMult:1.08,stopMult:1,signalGain:1,
  flowThresholdMult:1,qualityThresholdMult:1,bookToleranceMult:1,leverageMult:1,
  maxSpreadBps:7,minTurnoverUsd:25_000_000,runnerMaxR:3.8,holdMult:1.10,
  minNetProfitMult:1.00,profitGivebackMult:1.00,reverseExitEvidenceMult:1.00,
  style:'BALANCED',correlationGroup:'ALT',priority:50,allowHighVolShockNewRisk:false,
  preferredRegimes:['TREND_UP','TREND_DOWN','BREAKOUT_UP','BREAKOUT_DOWN','SQUEEZE','TRANSITION','REVERSAL','RANGE']
};
const p=(symbol,name,x)=>freeze({...base,symbol,name,...x});

export const BYBIT_COIN_PROFILES=freeze({
  BTCUSDT:p('BTCUSDT','Bitcoin',{marketCapClass:'MEGA',style:'TREND',correlationGroup:'BTC',priority:100,riskMult:1,targetMult:1.30,stopMult:1.00,signalGain:1.00,flowThresholdMult:1.00,qualityThresholdMult:.95,bookToleranceMult:1.00,leverageMult:1.00,maxSpreadBps:4,minTurnoverUsd:500_000_000,runnerMaxR:6.0,holdMult:1.50,minNetProfitMult:1.00,profitGivebackMult:1.15,reverseExitEvidenceMult:1.20}),
  ETHUSDT:p('ETHUSDT','Ethereum',{marketCapClass:'MEGA',style:'TREND',correlationGroup:'ETH_L1',priority:96,riskMult:.95,targetMult:1.28,stopMult:1.04,signalGain:1.03,flowThresholdMult:.96,qualityThresholdMult:.96,bookToleranceMult:1.02,leverageMult:.96,maxSpreadBps:5,minTurnoverUsd:350_000_000,runnerMaxR:5.7,holdMult:1.42,minNetProfitMult:1.00,profitGivebackMult:1.12,reverseExitEvidenceMult:1.16}),
  BNBUSDT:p('BNBUSDT','BNB',{style:'TREND',correlationGroup:'ETH_L1',priority:90,riskMult:.82,targetMult:1.20,stopMult:.96,signalGain:.98,flowThresholdMult:1.03,qualityThresholdMult:1.00,bookToleranceMult:.98,leverageMult:.88,maxSpreadBps:6,minTurnoverUsd:80_000_000,runnerMaxR:4.8,holdMult:1.30,minNetProfitMult:1.00,profitGivebackMult:1.08,reverseExitEvidenceMult:1.12}),
  XRPUSDT:p('XRPUSDT','XRP',{style:'BURST',correlationGroup:'PAYMENT',priority:94,riskMult:.82,targetMult:1.30,stopMult:1.10,signalGain:1.08,flowThresholdMult:.92,qualityThresholdMult:1.00,bookToleranceMult:1.08,leverageMult:.90,maxSpreadBps:6,minTurnoverUsd:120_000_000,runnerMaxR:5.0,holdMult:1.24,minNetProfitMult:1.02,profitGivebackMult:1.06,reverseExitEvidenceMult:1.10}),
  SOLUSDT:p('SOLUSDT','Solana',{style:'MOMENTUM',correlationGroup:'ETH_L1',priority:95,riskMult:.86,targetMult:1.38,stopMult:1.18,signalGain:1.08,flowThresholdMult:.92,qualityThresholdMult:.98,bookToleranceMult:1.08,leverageMult:.90,maxSpreadBps:6,minTurnoverUsd:150_000_000,runnerMaxR:5.6,holdMult:1.34,minNetProfitMult:1.02,profitGivebackMult:1.10,reverseExitEvidenceMult:1.12}),
  TRXUSDT:p('TRXUSDT','TRON',{style:'RANGE',correlationGroup:'PAYMENT',priority:82,riskMult:.62,targetMult:1.02,stopMult:.82,signalGain:.94,flowThresholdMult:1.08,qualityThresholdMult:1.04,bookToleranceMult:.96,leverageMult:.72,maxSpreadBps:7,minTurnoverUsd:35_000_000,runnerMaxR:3.2,holdMult:1.02,minNetProfitMult:1.00,profitGivebackMult:.92,reverseExitEvidenceMult:1.05,preferredRegimes:['RANGE','SQUEEZE','TREND_UP','TREND_DOWN','BREAKOUT_UP','BREAKOUT_DOWN']}),
  DOGEUSDT:p('DOGEUSDT','Dogecoin',{style:'MOMENTUM',correlationGroup:'HIGH_BETA',priority:86,riskMult:.58,targetMult:1.34,stopMult:1.25,signalGain:1.10,flowThresholdMult:.94,qualityThresholdMult:1.08,bookToleranceMult:1.10,leverageMult:.70,maxSpreadBps:8,minTurnoverUsd:60_000_000,runnerMaxR:4.8,holdMult:1.20,minNetProfitMult:1.05,profitGivebackMult:1.04,reverseExitEvidenceMult:1.08}),
  ADAUSDT:p('ADAUSDT','Cardano',{style:'RANGE',correlationGroup:'ETH_L1',priority:80,riskMult:.64,targetMult:1.10,stopMult:1.04,signalGain:.98,flowThresholdMult:1.02,qualityThresholdMult:1.04,bookToleranceMult:1.02,leverageMult:.74,maxSpreadBps:8,minTurnoverUsd:35_000_000,runnerMaxR:3.8,holdMult:1.10,minNetProfitMult:1.00,profitGivebackMult:.98,reverseExitEvidenceMult:1.06}),
  LINKUSDT:p('LINKUSDT','Chainlink',{style:'TREND',correlationGroup:'DEFI',priority:84,riskMult:.72,targetMult:1.28,stopMult:1.10,signalGain:1.03,flowThresholdMult:.98,qualityThresholdMult:1.02,bookToleranceMult:1.04,leverageMult:.80,maxSpreadBps:8,minTurnoverUsd:30_000_000,runnerMaxR:4.8,holdMult:1.26,minNetProfitMult:1.02,profitGivebackMult:1.08,reverseExitEvidenceMult:1.10}),
  AVAXUSDT:p('AVAXUSDT','Avalanche',{style:'MOMENTUM',correlationGroup:'ETH_L1',priority:76,riskMult:.58,targetMult:1.32,stopMult:1.22,signalGain:1.06,flowThresholdMult:.95,qualityThresholdMult:1.06,bookToleranceMult:1.08,leverageMult:.68,maxSpreadBps:9,minTurnoverUsd:20_000_000,runnerMaxR:4.6,holdMult:1.18,minNetProfitMult:1.04,profitGivebackMult:1.03,reverseExitEvidenceMult:1.08}),
  LTCUSDT:p('LTCUSDT','Litecoin',{style:'BALANCED',correlationGroup:'PAYMENT',priority:74,riskMult:.66,targetMult:1.14,stopMult:1.02,signalGain:.99,flowThresholdMult:1.00,qualityThresholdMult:1.04,bookToleranceMult:1.00,leverageMult:.76,maxSpreadBps:8,minTurnoverUsd:25_000_000,runnerMaxR:3.9,holdMult:1.14,minNetProfitMult:1.00,profitGivebackMult:1.00,reverseExitEvidenceMult:1.06}),
  BCHUSDT:p('BCHUSDT','Bitcoin Cash',{style:'BURST',correlationGroup:'BTC',priority:72,riskMult:.62,targetMult:1.22,stopMult:1.12,signalGain:1.03,flowThresholdMult:.98,qualityThresholdMult:1.06,bookToleranceMult:1.05,leverageMult:.72,maxSpreadBps:9,minTurnoverUsd:18_000_000,runnerMaxR:4.2,holdMult:1.14,minNetProfitMult:1.02,profitGivebackMult:1.02,reverseExitEvidenceMult:1.07}),
  XLMUSDT:p('XLMUSDT','Stellar',{style:'BURST',correlationGroup:'PAYMENT',priority:68,riskMult:.50,targetMult:1.16,stopMult:1.12,signalGain:1.04,flowThresholdMult:.98,qualityThresholdMult:1.10,bookToleranceMult:1.04,leverageMult:.62,maxSpreadBps:10,minTurnoverUsd:12_000_000,runnerMaxR:3.8,holdMult:1.08,minNetProfitMult:1.03,profitGivebackMult:.98,reverseExitEvidenceMult:1.06}),
  DOTUSDT:p('DOTUSDT','Polkadot',{style:'BALANCED',correlationGroup:'ETH_L1',priority:66,riskMult:.54,targetMult:1.16,stopMult:1.10,signalGain:1.00,flowThresholdMult:1.00,qualityThresholdMult:1.08,bookToleranceMult:1.02,leverageMult:.64,maxSpreadBps:10,minTurnoverUsd:12_000_000,runnerMaxR:3.9,holdMult:1.10,minNetProfitMult:1.02,profitGivebackMult:1.00,reverseExitEvidenceMult:1.06}),
  NEARUSDT:p('NEARUSDT','NEAR',{style:'MOMENTUM',correlationGroup:'ETH_L1',priority:64,riskMult:.50,targetMult:1.24,stopMult:1.18,signalGain:1.05,flowThresholdMult:.97,qualityThresholdMult:1.10,bookToleranceMult:1.06,leverageMult:.60,maxSpreadBps:10,minTurnoverUsd:12_000_000,runnerMaxR:4.2,holdMult:1.12,minNetProfitMult:1.04,profitGivebackMult:1.00,reverseExitEvidenceMult:1.07}),
  UNIUSDT:p('UNIUSDT','Uniswap',{style:'BALANCED',correlationGroup:'DEFI',priority:62,riskMult:.50,targetMult:1.20,stopMult:1.14,signalGain:1.00,flowThresholdMult:1.01,qualityThresholdMult:1.10,bookToleranceMult:1.04,leverageMult:.60,maxSpreadBps:10,minTurnoverUsd:10_000_000,runnerMaxR:4.0,holdMult:1.10,minNetProfitMult:1.03,profitGivebackMult:1.00,reverseExitEvidenceMult:1.07}),
  AAVEUSDT:p('AAVEUSDT','Aave',{style:'TREND',correlationGroup:'DEFI',priority:60,riskMult:.46,targetMult:1.26,stopMult:1.16,signalGain:1.01,flowThresholdMult:1.00,qualityThresholdMult:1.12,bookToleranceMult:1.04,leverageMult:.56,maxSpreadBps:10,minTurnoverUsd:10_000_000,runnerMaxR:4.4,holdMult:1.16,minNetProfitMult:1.04,profitGivebackMult:1.04,reverseExitEvidenceMult:1.08}),
  HBARUSDT:p('HBARUSDT','Hedera',{style:'BURST',correlationGroup:'ALT',priority:58,riskMult:.44,targetMult:1.14,stopMult:1.14,signalGain:1.02,flowThresholdMult:1.00,qualityThresholdMult:1.12,bookToleranceMult:1.04,leverageMult:.54,maxSpreadBps:11,minTurnoverUsd:8_000_000,runnerMaxR:3.6,holdMult:1.06,minNetProfitMult:1.04,profitGivebackMult:.98,reverseExitEvidenceMult:1.06})
});

export const BYBIT_PORTFOLIO_POLICY=freeze({
  authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V8_CAPITAL_INTELLIGENCE_FAST_SCALE',
  maxNewEntriesPerEvent:1,
  deepScanCount:16,promotionScanCount:0,
  protectedRiskSlotReuse:true,
  protectedSlotWeight:.20,
  protectedActiveRiskEquityPct:.05,
  physicalPositionBuffer:2,
  forcedOpportunityReplacement:false,
  maxCorrelatedSmall:1,
  maxCorrelatedNormal:2,
  concurrentByEquity:[{equityUsd:0,max:2.35},{equityUsd:50,max:2.70},{equityUsd:100,max:3.10},{equityUsd:250,max:4.00},{equityUsd:500,max:5.00},{equityUsd:1000,max:6.00},{equityUsd:2500,max:7.00},{equityUsd:5000,max:8.00}],
  noTimeGate:true,noDailyQuota:true,noMartingale:true,noAddToLoser:true,
  requireNativeProtection:true,unmanagedSymbolFailClosed:true
});

export function normalizeBybitSymbol(symbol='BTCUSDT'){
  return String(symbol||'BTCUSDT').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
}
const DYNAMIC_PROFILE_BASE=freeze({...base,marketCapClass:'DYNAMIC',riskMult:.55,targetMult:1.10,stopMult:1.06,signalGain:.96,flowThresholdMult:1.04,qualityThresholdMult:1.10,bookToleranceMult:.94,leverageMult:.82,maxSpreadBps:20.0,minTurnoverUsd:500_000,runnerMaxR:4.5,holdMult:1.08,minNetProfitMult:1.00,profitGivebackMult:.92,reverseExitEvidenceMult:1.08,style:'BALANCED',correlationGroup:'DYNAMIC_ALT',priority:35,dynamicProfile:true});
const DYNAMIC_PROFILE_CACHE=new Map();
export function isCoreTradeSymbol(symbol){return !!BYBIT_COIN_PROFILES[normalizeBybitSymbol(symbol)];}
export function coinProfileForSymbol(symbol='BTCUSDT'){
  const s=normalizeBybitSymbol(symbol),core=BYBIT_COIN_PROFILES[s];if(core)return core;
  if(!/^[A-Z0-9]{2,28}USDT$/.test(s))return null;
  const baseCoin=s.slice(0,-4);if(['USDT','USDC','USDE','DAI','FDUSD','TUSD','USDD','PYUSD'].includes(baseCoin))return null;
  if(!DYNAMIC_PROFILE_CACHE.has(s))DYNAMIC_PROFILE_CACHE.set(s,freeze({...DYNAMIC_PROFILE_BASE,symbol:s}));return DYNAMIC_PROFILE_CACHE.get(s);
}
export function isSupportedTradeSymbol(symbol){return !!coinProfileForSymbol(symbol);}
function lerp(a,b,t){return Number(a)+(Number(b)-Number(a))*Math.max(0,Math.min(1,t));}
export function maxConcurrentForEquity(equityUsd=0){
  const e=Math.max(0,Number(equityUsd)||0),rows=[...BYBIT_PORTFOLIO_POLICY.concurrentByEquity].sort((a,b)=>a.equityUsd-b.equityUsd);if(!rows.length)return 2;
  if(e<=rows[0].equityUsd)return rows[0].max;for(let i=0;i<rows.length-1;i++){const a=rows[i],b=rows[i+1];if(e>=a.equityUsd&&e<b.equityUsd)return lerp(a.max,b.max,(e-a.equityUsd)/(b.equityUsd-a.equityUsd));}const last=rows.at(-1);return Math.min(10,last.max+Math.log1p(Math.max(0,e-last.equityUsd)/Math.max(1,last.equityUsd))*1.25);
}
export function correlationCapForEquity(equityUsd=0){const e=Math.max(0,Number(equityUsd)||0);return Math.min(3,1.20+Math.log1p(e/150)*.55);}
