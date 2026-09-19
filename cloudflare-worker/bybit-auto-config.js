import {BYBIT_PORTFOLIO_POLICY} from './bybit-coin-profiles.js';
import {BYBIT_EXECUTION_SYMBOL,BYBIT_EXECUTION_UNIVERSE} from './bybit-execution-authority.js';
// Canonical BTCUSDT execution configuration. Read-only market discovery may
// remain broad elsewhere, but no non-BTC symbol is part of this execution config.
import {BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';
export {BYBIT_AUTO_VERSION};

const TOP100_EXECUTION_PORTFOLIO_POLICY=Object.freeze({...BYBIT_PORTFOLIO_POLICY,authority:'BYBIT_TOP100_MARKET_CAP_STATEFLOW_PORTFOLIO'});

export const BYBIT_AUTO_CONFIG={
  symbol:BYBIT_EXECUTION_SYMBOL,symbols:BYBIT_EXECUTION_UNIVERSE,multiAsset:true,portfolio:TOP100_EXECUTION_PORTFOLIO_POLICY,category:'linear',settleCoin:'USDT',
  strategyAuthority:'BYBIT-TOP100-STATEFLOW-3.0',
  trigger:{authority:'CLOUD_PLUS_VPC_BYBIT_WS_STATE_CHANGE',eventDriven:true,scheduledExecution:false,sessionGate:false,cooldownGate:false,timedPause:false},
  leverage:{
    min:3,max:125,authority:'EXCHANGE_CAPPED_CONTINUOUS_CAPITAL_LEVERAGE',holdConstantInsideOpenCluster:true,profitFloorAdaptive:true,profitFloorMax:125,exchangeInstrumentCapRequired:true,
    equityAdaptive:{enabled:true,steps:[
      {equityUsd:0,normal:16,strong:22,aPlus:30,max:35},
      {equityUsd:50,normal:15,strong:21,aPlus:29,max:34},
      {equityUsd:100,normal:14,strong:19,aPlus:27,max:32},
      {equityUsd:250,normal:11,strong:16,aPlus:23,max:28},
      {equityUsd:500,normal:9,strong:14,aPlus:20,max:24},
      {equityUsd:1000,normal:8,strong:12,aPlus:18,max:22},
      {equityUsd:2500,normal:7,strong:11,aPlus:16,max:20},
      {equityUsd:5000,normal:6,strong:10,aPlus:14,max:18}
    ]}
  },
  scalp:{
    authority:'SCALP_FIRST_REALISTIC_TARGET_FAST_TURNOVER_PROFIT_LOCK',
    minPlannedNetProfitUsd:.30,
    preferredRunnerNetProfitUsd:1.00,
    minPlannedNetProfitPct:.35,
    minViableNetProfitUsd:.18,
    allowFloorRelaxationForFastScalp:true,
    profitFloorLadder:[
      {equityUsd:0,minNetUsd:.25},{equityUsd:50,minNetUsd:.35},{equityUsd:75,minNetUsd:.45},
      {equityUsd:100,minNetUsd:.55},{equityUsd:150,minNetUsd:.75},{equityUsd:250,minNetUsd:1.10},
      {equityUsd:500,minNetUsd:2.00},{equityUsd:1000,minNetUsd:3.50},{equityUsd:2500,minNetUsd:8.00},
      {equityUsd:5000,minNetUsd:16.00},{equityUsd:10000,minNetUsd:32.00}
    ],
    profitFloorBufferMult:1.04,
    requireNetFloorAfterFees:true,
    profitFloorProtectAfterHit:true,
    profitFloorLockAtHit:true,
    profitFloorRetentionPct:1.00,
    profitPeakRetentionPct:.72,
    profitLockR:.45,
    trailStartR:.82,
    trailRange5Pct:.16,
    trailPricePct:.00110,
    netProfitLockBufferMult:1.12,
    positiveAntiSweep:{enabled:true,authority:'POSITIVE_AFTER_COST_WIDE_NOISE_GAP',minPreservedNetUsd:.12,minGapTicks:12,range5GapPct:.28,range15GapPct:.09,priceGapPct:.00110,minGapR:.14,spreadGapMult:3.5,delayUntilRoom:true,neverMoveToLiteralEntry:true},
    adaptiveProtection:{
      enabled:true,
      authority:'SCALP_FIRST_NATIVE_TP_SL_SINGLE_WRITER',
      probeBaseTargetR:1.25,
      confirmBaseTargetR:1.50,
      fullBaseTargetR:1.75,
      minTargetR:.75,
      maxTargetR:2.20,
      strongExtensionR:.28,
      weakCompressionR:.32,
      minTargetMoveR:.10,
      minLiveGapR:.12,
      peakGivebackActivationR:.65,
      peakGivebackR:.30,
      neverLoosenStop:true,
      combineNativeTpSlWrite:true,
      timeGate:false
    }
  },
  scan:{decisionAuthority:'EVENT_DRIVEN_TOP100_STATE_CHANGE',microstructureCollectorEventDriven:true,hardDailyTradeQuota:false,entryQuotaPerDay:null,timeGate:false,sessionGate:false,cooldownGate:false},
  aiLegion:{enabledByDefault:true,demoAuto:true,liveRequiresExplicitAck:true,liveAckEnv:'BYBIT_AI_LEGION_LIVE_ENABLED',modelMeshRequired:true,requiredDistinctWorkers:3,maxDistinctWorkers:4,authority:'ADVISORY_EVIDENCE_ONLY',mayIncreaseRisk:false,mayPlaceOrders:false,mayOverrideStateFlow:false},
  risk:{
    mode:'PROGRESSIVE_COMPOUNDING_WITH_DRAWDOWN_CONTRACTION',fullAccountAuthority:true,compoundContinuously:true,riskGrowsWithCapital:true,riskShrinksWithDrawdown:true,
    baseEntryRiskPct:.75,strongEntryRiskPct:1.00,aPlusEntryRiskPct:1.25,absoluteSingleEntryRiskPct:1.50,
    maxActiveRiskPct:6.0,temporaryAPlusActiveRiskPct:8.0,maxPortfolioMarginPct:100,maxMarginPerPositionPct:100,minFreeReservePct:0,
    addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,dailyLossLimit:false,dailyMaxProfit:false,dailyMaxLoss:false,maxDailyTrades:null,maxSameDirectionPositions:1,riskRecycleAfterProtection:true,
    timedPause:false,lossStreakTimeGate:false,
    priorRiskProtectionThresholdPct:30,
    tierUpgradeMinR:.24,
    tierUpgradeMaxRemainingRiskPct:62,
    capitalBase:{enabled:true,unrealizedProfitCreditPct:25,useLowerOfBalanceAndEquityOnDrawdown:true,continuousTimeScale:true,smoothingHalfLifeMs:900000,instantDownside:true},
    equityScale:{
      enabled:true,
      authority:'PROGRESSIVE_COMPOUNDING_FULL_CAPITAL_NO_DAILY_LIMITS',
      anchorUsd:39,
      steps:[
        {equityUsd:39,riskMult:.75,marginCapPct:100},
        {equityUsd:50,riskMult:.80,marginCapPct:100},
        {equityUsd:75,riskMult:.88,marginCapPct:100},
        {equityUsd:100,riskMult:.95,marginCapPct:100},
        {equityUsd:150,riskMult:1.00,marginCapPct:100},
        {equityUsd:250,riskMult:1.05,marginCapPct:100},
        {equityUsd:500,riskMult:1.10,marginCapPct:100},
        {equityUsd:1000,riskMult:1.16,marginCapPct:100},
        {equityUsd:2500,riskMult:1.22,marginCapPct:100},
        {equityUsd:5000,riskMult:1.28,marginCapPct:100},
        {equityUsd:10000,riskMult:1.32,marginCapPct:100},
        {equityUsd:25000,riskMult:1.35,marginCapPct:100}
      ],
      maxRiskMult:1.35,
      maxMarginCapPct:100,
      scaleUpOnRealizedCapital:true,
      unrealizedProfitCreditLimitedByCapitalBase:true,
      instantDownscaleOnEquityLoss:true
    },
    drawdownGovernor:[
      {ddPct:2,multiplier:.92},
      {ddPct:5,multiplier:.80},
      {ddPct:8,multiplier:.65},
      {ddPct:10,multiplier:.55},
      {ddPct:15,multiplier:.30},
      {ddPct:20,multiplier:0}
    ]
  },
  aiLearning:{
    enabled:true,
    authority:'POST_TRADE_EVIDENCE_CANDIDATES_ONLY',
    autoMutateLive:false,
    autoIncreaseRisk:false,
    minClosedTradesBeforeCandidate:30,
    minPerRegimeSamples:12,
    rollingWindows:[30,75,150],
    metrics:['net_expectancy_r','win_rate_context','profit_factor','max_adverse_excursion_r','max_favorable_excursion_r','slippage_bps','fee_cost_bps','stop_sweep_then_thesis_recovery','target_miss_then_reversal','ai_veto_precision'],
    boundedCandidateAdjustments:{entryThresholdPct:10,stopNoiseBufferPct:15,targetRPct:10,aiRiskReductionPct:15},
    promotionRequires:['DEMO_EVIDENCE','INDEPENDENT_CHECK','NO_RISK_CEILING_EXPANSION','ROLLBACK_SNAPSHOT'],
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
    profitableMarketExit:true,
    profitHarvestExit:true,
    profitHarvestMinEvidence:2,
    earlyHarvestMinNetUsd:.18,
    earlyHarvestMinPeakR:.42,
    earlyHarvestMinEvidence:2,
    earlyHarvestConfirmEvents:1,
    earlyHarvestGivebackR:.18,
    profitHarvestConfirmEvents:1,
    profitHarvestPeakGivebackR:.24,
    shortMomentumAloneCanExit:false,
    shortMomentumAloneCanCompressTp:false,
    profitHarvestRequiresMultiStageInvalidation:true,
    highVolShockAdverseExit:true,
    profitLockOnDeceleration:true,
    decelerationLockMinR:.38,
    decelerationPeakMinR:.55,
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
    netProfitFloorAfterFees:true,holdWhileEdgePersists:true,multiStageExitEvidence:true,perSymbolProfitFloor:true,profitFloorRetention:true,priceBasedProfitProtection:true,profitFloorAdaptiveLeverage:true,profileNormalizedQuality:true,peakNetProfitRetention:true,protectedRiskSlotReuse:true,uiReadOnlyContract:true,positiveAntiSweepLock:true,dynamicBybitScalpUniverse:false,momentumFootprint:true,continuousTimeCapitalScale:true,exchangeMaxLeverageCap:true
  },
  entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true,squeezeRelease:true,momentumEarlyRelease:true,rangeMicroReclaimScalp:true,transitionWsScalp:true,shortHorizonReversal:true,sampleQualityGuard:true,probeConfirmFull:true},
  execution:{recvWindow:10000,positionIdx:0,adaptiveOrderRouting:true,postOnlyPreferredForPassive:false,iocLimitForPassiveEdge:true,iocBufferTicks:1,marketAllowedForUrgentEdge:true,marketForUrgentMomentum:true,nativeTpAlways:true,requireFreshBook:true,requireFreshTrades:true,requirePostOrderReconciliation:true,requireProtectionConfirmation:true,reduceOnlyExits:true,noTimeGate:true,managementEveryMarketStateChange:true}
};

