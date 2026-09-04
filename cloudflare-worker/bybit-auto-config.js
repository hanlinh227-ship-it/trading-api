// BYBIT-BTC-HYPERSCALE-2.0 migration config.
// Legacy multi-coin strategy configuration is retired. API credentials and transport remain reusable.
import {BYBIT_AUTO_VERSION} from "./bybit-runtime-contract.js";
export {BYBIT_AUTO_VERSION};

export const BYBIT_AUTO_CONFIG={
  symbol:"BTCUSDT",
  category:"linear",
  settleCoin:"USDT",
  strategyAuthority:"BTC_MARKET_STRUCTURE_ORDERFLOW_DERIVATIVES_MICROSTRUCTURE",
  leverage:{min:3,normal:5,max:15},
  maxOpenPositions:1000000,
  maxTradesPerDay:1000000000,
  // Current migration runtime evaluates fresh REST snapshots once per scheduler cycle.
  // WebSocket/event-driven execution is a later research/deployment stage and is not claimed active here.
  scan:{barContextSec:60,eventDriven:false,hardDailyTradeQuota:false},
  risk:{
    mode:"CONTINUOUS_EQUITY_RISK_RECYCLING",
    baseEntryRiskPct:.75,strongEntryRiskPct:1.0,aPlusEntryRiskPct:1.25,absoluteSingleEntryRiskPct:1.50,
    maxActiveRiskPct:6.0,temporaryAPlusActiveRiskPct:8.0,maxPortfolioMarginPct:65,maxMarginPerPositionPct:65,minFreeReservePct:25,
    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,dailyLossCircuitPct:20,maxLossStreak:4,pauseMinutes:15,maxSameDirectionPositions:1000000,riskRecycleAfterProtection:true,
    drawdownGovernor:[{ddPct:5,multiplier:.80},{ddPct:10,multiplier:.55},{ddPct:15,multiplier:.30},{ddPct:20,multiplier:0}]
  },
  regime:{states:["TREND_UP","TREND_DOWN","RANGE","SQUEEZE","BREAKOUT_UP","BREAKOUT_DOWN","REVERSAL","HIGH_VOL_SHOCK","TRANSITION"]},
  features:{marketStructure:true,liquidityMap:true,publicTrades:true,orderBook:true,orderFlowImbalance:true,microprice:true,liquidationFlow:false,openInterest:true,fundingRate:true,basis:true,longShortRatio:true,realizedVolatility:true,indicatorsSupportingOnly:true},
  entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:false,absorptionReversal:true},
  execution:{recvWindow:10000,cooldownSec:0,positionIdx:0,postOnlyPreferredForPassive:true,marketAllowedForUrgentEdge:true,requireFreshBook:true,requirePostOrderReconciliation:true,requireProtectionConfirmation:true,reduceOnlyExits:true}
};

const n=(env,k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
const on=v=>String(v||"").toLowerCase()==="true";
export function bybitAutoConfig(env={}){const c=structuredClone(BYBIT_AUTO_CONFIG);c.leverage.max=Math.max(1,Math.min(25,Math.round(n(env,"BYBIT_AUTO_MAX_LEVERAGE",c.leverage.max))));c.risk.maxActiveRiskPct=Math.max(2,Math.min(10,n(env,"BYBIT_BTC_MAX_ACTIVE_RISK_PCT",c.risk.maxActiveRiskPct)));c.risk.maxPortfolioMarginPct=Math.max(30,Math.min(75,n(env,"BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT",c.risk.maxPortfolioMarginPct)));c.execution.recvWindow=Math.max(5000,Math.min(20000,Math.round(n(env,"BYBIT_RECV_WINDOW_MS",c.execution.recvWindow))));c.execution.cooldownSec=Math.max(0,Math.min(60,Math.round(n(env,"BYBIT_BTC_ENTRY_COOLDOWN_SEC",c.execution.cooldownSec))));return c;}
export function bybitExecutionMode(env={}){return on(env.BYBIT_AUTO_LIVE)&&on(env.BYBIT_BTC_LIVE_ACK)?"LIVE":"PAPER";}
export function bybitCredentials(env={}){const demo=on(env.BYBIT_AUTO_DEMO);if(demo)return {apiKey:env.HYRO_BYBIT_API_KEY||"",apiSecret:env.HYRO_BYBIT_API_SECRET||"",source:"HYRO_BYBIT_DEMO"};return {apiKey:env.BYBIT_AUTO_API_KEY||env.HYRO_BYBIT_LIVE_API_KEY||"",apiSecret:env.BYBIT_AUTO_API_SECRET||env.HYRO_BYBIT_LIVE_API_SECRET||"",source:env.BYBIT_AUTO_API_KEY&&env.BYBIT_AUTO_API_SECRET?"BYBIT_AUTO":"HYRO_BYBIT_LIVE_FALLBACK"};}
