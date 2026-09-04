// BYBIT-BTC-STATEFLOW-2.3 configuration.
// Single production authority: BTCUSDT linear perpetual. No hard daily trade quota.
// LIVE credentials and signed VPS transport are preserved.
import {BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';
export {BYBIT_AUTO_VERSION};

export const BYBIT_AUTO_CONFIG={
  symbol:'BTCUSDT',category:'linear',settleCoin:'USDT',
  strategyAuthority:'BTC_STATE_FIRST_STRUCTURE_EXECUTED_FLOW_NEAR_TOUCH_LIQUIDITY_DERIVATIVES',
  leverage:{min:3,normal:6,strong:8,aPlus:11,max:15},
  maxOpenPositions:1000000,maxTradesPerDay:1000000000,
  scan:{workerCycleSec:60,microstructureCollectorEventDriven:true,hardDailyTradeQuota:false,entryQuotaPerDay:null},
  risk:{
    mode:'ADAPTIVE_FULL_ACCOUNT_EQUITY_BALANCE_SCALE',fullAccountAuthority:true,
    baseEntryRiskPct:.85,strongEntryRiskPct:1.20,aPlusEntryRiskPct:1.50,absoluteSingleEntryRiskPct:1.60,
    maxActiveRiskPct:7.5,temporaryAPlusActiveRiskPct:9.5,maxPortfolioMarginPct:78,maxMarginPerPositionPct:78,minFreeReservePct:12,
    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,dailyLossCircuitPct:20,maxLossStreak:4,pauseMinutes:15,maxSameDirectionPositions:1000000,riskRecycleAfterProtection:true,
    priorRiskProtectionThresholdPct:30,
    equityScale:{enabled:true,anchorUsd:39,steps:[
      {equityUsd:39,riskMult:1.00,marginCapPct:72,leverageBonus:0},
      {equityUsd:50,riskMult:1.06,marginCapPct:74,leverageBonus:0},
      {equityUsd:75,riskMult:1.12,marginCapPct:76,leverageBonus:1},
      {equityUsd:100,riskMult:1.18,marginCapPct:78,leverageBonus:1},
      {equityUsd:150,riskMult:1.24,marginCapPct:80,leverageBonus:2},
      {equityUsd:250,riskMult:1.30,marginCapPct:82,leverageBonus:2},
      {equityUsd:500,riskMult:1.36,marginCapPct:84,leverageBonus:2}
    ],maxRiskMult:1.40,maxMarginCapPct:84},
    drawdownGovernor:[{ddPct:4,multiplier:.90},{ddPct:7,multiplier:.72},{ddPct:10,multiplier:.52},{ddPct:15,multiplier:.28},{ddPct:20,multiplier:0}]
  },
  regime:{states:['TREND_UP','TREND_DOWN','RANGE','SQUEEZE','BREAKOUT_UP','BREAKOUT_DOWN','REVERSAL','HIGH_VOL_SHOCK','TRANSITION']},
  features:{
    marketStructure:true,liquiditySweepReclaim:true,publicTrades:true,executedFlowWindows:true,
    orderBook:true,nearTouchDepthBands:true,orderFlowImbalance:true,microprice:true,liquidityFragility:true,
    liquidationFlow:true,openInterest:true,fundingRate:true,basisPremium:true,longShortRatio:true,realizedVolatility:true,
    stateFirst:true,indicatorsSupportingOnly:true
  },
  entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true},
  execution:{recvWindow:10000,cooldownSec:0,positionIdx:0,postOnlyPreferredForPassive:true,marketAllowedForUrgentEdge:true,requireFreshBook:true,requireFreshTrades:true,requirePostOrderReconciliation:true,requireProtectionConfirmation:true,reduceOnlyExits:true}
};

const n=(env,k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
const on=v=>String(v||'').toLowerCase()==='true';
export function bybitAutoConfig(env={}){const c=structuredClone(BYBIT_AUTO_CONFIG);c.leverage.max=Math.max(1,Math.min(25,Math.round(n(env,'BYBIT_AUTO_MAX_LEVERAGE',c.leverage.max))));c.risk.maxActiveRiskPct=Math.max(2,Math.min(12,n(env,'BYBIT_BTC_MAX_ACTIVE_RISK_PCT',c.risk.maxActiveRiskPct)));c.risk.maxPortfolioMarginPct=Math.max(30,Math.min(85,n(env,'BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT',c.risk.maxPortfolioMarginPct)));c.execution.recvWindow=Math.max(5000,Math.min(20000,Math.round(n(env,'BYBIT_RECV_WINDOW_MS',c.execution.recvWindow))));c.execution.cooldownSec=Math.max(0,Math.min(60,Math.round(n(env,'BYBIT_BTC_ENTRY_COOLDOWN_SEC',c.execution.cooldownSec))));return c;}
export function bybitExecutionMode(env={}){return on(env.BYBIT_AUTO_LIVE)&&on(env.BYBIT_BTC_LIVE_ACK)?'LIVE':'PAPER';}
export function bybitCredentials(env={}){const demo=on(env.BYBIT_AUTO_DEMO);if(demo)return {apiKey:env.HYRO_BYBIT_API_KEY||'',apiSecret:env.HYRO_BYBIT_API_SECRET||'',source:'HYRO_BYBIT_DEMO'};return {apiKey:env.BYBIT_AUTO_API_KEY||env.HYRO_BYBIT_LIVE_API_KEY||'',apiSecret:env.BYBIT_AUTO_API_SECRET||env.HYRO_BYBIT_LIVE_API_SECRET||'',source:env.BYBIT_AUTO_API_KEY&&env.BYBIT_AUTO_API_SECRET?'BYBIT_AUTO':'HYRO_BYBIT_LIVE_FALLBACK'};}