const n=(env,k,d)=>Number.isFinite(Number(env[k]))?Number(env[k]):d;
const on=v=>String(v||'').toLowerCase()==='true';
export function bybitAutoConfig(env={}){const c=structuredClone(BYBIT_AUTO_CONFIG);const requestedActive=n(env,'BYBIT_BTC_MAX_ACTIVE_RISK_PCT',c.risk.maxActiveRiskPct),requestedMargin=n(env,'BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT',c.risk.maxPortfolioMarginPct);c.risk.maxActiveRiskPct=Math.max(.5,Math.min(c.risk.maxActiveRiskPct,requestedActive));c.risk.maxPortfolioMarginPct=Math.max(10,Math.min(c.risk.maxPortfolioMarginPct,requestedMargin));c.risk.capitalBase.unrealizedProfitCreditPct=Math.max(0,Math.min(50,n(env,'BYBIT_BTC_UNREALIZED_SCALE_CREDIT_PCT',c.risk.capitalBase.unrealizedProfitCreditPct)));c.execution.recvWindow=Math.max(5000,Math.min(20000,Math.round(n(env,'BYBIT_RECV_WINDOW_MS',c.execution.recvWindow))));return c;}
export function bybitExecutionMode(env={}){const demo=on(env.BYBIT_AUTO_DEMO),liveRequested=on(env.BYBIT_AUTO_LIVE),liveAck=on(env.BYBIT_BTC_LIVE_ACK);if(demo&&liveRequested)return 'BLOCKED';if(demo)return 'DEMO';return liveRequested&&liveAck?'LIVE':'PAPER';}
export function bybitExecutionAllowsOrders(mode){return ['LIVE','DEMO'].includes(String(mode||'').toUpperCase());}
export function bybitCredentials(env={}){const demo=on(env.BYBIT_AUTO_DEMO);if(demo){const apiKey=env.BYBIT_DEMO_API_KEY||env.HYRO_BYBIT_API_KEY||'',apiSecret=env.BYBIT_DEMO_API_SECRET||env.HYRO_BYBIT_API_SECRET||'';return {apiKey,apiSecret,source:env.BYBIT_DEMO_API_KEY&&env.BYBIT_DEMO_API_SECRET?'BYBIT_DEMO':'HYRO_BYBIT_DEMO_FALLBACK'};}return {apiKey:env.BYBIT_AUTO_API_KEY||env.HYRO_BYBIT_LIVE_API_KEY||'',apiSecret:env.BYBIT_AUTO_API_SECRET||env.HYRO_BYBIT_LIVE_API_SECRET||'',source:env.BYBIT_AUTO_API_KEY&&env.BYBIT_AUTO_API_SECRET?'BYBIT_AUTO':'HYRO_BYBIT_LIVE_FALLBACK'};}
