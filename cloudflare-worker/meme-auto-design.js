export const MEME_AUTO_VERSION="MEME-AUTO-0.2.1-DESIGN";
export const MEME_AUTO_MODE="DESIGN_ONLY";

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

export const MEME_AUTO_DESIGN={
  chain:"SOLANA",
  executionEnabled:false,
  walletConnected:false,
  signingEnabled:false,
  leverage:false,
  philosophy:"CONFIRMED_MOMENTUM_NOT_BLIND_SNIPING",
  startingCapitalUsd:30,
  capital:{
    mode:"BALANCE_AWARE_CONTINUOUS_ALLOCATOR",
    autoScaleWithBalance:true,
    autoDeRiskWithDrawdown:true,
    startingBalanceUsd:30,
    minimumOperatingBalanceUsd:20,
    reserve:{minUsd:5,targetPct:15,maxPct:25},
    allocationTiers:[
      {maxEquityUsd:29.999999,targetPct:20,maxPct:23.5,maxOpenPositions:1},
      {maxEquityUsd:50,targetPct:20,maxPct:23.5,maxOpenPositions:3},
      {maxEquityUsd:99.999999,targetPct:18,maxPct:21,maxOpenPositions:3},
      {maxEquityUsd:250,targetPct:14,maxPct:18,maxOpenPositions:5},
      {maxEquityUsd:500,targetPct:11,maxPct:15,maxOpenPositions:5},
      {maxEquityUsd:1000,targetPct:8,maxPct:12,maxOpenPositions:5},
      {maxEquityUsd:Infinity,targetPct:6,maxPct:10,maxOpenPositions:5}
    ],
    minimumPositionUsd:4,
    liquidityParticipationCapPct:0.05,
    maxOpenPositionsHard:5,
    drawdownMultipliers:[
      {maxDrawdownPct:5,sizeMultiplier:1,positionCapMultiplier:1},
      {maxDrawdownPct:10,sizeMultiplier:.80,positionCapMultiplier:1},
      {maxDrawdownPct:15,sizeMultiplier:.60,positionCapMultiplier:.67},
      {maxDrawdownPct:Infinity,sizeMultiplier:.40,positionCapMultiplier:.34}
    ],
    setupSizeMultipliers:{MOMENTUM_RETEST:1,FRESH_BREAKOUT:.85,EARLY_ROTATION:.70},
    qualitySizeMultipliers:{ENTRY:.85,PREMIUM:1},
    riskRules:{neverScaleSafetyLimits:true,neverScaleSlippageCaps:true,neverScaleSecurityTolerance:true,neverForceFullAllocation:true,reduceSizeWhenLiquidityLimited:true,reduceSizeWhenDrawdown:true,scaleDownImmediatelyOnBalanceLoss:true,scaleUpOnlyFromCurrentConfirmedEquity:true},
    reserveUsd:5,
    tradableUsd:25,
    maxOpenPositions:3,
    targetPositionUsd:6,
    minPositionUsd:4,
    maxPositionUsd:7,
    maxAllocationPct:23.5,
    dca:false,
    averagingDown:false,
    martingale:false
  },
  discovery:{sources:["BIRDEYE_NEW_LISTINGS","BIRDEYE_MEME_SCREEN","DEXSCREENER_CROSSCHECK"],preferredAgeMin:5,preferredAgeMaxHours:24,blindLaunchSniping:false,requireExecutableSellRouteBeforeEntry:true},
  hardSafety:{enabled:true,rejectUnknownSellability:true,rejectFreezeRisk:true,rejectMintRisk:true,rejectCriticalSecurityFlags:true,minLiquidityUsd:30000,minLiquidityForFastBreakoutUsd:50000,maxTop10HolderPct:35,maxDevInsiderSupplyPct:8,maxBundlerSupplyPct:12,maxSniperSupplyPct:18,requireWalletLevelHolderView:true,requireHolderProfile:true,requireFreshSellQuote:true},
  qualityScore:{hardGateBeforeScore:true,weights:{safety:30,holders:20,liquidity:15,flow:20,momentum:15},watchScore:78,entryScore:85,premiumScore:92,maxScore:100,learningBounds:{minEntryScore:82,maxEntryScore:92,minClosedSamples:20,fullWeightSamples:100}},
  holderIntelligence:{useWalletDistribution:true,labels:["bundler","sniper","insider","dev","smart_trader"],penalizeConcentration:true,penalizeCoordinatedEarlyBuying:true,rewardHealthyHolderGrowth:true,rewardSmartTraderParticipationOnlyWhenNotConcentrated:true},
  flow:{useUniqueBuyers:true,useBuySellCounts:true,useNetBuyVolume:true,useVolumeAcceleration:true,useHolderAcceleration:true,useInsiderSelling:true,useBundlerDominance:true,washLikeConcentrationPenalty:true,requireBuyerBreadth:true},
  regimes:["EARLY_DISCOVERY","MOMENTUM_BUILD","BREAKOUT_EXPANSION","HEALTHY_PULLBACK","EUPHORIA","DISTRIBUTION","LIQUIDITY_DECAY"],
  allowedEntryRegimes:["MOMENTUM_BUILD","BREAKOUT_EXPANSION","HEALTHY_PULLBACK"],
  blockedEntryRegimes:["EUPHORIA","DISTRIBUTION","LIQUIDITY_DECAY"],
  setups:{MOMENTUM_RETEST:{priority:1,sizeMultiplier:1},FRESH_BREAKOUT:{priority:2,sizeMultiplier:.85,requirePremiumFlow:true},EARLY_ROTATION:{priority:3,sizeMultiplier:.70,requireHighSafety:true}},
  executionDesign:{futureRouter:"JUPITER",freshQuoteRequired:true,freshSellQuoteBeforeBuy:true,maxQuoteAgeMs:2500,targetMaxPriceImpactPct:1.5,hardMaxPriceImpactPct:3,targetSlippagePct:1,hardMaxSlippagePct:4,noChaseAfterQuoteDriftPct:2.5,confirmationRequired:true},
  exits:{initialCutPctRange:[8,12],hardLossPct:16,tp1:{gainPct:18,sellPct:25},tp2:{gainPct:35,sellPct:25},principalRecovery:true,runner:true,volatilityTrailing:true,smartCutSignals:["MOMENTUM_COLLAPSE","BUYER_SELLER_FLIP","HOLDER_GROWTH_STALL","DEV_INSIDER_SELLING","BREAKOUT_FAILURE","DISTRIBUTION_FLOW"],emergencyExitSignals:["SELL_ROUTE_LOST","LIQUIDITY_SHOCK","SECURITY_STATE_DETERIORATION","DEV_DUMP","EXTREME_EXIT_PRICE_IMPACT"]},
  learning:{enabledDesign:true,autoPromote:false,keys:["TOKEN","LAUNCH_SOURCE","AGE_BUCKET","REGIME","SETUP","LIQUIDITY_BUCKET","EQUITY_BUCKET","DRAWDOWN_BUCKET"],metrics:["NET_PNL","NET_R","MFE","MAE","HOLD_SEC","ENTRY_IMPACT","EXIT_IMPACT","FEES","EXIT_REASON","EQUITY_AT_ENTRY","POSITION_PCT"],mayAdjust:["ENTRY_SCORE_WITHIN_BOUNDS","SETUP_PRIORITY","SIZE_MULTIPLIER_WITHIN_BOUNDS","EXIT_PROFILE"],mayNeverAdjust:["HARD_SAFETY","WALLET_AUTHORITY","MAX_ALLOCATION_CAPS","EMERGENCY_EXIT","NO_MARTINGALE","DRAWDOWN_DERISK"]},
  ai:{requiredForExecution:false,allowedRole:"OPTIONAL_NARRATIVE_REVIEW_ONLY",mayOverrideSafety:false,maySignTransactions:false}
};

