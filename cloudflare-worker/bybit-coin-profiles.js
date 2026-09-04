// Explicit per-symbol cognition for the major/liquid Bybit USDT perpetual universe.
// These profiles are NOT win probabilities. They shape sensitivity, risk, target distance,
// holding tolerance and regime preference for each coin while portfolio risk remains global.
const freeze=x=>Object.freeze(x);

export const BYBIT_TRADE_UNIVERSE=freeze([
  'BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT','SOLUSDT','TRXUSDT','DOGEUSDT','ADAUSDT','LINKUSDT',
  'AVAXUSDT','LTCUSDT','BCHUSDT','XLMUSDT','DOTUSDT','NEARUSDT','UNIUSDT','AAVEUSDT','HBARUSDT'
]);

const base={
  enabled:true,marketCapClass:'MAJOR',riskMult:.70,targetMult:1,stopMult:1,signalGain:1,
  flowThresholdMult:1,qualityThresholdMult:1,bookToleranceMult:1,leverageMult:1,
  maxSpreadBps:7,minTurnoverUsd:25_000_000,runnerMaxR:3.2,holdMult:1,
  style:'BALANCED',correlationGroup:'ALT',priority:50,allowHighVolShockNewRisk:false,
  preferredRegimes:['TREND_UP','TREND_DOWN','BREAKOUT_UP','BREAKOUT_DOWN','SQUEEZE','TRANSITION','REVERSAL','RANGE']
};
const p=(symbol,name,x)=>freeze({...base,symbol,name,...x});

