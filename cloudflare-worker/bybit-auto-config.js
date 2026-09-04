import {BYBIT_TRADE_UNIVERSE,BYBIT_PORTFOLIO_POLICY} from './bybit-coin-profiles.js';
// BYBIT-MULTI-STATEFLOW-4.4.0 FINAL-CORE-FREEZE + UI-READY configuration.
// Event-driven authority: no session gate, cooldown, timed pause, cron execution or daily quota.
import {BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';
export {BYBIT_AUTO_VERSION};

export const BYBIT_AUTO_CONFIG={
  symbol:'BTCUSDT',symbols:BYBIT_TRADE_UNIVERSE,multiAsset:true,portfolio:BYBIT_PORTFOLIO_POLICY,category:'linear',settleCoin:'USDT',
  strategyAuthority:'STATE_FIRST_ULTRAFAST_FLOW_STRUCTURE_LIQUIDITY_DERIVATIVES_PER_SYMBOL',
  trigger:{authority:'VPS_WS_MARKET_STATE_CHANGE',eventDriven:true,scheduledExecution:false,sessionGate:false,cooldownGate:false,timedPause:false},
  leverage:{
    min:3,max:125,authority:'EXCHANGE_CAPPED_CONTINUOUS_CAPITAL_LEVERAGE',holdConstantInsideOpenCluster:true,profitFloorAdaptive:true,profitFloorMax:125,exchangeInstrumentCapRequired:true,
    equityAdaptive:{enabled:true,steps:[
      {equityUsd:0,normal:11,strong:14,aPlus:18,max:20},
      {equityUsd:50,normal:10,strong:13,aPlus:17,max:20},
      {equityUsd:100,normal:9,strong:12,aPlus:16,max:18},
      {equityUsd:250,normal:7.5,strong:10.5,aPlus:14,max:16},
      {equityUsd:500,normal:6.5,strong:9.5,aPlus:12.5,max:14},
      {equityUsd:1000,normal:5.5,strong:8.5,aPlus:11.5,max:13},
      {equityUsd:2500,normal:4.5,strong:7.5,aPlus:10,max:12},
      {equityUsd:5000,normal:4,strong:6.5,aPlus:9,max:10}
    ]}
  },
  scalp:{
    authority:'OBJECTIVE_PROFIT_FLOOR_EDGE_PERSISTENCE_FLOOR_LOCK',
    // Hard entry floor is >$1 net at low scale. Larger profits come from runners, not by starving valid entries.
    minPlannedNetProfitUsd:1.05,
    minPlannedNetProfitPct:.35,
    profitFloorLadder:[
      {equityUsd:0,minNetUsd:1.05},{equityUsd:50,minNetUsd:1.25},{equityUsd:75,minNetUsd:1.50},
      {equityUsd:100,minNetUsd:1.80},{equityUsd:150,minNetUsd:2.30},{equityUsd:250,minNetUsd:3.25},
      {equityUsd:500,minNetUsd:5.50},{equityUsd:1000,minNetUsd:10.00},{equityUsd:2500,minNetUsd:22.00},
      {equityUsd:5000,minNetUsd:45.00},{equityUsd:10000,minNetUsd:80.00}
    ],
    profitFloorBufferMult:1.04,
    requireNetFloorAfterFees:true,
    profitFloorProtectAfterHit:true,
    profitFloorLockAtHit:true,
    profitFloorRetentionPct:1.00,
    profitPeakRetentionPct:.68,
    profitLockR:.72,
    trailStartR:1.55,
    trailRange5Pct:.22,
    trailPricePct:.00170,
    netProfitLockBufferMult:1.12,
    positiveAntiSweep:{enabled:true,authority:'POSITIVE_AFTER_COST_WIDE_NOISE_GAP',minPreservedNetUsd:.12,minGapTicks:12,range5GapPct:.28,range15GapPct:.09,priceGapPct:.00110,minGapR:.14,spreadGapMult:3.5,delayUntilRoom:true,neverMoveToLiteralEntry:true},
    adaptiveProtection:{
      enabled:true,
      authority:'EDGE_PERSISTENCE_NATIVE_TP_SL_SINGLE_WRITER',
      probeBaseTargetR:2.35,
      confirmBaseTargetR:2.85,
      fullBaseTargetR:3.40,
      minTargetR:1.85,
      maxTargetR:6.00,
      strongExtensionR:.95,
      weakCompressionR:.08,
      minTargetMoveR:.22,
      minLiveGapR:.30,
      peakGivebackActivationR:1.45,
      peakGivebackR:.82,
      neverLoosenStop:true,
      combineNativeTpSlWrite:true,
      timeGate:false
    }
  },
  scan:{decisionAuthority:'EVENT_DRIVEN_MARKET_STATE_CHANGE',microstructureCollectorEventDriven:true,hardDailyTradeQuota:false,entryQuotaPerDay:null,timeGate:false,sessionGate:false,cooldownGate:false},
  risk:{
    mode:'ADAPTIVE_FULL_ACCOUNT_BALANCE_EQUITY_SCALE',fullAccountAuthority:true,
    baseEntryRiskPct:1.05,strongEntryRiskPct:1.35,aPlusEntryRiskPct:1.60,absoluteSingleEntryRiskPct:1.60,
    maxActiveRiskPct:7.5,temporaryAPlusActiveRiskPct:9.5,maxPortfolioMarginPct:78,maxMarginPerPositionPct:78,minFreeReservePct:12,
    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,maxSameDirectionPositions:3,riskRecycleAfterProtection:true,
    timedPause:false,lossStreakTimeGate:false,
    priorRiskProtectionThresholdPct:30,
    tierUpgradeMinR:.24,
    tierUpgradeMaxRemainingRiskPct:62,
    capitalBase:{enabled:true,unrealizedProfitCreditPct:25,useLowerOfBalanceAndEquityOnDrawdown:true,continuousTimeScale:true,smoothingHalfLifeMs:900000,instantDownside:true},
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
    authority:'MULTI_STAGE_THESIS_INVALIDATION_HOLD_WINNERS',
    instabilityExit:true,
    hardInvalidationScore:.56,
    softInvalidationScore:.30,
    hardConfirmEvents:3,
    softConfirmEvents:5,
    minExitEvidence:3,
    hardAdverseRForCut:.26,
    softAdverseRForCut:.48,
    profitableMarketExit:false,
    profitHarvestExit:true,
    profitHarvestMinEvidence:4,
    profitHarvestConfirmEvents:4,
    profitHarvestPeakGivebackR:.70,
    shortMomentumAloneCanExit:false,
    shortMomentumAloneCanCompressTp:false,
    profitHarvestRequiresMultiStageInvalidation:true,
    highVolShockAdverseExit:true,
    profitLockOnDeceleration:true,
    decelerationLockMinR:1.05,
    decelerationPeakMinR:1.40,
    freshThesisReentry:true,
    recoveryMartingale:false,
    recoveryAddToLoser:false
  },
  regime:{states:['TREND_UP','TREND_DOWN','RANGE','SQUEEZE','BREAKOUT_UP','BREAKOUT_DOWN','REVERSAL','HIGH_VOL_SHOCK','TRANSITION']},
  features:{
    marketStructure:true,liquiditySweepReclaim:true,publicTrades:true,executedFlowWindows:true,
    ultraFastFlow1s3s:true,marketPulseConsensus:true,orderBook:true,nearTouchDepthBands:true,orderFlowImbalance:true,microprice:true,liquidityFragility:true,
    liquidationFlow:true,openInterest:true,fundingRate:true,basisPremium:true,longShortRatio:true,realizedVolatility:true,
    stateFirst:true,indicatorsSupportingOnly:true,eventDrivenDecision:true,openPositionManagementAlwaysOn:true,
    shortHorizonFlowReversal:true,sampleQualityWeighted:true,tieredEntryRisk:true,adaptiveNativeTpSl:true,multiAssetUniverse:true,perSymbolCognition:true,portfolioCorrelationGuard:true,peakGivebackProtection:true,profitScaleLadder:true,thesisAwareProfitHarvest:true,
    netProfitFloorAfterFees:true,holdWhileEdgePersists:true,multiStageExitEvidence:true,perSymbolProfitFloor:true,profitFloorRetention:true,priceBasedProfitProtection:true,profitFloorAdaptiveLeverage:true,profileNormalizedQuality:true,peakNetProfitRetention:true,protectedRiskSlotReuse:true,uiReadOnlyContract:true,positiveAntiSweepLock:true,dynamicBybitScalpUniverse:true,momentumFootprint:true,continuousTimeCapitalScale:true,exchangeMaxLeverageCap:true
  },
  entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true,squeezeRelease:true,momentumEarlyRelease:true,rangeMicroReclaimScalp:true,transitionWsScalp:true,shortHorizonReversal:true,sampleQualityGuard:true,probeConfirmFull:true},
  execution:{recvWindow:10000,positionIdx:0,adaptiveOrderRouting:true,postOnlyPreferredForPassive:false,iocLimitForPassiveEdge:true,iocBufferTicks:1,marketAllowedForUrgentEdge:true,marketForUrgentMomentum:true,nativeTpAlways:true,requireFreshBook:true,requireFreshTrades:true,requirePostOrderReconciliation:true,requireProtectionConfirmation:true,reduceOnlyExits:true,noTimeGate:true,managementEveryMarketStateChange:true}
};