function allocationTier(equity){return MEME_AUTO_DESIGN.capital.allocationTiers.find(x=>equity<=x.maxEquityUsd)||MEME_AUTO_DESIGN.capital.allocationTiers.at(-1);}
function drawdownTier(dd){return MEME_AUTO_DESIGN.capital.drawdownMultipliers.find(x=>dd<=x.maxDrawdownPct)||MEME_AUTO_DESIGN.capital.drawdownMultipliers.at(-1);}

export function computeMemeCapitalPlan({equityUsd=30,peakEquityUsd=equityUsd,availableUsd=equityUsd,liquidityUsd=null,setup="MOMENTUM_RETEST",qualityScore=85}={}){
  const c=MEME_AUTO_DESIGN.capital,equity=Math.max(0,Number(equityUsd)||0),peak=Math.max(equity,Number(peakEquityUsd)||equity),available=Math.max(0,Number(availableUsd)||0);
  if(equity<c.minimumOperatingBalanceUsd)return {ok:false,reason:"BELOW_MINIMUM_OPERATING_BALANCE",equityUsd:equity};
  const reserveUsd=Math.max(c.reserve.minUsd,equity*c.reserve.targetPct/100),reservePct=equity>0?reserveUsd/equity*100:100,usableUsd=Math.max(0,Math.min(available,equity-reserveUsd));
  if(usableUsd<c.minimumPositionUsd)return {ok:false,reason:"INSUFFICIENT_USABLE_BALANCE_AFTER_RESERVE",equityUsd:equity,reserveUsd,usableUsd};
  const drawdownPct=peak>0?Math.max(0,(peak-equity)/peak*100):0,tier=allocationTier(equity),dd=drawdownTier(drawdownPct);
  const setupMultiplier=c.setupSizeMultipliers[setup]??.70,qualityMultiplier=qualityScore>=MEME_AUTO_DESIGN.qualityScore.premiumScore?c.qualitySizeMultipliers.PREMIUM:c.qualitySizeMultipliers.ENTRY;
  const targetByEquity=equity*tier.targetPct/100,maxByEquity=equity*tier.maxPct/100;
  const liquidityCap=Number.isFinite(Number(liquidityUsd))&&Number(liquidityUsd)>0?Number(liquidityUsd)*c.liquidityParticipationCapPct/100:Infinity;
  const rawTarget=targetByEquity*dd.sizeMultiplier*setupMultiplier*qualityMultiplier;
  const positionUsd=Math.min(rawTarget,maxByEquity*dd.sizeMultiplier,usableUsd,liquidityCap);
  const maxOpenPositions=Math.max(1,Math.min(c.maxOpenPositionsHard,Math.floor(tier.maxOpenPositions*dd.positionCapMultiplier)||1));
  if(positionUsd<c.minimumPositionUsd)return {ok:false,reason:"POSITION_BELOW_MINIMUM_AFTER_CAPS",equityUsd:equity,reserveUsd,usableUsd,drawdownPct,liquidityCapUsd:Number.isFinite(liquidityCap)?liquidityCap:null};
  return {ok:true,mode:c.mode,equityUsd:equity,peakEquityUsd:peak,drawdownPct,reserveUsd,reservePct,usableUsd,targetAllocationPct:tier.targetPct,maxAllocationPct:tier.maxPct,positionUsd,maxOpenPositions,setup,setupMultiplier,qualityMultiplier,liquidityCapUsd:Number.isFinite(liquidityCap)?liquidityCap:null,balanceAutoScaled:true,drawdownDeRisked:dd.sizeMultiplier<1};
}

export function getMemeAutoDesignStatus(){return {ok:true,service:"MEME_AUTO",version:MEME_AUTO_VERSION,mode:MEME_AUTO_MODE,executionEnabled:false,walletConnected:false,signingEnabled:false,readyForWalletIntegration:false,sampleCapitalPlans:[25,30,50,100,250,500,1000].map(equityUsd=>computeMemeCapitalPlan({equityUsd,peakEquityUsd:equityUsd,availableUsd:equityUsd,qualityScore:92})),design:MEME_AUTO_DESIGN};}