export const BYBIT_COIN_PROFILES=freeze({
  BTCUSDT:p('BTCUSDT','Bitcoin',{marketCapClass:'MEGA',style:'TREND',correlationGroup:'BTC',priority:100,riskMult:1,targetMult:1.15,stopMult:1.00,signalGain:1.00,flowThresholdMult:1.00,qualityThresholdMult:.95,bookToleranceMult:1.00,leverageMult:1.00,maxSpreadBps:4,minTurnoverUsd:500_000_000,runnerMaxR:5.2,holdMult:1.30}),
  ETHUSDT:p('ETHUSDT','Ethereum',{marketCapClass:'MEGA',style:'TREND',correlationGroup:'ETH_L1',priority:96,riskMult:.95,targetMult:1.14,stopMult:1.04,signalGain:1.03,flowThresholdMult:.96,qualityThresholdMult:.96,bookToleranceMult:1.02,leverageMult:.96,maxSpreadBps:5,minTurnoverUsd:350_000_000,runnerMaxR:4.8,holdMult:1.25}),
  BNBUSDT:p('BNBUSDT','BNB',{style:'TREND',correlationGroup:'ETH_L1',priority:90,riskMult:.82,targetMult:1.08,stopMult:.96,signalGain:.98,flowThresholdMult:1.03,qualityThresholdMult:1.00,bookToleranceMult:.98,leverageMult:.88,maxSpreadBps:6,minTurnoverUsd:80_000_000,runnerMaxR:4.0,holdMult:1.18}),
  XRPUSDT:p('XRPUSDT','XRP',{style:'BURST',correlationGroup:'PAYMENT',priority:94,riskMult:.82,targetMult:1.18,stopMult:1.10,signalGain:1.08,flowThresholdMult:.92,qualityThresholdMult:1.00,bookToleranceMult:1.08,leverageMult:.90,maxSpreadBps:6,minTurnoverUsd:120_000_000,runnerMaxR:4.2,holdMult:1.12}),
  SOLUSDT:p('SOLUSDT','Solana',{style:'MOMENTUM',correlationGroup:'ETH_L1',priority:95,riskMult:.86,targetMult:1.24,stopMult:1.18,signalGain:1.08,flowThresholdMult:.92,qualityThresholdMult:.98,bookToleranceMult:1.08,leverageMult:.90,maxSpreadBps:6,minTurnoverUsd:150_000_000,runnerMaxR:4.8,holdMult:1.20}),
  TRXUSDT:p('TRXUSDT','TRON',{style:'RANGE',correlationGroup:'PAYMENT',priority:82,riskMult:.62,targetMult:.92,stopMult:.82,signalGain:.94,flowThresholdMult:1.08,qualityThresholdMult:1.04,bookToleranceMult:.96,leverageMult:.72,maxSpreadBps:7,minTurnoverUsd:35_000_000,runnerMaxR:2.7,holdMult:.92,preferredRegimes:['RANGE','SQUEEZE','TREND_UP','TREND_DOWN','BREAKOUT_UP','BREAKOUT_DOWN']}),
  DOGEUSDT:p('DOGEUSDT','Dogecoin',{style:'MOMENTUM',correlationGroup:'HIGH_BETA',priority:86,riskMult:.58,targetMult:1.20,stopMult:1.25,signalGain:1.10,flowThresholdMult:.94,qualityThresholdMult:1.08,bookToleranceMult:1.10,leverageMult:.70,maxSpreadBps:8,minTurnoverUsd:60_000_000,runnerMaxR:4.0,holdMult:1.05}),
  ADAUSDT:p('ADAUSDT','Cardano',{style:'RANGE',correlationGroup:'ETH_L1',priority:80,riskMult:.64,targetMult:1.00,stopMult:1.04,signalGain:.98,flowThresholdMult:1.02,qualityThresholdMult:1.04,bookToleranceMult:1.02,leverageMult:.74,maxSpreadBps:8,minTurnoverUsd:35_000_000,runnerMaxR:3.2,holdMult:1.00}),
  LINKUSDT:p('LINKUSDT','Chainlink',{style:'TREND',correlationGroup:'DEFI',priority:84,riskMult:.72,targetMult:1.14,stopMult:1.10,signalGain:1.03,flowThresholdMult:.98,qualityThresholdMult:1.02,bookToleranceMult:1.04,leverageMult:.80,maxSpreadBps:8,minTurnoverUsd:30_000_000,runnerMaxR:4.0,holdMult:1.12}),
  AVAXUSDT:p('AVAXUSDT','Avalanche',{style:'MOMENTUM',correlationGroup:'ETH_L1',priority:76,riskMult:.58,targetMult:1.18,stopMult:1.22,signalGain:1.06,flowThresholdMult:.95,qualityThresholdMult:1.06,bookToleranceMult:1.08,leverageMult:.68,maxSpreadBps:9,minTurnoverUsd:20_000_000,runnerMaxR:3.9,holdMult:1.05}),
  LTCUSDT:p('LTCUSDT','Litecoin',{style:'BALANCED',correlationGroup:'PAYMENT',priority:74,riskMult:.66,targetMult:1.02,stopMult:1.02,signalGain:.99,flowThresholdMult:1.00,qualityThresholdMult:1.04,bookToleranceMult:1.00,leverageMult:.76,maxSpreadBps:8,minTurnoverUsd:25_000_000,runnerMaxR:3.3,holdMult:1.04}),
  BCHUSDT:p('BCHUSDT','Bitcoin Cash',{style:'BURST',correlationGroup:'BTC',priority:72,riskMult:.62,targetMult:1.08,stopMult:1.12,signalGain:1.03,flowThresholdMult:.98,qualityThresholdMult:1.06,bookToleranceMult:1.05,leverageMult:.72,maxSpreadBps:9,minTurnoverUsd:18_000_000,runnerMaxR:3.5,holdMult:1.02}),
  XLMUSDT:p('XLMUSDT','Stellar',{style:'BURST',correlationGroup:'PAYMENT',priority:68,riskMult:.50,targetMult:1.04,stopMult:1.12,signalGain:1.04,flowThresholdMult:.98,qualityThresholdMult:1.10,bookToleranceMult:1.04,leverageMult:.62,maxSpreadBps:10,minTurnoverUsd:12_000_000,runnerMaxR:3.2,holdMult:.98}),
  DOTUSDT:p('DOTUSDT','Polkadot',{style:'BALANCED',correlationGroup:'ETH_L1',priority:66,riskMult:.54,targetMult:1.05,stopMult:1.10,signalGain:1.00,flowThresholdMult:1.00,qualityThresholdMult:1.08,bookToleranceMult:1.02,leverageMult:.64,maxSpreadBps:10,minTurnoverUsd:12_000_000,runnerMaxR:3.3,holdMult:1.02}),
  NEARUSDT:p('NEARUSDT','NEAR',{style:'MOMENTUM',correlationGroup:'ETH_L1',priority:64,riskMult:.50,targetMult:1.10,stopMult:1.18,signalGain:1.05,flowThresholdMult:.97,qualityThresholdMult:1.10,bookToleranceMult:1.06,leverageMult:.60,maxSpreadBps:10,minTurnoverUsd:12_000_000,runnerMaxR:3.5,holdMult:1.00}),
  UNIUSDT:p('UNIUSDT','Uniswap',{style:'BALANCED',correlationGroup:'DEFI',priority:62,riskMult:.50,targetMult:1.08,stopMult:1.14,signalGain:1.00,flowThresholdMult:1.01,qualityThresholdMult:1.10,bookToleranceMult:1.04,leverageMult:.60,maxSpreadBps:10,minTurnoverUsd:10_000_000,runnerMaxR:3.4,holdMult:1.00}),
  AAVEUSDT:p('AAVEUSDT','Aave',{style:'TREND',correlationGroup:'DEFI',priority:60,riskMult:.46,targetMult:1.12,stopMult:1.16,signalGain:1.01,flowThresholdMult:1.00,qualityThresholdMult:1.12,bookToleranceMult:1.04,leverageMult:.56,maxSpreadBps:10,minTurnoverUsd:10_000_000,runnerMaxR:3.6,holdMult:1.04}),
  HBARUSDT:p('HBARUSDT','Hedera',{style:'BURST',correlationGroup:'ALT',priority:58,riskMult:.44,targetMult:1.02,stopMult:1.14,signalGain:1.02,flowThresholdMult:1.00,qualityThresholdMult:1.12,bookToleranceMult:1.04,leverageMult:.54,maxSpreadBps:11,minTurnoverUsd:8_000_000,runnerMaxR:3.1,holdMult:.98})
});

