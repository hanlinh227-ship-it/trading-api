// BYBIT-BTC-STATEFLOW-2.5 configuration.
// BTCUSDT linear perpetual. Pure event-driven authority: no session gate, cooldown, timed pause, cron execution or daily quota.
import {BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';
export {BYBIT_AUTO_VERSION};

export const BYBIT_AUTO_CONFIG={
  symbol:'BTCUSDT',category:'linear',settleCoin:'USDT',
  strategyAuthority:'BTC_STATE_FIRST_STRUCTURE_EXECUTED_FLOW_NEAR_TOUCH_LIQUIDITY_DERIVATIVES',
  trigger:{authority:'VPS_WS_MARKET_STATE_CHANGE',eventDriven:true,scheduledExecution:false,sessionGate:false,cooldownGate:false,timedPause:false},
  leverage:{
    min:3,max:20,
    authority:'EQUITY_TAPERED_CLUSTER_LEVERAGE',
    holdConstantInsideOpenCluster:true,
    equityAdaptive:{enabled:true,steps:[
      {equityUsd:0,normal:10,strong:13,aPlus:17,max:20},
      {equityUsd:50,normal:9,strong:12,aPlus:16,max:19},
      {equityUsd:100,normal:8,strong:11,aPlus:15,max:18},
      {equityUsd:250,normal:7,strong:10,aPlus:14,max:16},
      {equityUsd:500,normal:6,strong:9,aPlus:12,max:14},
      {equityUsd:1000,normal:5,strong:8,aPlus:11,max:13},
      {equityUsd:2500,normal:4,strong:7,aPlus:10,max:12},
      {equityUsd:5000,normal:4,strong:6,aPlus:9,max:10}
    ]}
  },
  scan:{decisionAuthority:'EVENT_DRIVEN_MARKET_STATE_CHANGE',microstructureCollectorEventDriven:true,hardDailyTradeQuota:false,entryQuotaPerDay:null,timeGate:false,sessionGate:false,cooldownGate:false},
  risk:{
    mode:'ADAPTIVE_FULL_ACCOUNT_BALANCE_EQUITY_SCALE',fullAccountAuthority:true,
    baseEntryRiskPct:.85,strongEntryRiskPct:1.20,aPlusEntryRiskPct:1.50,absoluteSingleEntryRiskPct:1.60,
    maxActiveRiskPct:7.5,temporaryAPlusActiveRiskPct:9.5,maxPortfolioMarginPct:78,maxMarginPerPositionPct:78,minFreeReservePct:12,
    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,maxSameDirectionPositions:1000000,riskRecycleAfterProtection:true,
    timedPause:false,lossStreakTimeGate:false,
    priorRiskProtectionThresholdPct:30,
    capitalBase:{enabled:true,unrealizedProfitCreditPct:25,useLowerOfBalanceAndEquityOnDrawdown:true},
    equityScale:{enabled:true,anchorUsd:39,steps:[
      {equityUsd:39,riskMult:1.00,marginCapPct:72},
      {equityUsd:50,riskMult:1.06,marginCapPct:74},
      {equityUsd:75,riskMult:1.12,marginCapPct:76},
      {equityUsd:100,riskMult:1.18,marginCapPct:78},
      {equityUsd:150,riskMult:1.24,marginCapPct:80},
      {equityUsd:250,riskMult:1.30,marginCapPct:82},
      {equityUsd:500,riskMult:1.36,marginCapPct:84}
    ],maxRiskMult:1.40,maxMarginCapPct:84},
    drawdownGovernor:[{ddPct:4,multiplier:.90},{ddPct:7,multiplier:.72},{ddPct:10,multiplier:.52},{ddPct:15,multiplier:.28},{ddPct:20,multiplier:0}]
  },
  positionControl:{
    authority:'STRUCTURE_FLOW_STABILITY_EXIT_FRESH_THESIS_REENTRY',
    instabilityExit:true,
    hardInvalidationScore:.42,
    softInvalidationScore:.22,
    softConfirmEvents:2,
    highVolShockAdverseExit:true,
    freshThesisReentry:true,
    recoveryMartingale:false,
    recoveryAddToLoser:false
  },
  regime:{states:['TREND_UP','TREND_DOWN','RANGE','SQUEEZE','BREAKOUT_UP','BREAKOUT_DOWN','REVERSAL','HIGH_VOL_SHOCK','TRANSITION']},
  features:{
    marketStructure:true,liquiditySweepReclaim:true,publicTrades:true,executedFlowWindows:true,
    orderBook:true,nearTouchDepthBands:true,orderFlowImbalance:true,microprice:true,liquidityFragility:true,
    liquidationFlow:true,openInterest:true,fundingRate:true,basisPremium:true,longShortRatio:true,realizedVolatility:true,
    stateFirst:true,indicatorsSupportingOnly:true,eventDrivenDecision:true,openPositionManagementAlwaysOn:true
  },
  entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true,squeezeRelease:true,momentumEarlyRelease:true},
  execution:{recvWindow:10000,positionIdx:0,postOnlyPreferredForPassive:true,marketAllowedForUrgentEdge:true,requireFreshBook:true,requireFreshTrades:true,requirePostOrderReconciliation:true,requireProtectionConfirmation:true,reduceOnlyExits:true,noTimeGate:true,managementEveryMarketStateChange:true}
};

const n=(env,k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
const on=v=>String(v||'').toLowerCase()==='true';
export function bybitAutoConfig(env={}){const c=structuredClone(BYBIT_AUTO_CONFIG);c.risk.maxActiveRiskPct=Math.max(2,Math.min(12,n(env,'BYBIT_BTC_MAX_ACTIVE_RISK_PCT',c.risk.maxActiveRiskPct)));c.risk.maxPortfolioMarginPct=Math.max(30,Math.min(85,n(env,'BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT',c.risk.maxPortfolioMarginPct)));c.risk.capitalBase.unrealizedProfitCreditPct=Math.max(0,Math.min(50,n(env,'BYBIT_BTC_UNREALIZED_SCALE_CREDIT_PCT',c.risk.capitalBase.unrealizedProfitCreditPct)));c.execution.recvWindow=Math.max(5000,Math.min(20000,Math.round(n(env,'BYBIT_RECV_WINDOW_MS',c.execution.recvWindow))));return c;}
export function bybitExecutionMode(env={}){return on(env.BYBIT_AUTO_LIVE)&&on(env.BYBIT_BTC_LIVE_ACK)?'LIVE':'PAPER';}
export function bybitCredentials(env={}){const demo=on(env.BYBIT_AUTO_DEMO);if(demo)return {apiKey:env.HYRO_BYBIT_API_KEY||'',apiSecret:env.HYRO_BYBIT_API_SECRET||'',source:'HYRO_BYBIT_DEMO'};return {apiKey:env.BYBIT_AUTO_API_KEY||env.HYRO_BYBIT_LIVE_API_KEY||'',apiSecret:env.BYBIT_AUTO_API_SECRET||env.HYRO_BYBIT_LIVE_API_SECRET||'',source:env.BYBIT_AUTO_API_KEY&&env.BYBIT_AUTO_API_SECRET?'BYBIT_AUTO':'HYRO_BYBIT_LIVE_FALLBACK'};}