const n=(env,k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
const on=v=>String(v||'').toLowerCase()==='true';
export function bybitAutoConfig(env={}){const c=structuredClone(BYBIT_AUTO_CONFIG);c.risk.maxActiveRiskPct=Math.max(2,Math.min(12,n(env,'BYBIT_BTC_MAX_ACTIVE_RISK_PCT',c.risk.maxActiveRiskPct)));c.risk.maxPortfolioMarginPct=Math.max(30,Math.min(85,n(env,'BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT',c.risk.maxPortfolioMarginPct)));c.risk.capitalBase.unrealizedProfitCreditPct=Math.max(0,Math.min(50,n(env,'BYBIT_BTC_UNREALIZED_SCALE_CREDIT_PCT',c.risk.capitalBase.unrealizedProfitCreditPct)));c.execution.recvWindow=Math.max(5000,Math.min(20000,Math.round(n(env,'BYBIT_RECV_WINDOW_MS',c.execution.recvWindow))));return c;}
export function bybitExecutionMode(env={}){return on(env.BYBIT_AUTO_LIVE)&&on(env.BYBIT_BTC_LIVE_ACK)?'LIVE':'PAPER';}
export function bybitCredentials(env={}){const demo=on(env.BYBIT_AUTO_DEMO);if(demo)return {apiKey:env.HYRO_BYBIT_API_KEY||'',apiSecret:env.HYRO_BYBIT_API_SECRET||'',source:'HYRO_BYBIT_DEMO'};return {apiKey:env.BYBIT_AUTO_API_KEY||env.HYRO_BYBIT_LIVE_API_KEY||'',apiSecret:env.BYBIT_AUTO_API_SECRET||env.HYRO_BYBIT_LIVE_API_SECRET||'',source:env.BYBIT_AUTO_API_KEY&&env.BYBIT_AUTO_API_SECRET?'BYBIT_AUTO':'HYRO_BYBIT_LIVE_FALLBACK'};}