export const BYBIT_PORTFOLIO_POLICY=freeze({
  authority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V1',
  maxNewEntriesPerEvent:1,
  deepScanCount:3,
  maxCorrelatedSmall:1,
  maxCorrelatedNormal:2,
  concurrentByEquity:[{equityUsd:0,max:2},{equityUsd:75,max:2},{equityUsd:150,max:3},{equityUsd:500,max:4},{equityUsd:2000,max:5}],
  noTimeGate:true,noDailyQuota:true,noMartingale:true,noAddToLoser:true,
  requireNativeProtection:true,unmanagedSymbolFailClosed:true
});

export function normalizeBybitSymbol(symbol='BTCUSDT'){
  return String(symbol||'BTCUSDT').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
}
export function coinProfileForSymbol(symbol='BTCUSDT'){
  const s=normalizeBybitSymbol(symbol);return BYBIT_COIN_PROFILES[s]||null;
}
export function isSupportedTradeSymbol(symbol){return !!coinProfileForSymbol(symbol);}
export function maxConcurrentForEquity(equityUsd=0){
  const e=Math.max(0,Number(equityUsd)||0);let n=BYBIT_PORTFOLIO_POLICY.concurrentByEquity[0].max;
  for(const x of BYBIT_PORTFOLIO_POLICY.concurrentByEquity)if(e>=x.equityUsd)n=x.max;return n;
}
export function correlationCapForEquity(equityUsd=0){return Number(equityUsd)>=150?BYBIT_PORTFOLIO_POLICY.maxCorrelatedNormal:BYBIT_PORTFOLIO_POLICY.maxCorrelatedSmall;}
