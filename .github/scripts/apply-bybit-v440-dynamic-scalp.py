from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
CW=ROOT/'cloudflare-worker'

def rw(path, fn):
    p=ROOT/path
    old=p.read_text(encoding='utf-8')
    new=fn(old)
    if new==old:
        raise SystemExit(f'NO_CHANGE:{path}')
    p.write_text(new,encoding='utf-8')

def rep(s,a,b,label):
    if a not in s:
        raise SystemExit(f'MISSING:{label}')
    return s.replace(a,b,1)

# 1) Configuration: exchange-capped leverage, anti-sweep positive lock, continuous capital trajectory.
def patch_cfg(s):
    s=s.replace('BYBIT-MULTI-STATEFLOW-4.3.3','BYBIT-MULTI-STATEFLOW-4.4.0')
    s=rep(s,"min:3,max:20,authority:'EQUITY_TAPERED_CLUSTER_LEVERAGE',holdConstantInsideOpenCluster:true,profitFloorAdaptive:true,profitFloorMax:20,","min:3,max:125,authority:'EXCHANGE_CAPPED_CONTINUOUS_CAPITAL_LEVERAGE',holdConstantInsideOpenCluster:true,profitFloorAdaptive:true,profitFloorMax:125,exchangeInstrumentCapRequired:true,",'cfg leverage')
    s=rep(s,"    netProfitLockBufferMult:1.12,\n    adaptiveProtection:{","    netProfitLockBufferMult:1.12,\n    positiveAntiSweep:{enabled:true,authority:'POSITIVE_AFTER_COST_WIDE_NOISE_GAP',minPreservedNetUsd:.12,minGapTicks:12,range5GapPct:.28,range15GapPct:.09,priceGapPct:.00110,minGapR:.14,spreadGapMult:3.5,delayUntilRoom:true,neverMoveToLiteralEntry:true},\n    adaptiveProtection:{",'cfg anti sweep')
    s=rep(s,"capitalBase:{enabled:true,unrealizedProfitCreditPct:25,useLowerOfBalanceAndEquityOnDrawdown:true},","capitalBase:{enabled:true,unrealizedProfitCreditPct:25,useLowerOfBalanceAndEquityOnDrawdown:true,continuousTimeScale:true,smoothingHalfLifeMs:900000,instantDownside:true},",'cfg capital time')
    s=s.replace('profitFloorAdaptiveLeverage:true,profileNormalizedQuality:true,peakNetProfitRetention:true,protectedRiskSlotReuse:true,uiReadOnlyContract:true','profitFloorAdaptiveLeverage:true,profileNormalizedQuality:true,peakNetProfitRetention:true,protectedRiskSlotReuse:true,uiReadOnlyContract:true,positiveAntiSweepLock:true,dynamicBybitScalpUniverse:true,momentumFootprint:true,continuousTimeCapitalScale:true,exchangeMaxLeverageCap:true')
    return s
rw('cloudflare-worker/bybit-auto-config.js',patch_cfg)

# 2) Profiles: core overrides + conservative dynamic profile for any active USDT linear symbol; continuous risk-slot capacity.
def patch_profiles(s):
    s=s.replace("authority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V4_PROTECTED_RISK_SLOT_REUSE'","authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V5_CONTINUOUS_RISK_SLOTS'")
    s=s.replace('physicalPositionBuffer:1,','physicalPositionBuffer:2,')
    s=s.replace("concurrentByEquity:[{equityUsd:0,max:2},{equityUsd:75,max:2},{equityUsd:150,max:3},{equityUsd:500,max:4},{equityUsd:2000,max:5}],","concurrentByEquity:[{equityUsd:0,max:2.35},{equityUsd:50,max:2.70},{equityUsd:100,max:3.10},{equityUsd:250,max:4.00},{equityUsd:500,max:5.00},{equityUsd:1000,max:6.00},{equityUsd:2500,max:7.00},{equityUsd:5000,max:8.00}],")
    old="""export function coinProfileForSymbol(symbol='BTCUSDT'){
  const s=normalizeBybitSymbol(symbol);return BYBIT_COIN_PROFILES[s]||null;
}
export function isSupportedTradeSymbol(symbol){return !!coinProfileForSymbol(symbol);}
export function maxConcurrentForEquity(equityUsd=0){
  const e=Math.max(0,Number(equityUsd)||0);let n=BYBIT_PORTFOLIO_POLICY.concurrentByEquity[0].max;
  for(const x of BYBIT_PORTFOLIO_POLICY.concurrentByEquity)if(e>=x.equityUsd)n=x.max;return n;
}
export function correlationCapForEquity(equityUsd=0){return Number(equityUsd)>=150?BYBIT_PORTFOLIO_POLICY.maxCorrelatedNormal:BYBIT_PORTFOLIO_POLICY.maxCorrelatedSmall;}
"""
    new="""const DYNAMIC_PROFILE_BASE=freeze({...base,marketCapClass:'DYNAMIC',riskMult:.55,targetMult:1.04,stopMult:1.04,signalGain:.96,flowThresholdMult:1.03,qualityThresholdMult:1.04,bookToleranceMult:.95,leverageMult:.90,maxSpreadBps:7.5,minTurnoverUsd:35_000_000,runnerMaxR:4.2,holdMult:1.05,minNetProfitMult:1.00,profitGivebackMult:.96,reverseExitEvidenceMult:1.05,style:'BALANCED',correlationGroup:'DYNAMIC_ALT',priority:42,dynamicProfile:true});
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
"""
    s=rep(s,old,new,'dynamic profiles funcs')
    return s
rw('cloudflare-worker/bybit-coin-profiles.js',patch_profiles)

# 3) Balance reconciler: time-decayed upward scale, immediate downside response.
def patch_balance(s):
    pat=r"function applySnapshot\(state,snap\)\{.*?return state;\n\}"
    new="""function applySnapshot(state,snap){
  const now=Date.now(),prevAt=Date.parse(state.lastBalanceObservedAt||'')||now,dt=Math.max(0,now-prevAt),halfLife=15*60*1000,alpha=dt<=0?1:1-Math.exp(-dt/halfLife),prevEq=num(state.smoothedEquityUsd)||snap.equityUsd,prevWallet=num(state.smoothedWalletBalanceUsd)||snap.walletBalanceUsd,smEq=prevEq+(snap.equityUsd-prevEq)*alpha,smWallet=prevWallet+(snap.walletBalanceUsd-prevWallet)*alpha,prevObserved=num(state.lastEquityUsd)||snap.equityUsd,hours=Math.max(dt/3600000,1/3600);
  state.smoothedEquityUsd=smEq;state.smoothedWalletBalanceUsd=smWallet;state.continuousCapitalUsd=Math.max(0,Math.min(snap.equityUsd,smEq,snap.walletBalanceUsd>0?Math.max(smWallet,snap.walletBalanceUsd*.75):smEq));state.equityVelocityUsdPerHour=(snap.equityUsd-prevObserved)/hours;state.continuousScaleAuthority='TIME_DECAYED_EQUITY_BALANCE_INSTANT_DOWNSIDE';
  state.lastWalletBalanceUsd=snap.walletBalanceUsd;
  state.lastEquityUsd=snap.equityUsd;
  state.lastAvailableUsd=snap.availableUsd;
  state.lastUnrealisedPnlUsd=snap.unrealisedPnlUsd;
  state.lastCumRealisedPnlUsd=snap.cumRealisedPnlUsd;
  state.lastBalanceObservedAt=new Date(now).toISOString();
  state.balanceAuthority='BYBIT_WALLET_PLUS_TRANSACTION_LOG';
  state.depositWithdrawalAware=true;
  return state;
}"""
    s,n=re.subn(pat,new,s,count=1,flags=re.S)
    if n!=1: raise SystemExit('MISSING:balance applySnapshot')
    s=s.replace("BTC_BALANCE_RECONCILER_V2_BASELINE_SAFE","BTC_BALANCE_RECONCILER_V3_CONTINUOUS_TIME_CAPITAL")
    return s
rw('cloudflare-worker/bybit-btc-balance-reconciler.js',patch_balance)

# 4) Risk engine consumes safe continuous capital (never above instantaneous admissible capital).
def patch_risk(s):
    old="const wallet=Math.max(0,num(state.lastWalletBalanceUsd)||equity),capital=capitalBaseState({equityUsd:equity,walletBalanceUsd:wallet,cfg});if(!(capital.capitalBaseUsd>0))return {ok:false,reason:'CAPITAL_BASE_INVALID',capital};"
    new="const wallet=Math.max(0,num(state.lastWalletBalanceUsd)||equity),rawCapital=capitalBaseState({equityUsd:equity,walletBalanceUsd:wallet,cfg}),continuous=Math.max(0,num(state.lastContinuousCapitalUsd)),capital=continuous>0?{...rawCapital,instantCapitalBaseUsd:rawCapital.capitalBaseUsd,capitalBaseUsd:Math.min(rawCapital.capitalBaseUsd,continuous),continuousTimeScale:true}:rawCapital;if(!(capital.capitalBaseUsd>0))return {ok:false,reason:'CAPITAL_BASE_INVALID',capital};"
    s=rep(s,old,new,'risk continuous capital')
    return s
rw('cloudflare-worker/bybit-btc-risk-engine.js',patch_risk)

# 5) Strategy: add footprint persistence/acceleration and spike-trap rejection while retaining freshness/cost gates.
def patch_strategy(s):
    pat=r"function signedMarketScore\(s=\{\},p=\{\}\)\{.*?\}\nfunction specializedSetup"
    new="""function momentumFootprint(s={}){const t=s.trades||{},u=s.ultraFast||{},b=s.book||{},f1=num(t.window1s?.imbalance),f3=num(t.window3s?.imbalance),f5=num(t.window5s?.imbalance),f15=num(t.window15s?.imbalance??t.aggressorImbalance),p1=clamp(num(t.window1s?.priceChangeBps)/8,-1,1),p3=clamp(num(t.window3s?.priceChangeBps)/14,-1,1),p5=clamp(num(t.window5s?.priceChangeBps)/22,-1,1),burst=clamp((num(t.burst1x)+num(t.burst3x)+num(t.burst5x)-3)/6,-1,1),acc=num(u.flowAcceleration),imp=num(u.impulseScore),press=num(u.pressureScore),book=num(b.imbalance2),micro=clamp(num(b.micropriceEdgeBps)/.30,-1,1),align=Math.sign(f15||f5||f3||f1||1),persistence=clamp(align*(.12*f1+.22*f3+.27*f5+.39*f15),-1,1),priceFollow=clamp(align*(.20*p1+.34*p3+.46*p5),-1,1),flowFollow=clamp(align*(.18*acc+.20*imp+.16*press+.12*book+.08*micro)+.26*Math.max(0,persistence),-1,1),spikeMismatch=Math.max(0,Math.abs(f1)-Math.abs(f5))*(Math.sign(f1)!==Math.sign(f15)&&Math.abs(f15)>.04?1:.35),priceMismatch=(Math.sign(p1)!==Math.sign(f15)&&Math.abs(p1)>.25&&Math.abs(f15)>.05)?Math.abs(p1):0,reversalPenalty=clamp(spikeMismatch+priceMismatch,0,1),raw=clamp(.42*persistence+.24*priceFollow+.18*flowFollow+.16*align*burst-align*reversalPenalty*.30,-1,1),confidence=clamp(.34*Math.abs(persistence)+.20*Math.max(0,priceFollow)+.20*Math.abs(flowFollow)+.16*Math.max(0,burst)+.10*(1-reversalPenalty),0,1);return {score:raw,confidence,persistence,priceFollow,flowFollow,burst,reversalPenalty,spikeTrap:reversalPenalty>.50&&confidence<.70};}
function signedMarketScore(s={},p={}){const t=s.trades||{},u=s.ultraFast||{},b=s.book||{},pulse=s.marketPulse||{},style=String(p.style||'BALANCED'),f1=num(t.window1s?.imbalance),f3=num(t.window3s?.imbalance),f5=num(t.window5s?.imbalance),f15=num(t.window15s?.imbalance??t.aggressorImbalance),f60=num(t.window60s?.imbalance),book=num(b.imbalance2),micro=clamp(num(b.micropriceEdgeBps)/.30,-1,1),pressure=num(u.pressureScore),impulse=num(u.impulseScore),acc=num(u.flowAcceleration),ps=num(pulse.score),d5=num(s.direction5),d15=num(s.direction15),d60=num(s.direction60),fp=momentumFootprint(s);let raw=0;if(style==='MOMENTUM')raw=.10*f1+.15*f3+.17*f5+.19*f15+.03*f60+.10*pressure+.10*impulse+.07*acc+.04*book+.025*micro+.025*ps;else if(style==='BURST')raw=.16*f1+.18*f3+.14*f5+.17*f15+.02*f60+.08*pressure+.10*impulse+.06*acc+.045*book+.03*micro+.025*ps;else if(style==='RANGE')raw=.05*f1+.09*f3+.15*f5+.23*f15+.03*f60+.08*pressure+.07*impulse+.10*book+.07*micro+.05*ps+.04*d5+.04*d15;else if(style==='TREND')raw=.04*f1+.08*f3+.12*f5+.23*f15+.10*f60+.07*pressure+.06*impulse+.04*acc+.05*book+.025*micro+.025*ps+.07*d15+.04*d60;else raw=.07*f1+.11*f3+.15*f5+.22*f15+.05*f60+.08*pressure+.08*impulse+.05*acc+.06*book+.03*micro+.03*ps+.04*d15+.03*d60;const footprintWeight=style==='MOMENTUM'||style==='BURST'?.38:.26;return clamp((raw*(1-footprintWeight)+fp.score*footprintWeight)*Math.max(.75,num(p.signalGain)||1),-1,1);}
function specializedSetup"""
    s,n=re.subn(pat,new,s,count=1,flags=re.S)
    if n!=1: raise SystemExit('MISSING:strategy score')
    old="function specializedSetup(s={},p={}){const q=qualityScore(s,p),score=signedMarketScore(s,p),abs=Math.abs(score),side=signSide(score),sgn=side==='Buy'?1:-1,t=s.trades||{},u=s.ultraFast||{},b=s.book||{},pulse=s.marketPulse||{},"
    new="function specializedSetup(s={},p={}){const q=qualityScore(s,p),fp=momentumFootprint(s),score=signedMarketScore(s,p),abs=Math.abs(score),side=signSide(score),sgn=side==='Buy'?1:-1,t=s.trades||{},u=s.ultraFast||{},b=s.book||{},pulse=s.marketPulse||{},"
    s=rep(s,old,new,'strategy specialized init')
    old="votes=[flow3>.045*flowMult,flow5>.055*flowMult,flow15>.045*flowMult,pressure>.035*flowMult,impulse>.04*flowMult,book>-.035*bookTol,micro>-.10*bookTol,pulseScore>.025].filter(Boolean).length,strongConsensus=abs>=threshold*1.75&&q>=qualityMin*1.10,minVotes=strongConsensus?4:5;if(q<qualityMin||abs<threshold||votes<minVotes)return {ok:false,reason:'PROFILE_EDGE_NOT_CONFIRMED',diagnostic:{q,qualityMin,score,threshold,votes,minVotes,strongConsensus,style:p.style}};"
    new="footprint=sgn*fp.score,votes=[flow3>.045*flowMult,flow5>.055*flowMult,flow15>.045*flowMult,pressure>.035*flowMult,impulse>.04*flowMult,book>-.035*bookTol,micro>-.10*bookTol,pulseScore>.025,footprint>.04&&fp.confidence>.30].filter(Boolean).length,strongConsensus=abs>=threshold*1.70&&q>=qualityMin*1.08&&footprint>-.03,minVotes=strongConsensus?4:5;if(fp.spikeTrap&&abs<threshold*2.20)return {ok:false,reason:'FOOTPRINT_SPIKE_WITHOUT_FOLLOW_THROUGH',diagnostic:{q,score,threshold,footprint,footprintConfidence:fp.confidence,reversalPenalty:fp.reversalPenalty}};if(q<qualityMin||abs<threshold||votes<minVotes)return {ok:false,reason:'PROFILE_EDGE_NOT_CONFIRMED',diagnostic:{q,qualityMin,score,threshold,votes,minVotes,strongConsensus,style:p.style,footprint,footprintConfidence:fp.confidence}};"
    s=rep(s,old,new,'strategy votes')
    s=s.replace("book,micro,pulse:pulseScore,source:s.microstructureSource}","book,micro,pulse:pulseScore,footprint,footprintConfidence:fp.confidence,footprintPersistence:fp.persistence,footprintPriceFollow:fp.priceFollow,footprintBurst:fp.burst,footprintReversalPenalty:fp.reversalPenalty,source:s.microstructureSource}")
    s=s.replace("BYBIT_SYMBOL_COGNITION_V3_FRESHNESS_ADAPTIVE_CONSENSUS","BYBIT_SYMBOL_COGNITION_V4_MOMENTUM_FOOTPRINT_DYNAMIC_SCALP")
    return s
rw('cloudflare-worker/bybit-symbol-strategy.js',patch_strategy)

# 6) Symbol engine: exchange max leverage, continuous profit floor, delayed positive anti-sweep lock.
def patch_engine(s):
    s=s.replace('BYBIT-MULTI-ASSET-ENGINE-4.3.2-FLOOR-RISK-SLOT-UI','BYBIT-MULTI-ASSET-ENGINE-4.4.0-ANTI-SWEEP-DYNAMIC-SCALP')
    s=s.replace('EQUITY_TAPERED_CLUSTER_LEVERAGE','EXCHANGE_CAPPED_CONTINUOUS_CAPITAL_LEVERAGE')
    pat=r"function leverageFor\(cfg,setup,equityUsd,ddMult=1,position=null,market=\{\}\)\{.*?\}\nfunction tighten"
    new="""function leverageFor(cfg,setup,equityUsd,ddMult=1,position=null,market={},filters={}){const exchangeMin=Math.max(1,num(filters?.minLeverage)||1),minLev=Math.max(exchangeMin,num(cfg?.leverage?.min)||3),configuredMax=Math.max(minLev,num(cfg?.leverage?.max)||125),exchangeMax=Math.max(minLev,num(filters?.maxLeverage)||configuredMax),globalMax=Math.min(configuredMax,exchangeMax),existing=num(position?.leverage);if(existing>0&&cfg?.leverage?.holdConstantInsideOpenCluster!==false)return Math.round(clamp(existing,minLev,globalMax));const p=leverageProfile(cfg,equityUsd),strength=String(setup?.strength||\"NORMAL\"),tier=String(setup?.entryTier||\"CONFIRM\"),base=strength===\"A_PLUS\"?num(p.aPlus):strength===\"STRONG\"?num(p.strong):num(p.normal);let x=Math.min(base,num(p.max)||globalMax,globalMax);x*=clamp(num(setup?.coinProfile?.leverageMult)||1,.45,1.15);if(tier==='PROBE')x=Math.min(x,Math.max(minLev,num(p.normal)));if(tier==='CONFIRM'&&strength==='A_PLUS')x=Math.min(x,Math.max(minLev,num(p.strong)));const setupName=String(setup?.setup||\"\");if(setup?.regime===\"RANGE\")x=Math.min(x,Math.max(minLev,num(p.normal)-2));if(setup?.regime===\"SQUEEZE\"&&!/(MOMENTUM|RELEASE|PROBE)/.test(setupName))x=Math.min(x,Math.max(minLev,num(p.normal)-2));if(!market?.quality?.wsFastPath)x=Math.min(x,Math.max(minLev,num(p.normal)));if(num(market?.volRatio)>1.35)x=Math.min(x,Math.max(minLev,num(p.normal)));if(ddMult<.90)x=Math.min(x,Math.max(minLev,num(p.normal)-1));if(ddMult<.75)x=Math.min(x,Math.min(globalMax,6));if(ddMult<.55)x=Math.min(x,Math.min(globalMax,4));return Math.round(clamp(x,minLev,globalMax));}
function tighten"""
    s,n=re.subn(pat,new,s,count=1,flags=re.S)
    if n!=1: raise SystemExit('MISSING:engine leverageFor')
    pat=r"function plannedProfitFloor\(cfg,capitalUsd,setup=\{\}\)\{.*?\}\nfunction expandSetupToProfitFloor"
    new="""function plannedProfitFloor(cfg,capitalUsd,setup={}){const capital=Math.max(0,num(capitalUsd)),rows=[...(cfg?.scalp?.profitFloorLadder||[])].sort((a,b)=>num(a.equityUsd)-num(b.equityUsd)),hard=Math.max(1,num(cfg?.scalp?.minPlannedNetProfitUsd)||1);let ladder=hard;if(rows.length){if(capital<=num(rows[0].equityUsd))ladder=Math.max(hard,num(rows[0].minNetUsd));else{let found=false;for(let i=0;i<rows.length-1;i++){const a=rows[i],b=rows[i+1],lo=num(a.equityUsd),hi=Math.max(lo+1e-9,num(b.equityUsd));if(capital>=lo&&capital<hi){ladder=Math.max(hard,lerp(a.minNetUsd,b.minNetUsd,(capital-lo)/(hi-lo)));found=true;break;}}if(!found){const last=rows.at(-1);ladder=Math.max(hard,num(last.minNetUsd));}}}const pct=capital*Math.max(0,num(cfg?.scalp?.minPlannedNetProfitPct)||0)/100,profileMult=clamp(num(setup?.coinProfile?.minNetProfitMult)||1,.90,1.25);return Math.max(1,ladder,pct)*profileMult;}
function expandSetupToProfitFloor"""
    s,n=re.subn(pat,new,s,count=1,flags=re.S)
    if n!=1: raise SystemExit('MISSING:engine profit floor')
    old="costBps=Math.max(11,num(latest.costBps),num(latest.costReserveUsd)>0&&num(latest.entry)*Math.abs(num(latest.qty))>0?num(latest.costReserveUsd)/(num(latest.entry)*Math.abs(num(latest.qty)))*10000:0),bufferMult=Math.max(1,num(cfg?.scalp?.netProfitLockBufferMult)||1.06),feeBuffer=Math.max(filters.tickSize*2,num(latest.entry)*costBps/10000*bufferMult),be=side===\"Buy\"?num(latest.entry)+feeBuffer:num(latest.entry)-feeBuffer,canNetLock=side===\"Buy\"?mark>be+filters.tickSize:mark<be-filters.tickSize,peakNow=Math.max(num(state.positionPeakR),r),decelerating="
    new="costBps=Math.max(11,num(latest.costBps),num(latest.costReserveUsd)>0&&num(latest.entry)*Math.abs(num(latest.qty))>0?num(latest.costReserveUsd)/(num(latest.entry)*Math.abs(num(latest.qty)))*10000:0),positionQty=Math.abs(num(position.size)||num(latest.qty)),bufferMult=Math.max(1,num(cfg?.scalp?.netProfitLockBufferMult)||1.06),anti=cfg?.scalp?.positiveAntiSweep||{},feeBuffer=Math.max(filters.tickSize*2,num(latest.entry)*costBps/10000*bufferMult),positiveNetUsd=Math.max(0,num(anti.minPreservedNetUsd)||.12),positiveDistance=feeBuffer+(positionQty>0?positiveNetUsd/positionQty:0),be=side===\"Buy\"?num(latest.entry)+positiveDistance:num(latest.entry)-positiveDistance,spreadGap=mark*Math.max(0,num(market?.book?.spreadBps))/10000*Math.max(1,num(anti.spreadGapMult)||3.5),antiSweepGap=Math.max(filters.tickSize*Math.max(6,num(anti.minGapTicks)||12),num(market.range5?.width)*Math.max(.08,num(anti.range5GapPct)||.28),num(market.range15?.width)*Math.max(.02,num(anti.range15GapPct)||.09),mark*Math.max(.00045,num(anti.priceGapPct)||.00110),d*Math.max(.08,num(anti.minGapR)||.14),spreadGap),roomStop=side===\"Buy\"?mark-antiSweepGap:mark+antiSweepGap,canNetLock=side===\"Buy\"?be<=roomStop:be>=roomStop,peakNow=Math.max(num(state.positionPeakR),r),decelerating="
    s=rep(s,old,new,'engine anti sweep base')
    s=s.replace(",positionQty=Math.abs(num(position.size)||num(latest.qty)),liveCostReserve=",",liveCostReserve=",1)
    s=s.replace("retainedGap=Math.max(filters.tickSize*5,d*.08)","retainedGap=Math.max(antiSweepGap,filters.tickSize*8,d*.10)",1)
    s=s.replace("const trailDist=Math.max(filters.tickSize*6,num(market.range5?.width)","const trailDist=Math.max(antiSweepGap,filters.tickSize*8,num(market.range5?.width)",1)
    s=s.replace("gap=Math.max(filters.tickSize*5,d*.10),raw=","gap=Math.max(antiSweepGap,filters.tickSize*8,d*.12),raw=",1)
    old="state.lastAdaptiveProtection={at:iso(),side,markPrice:mark,stopLoss:currentStop,takeProfit:currentTarget,r,peakR:state.positionPeakR,support:adaptive?.support??null"
    new="state.lastAdaptiveProtection={at:iso(),side,markPrice:mark,stopLoss:currentStop,takeProfit:currentTarget,r,peakR:state.positionPeakR,positiveLockStop:be,positiveLockReady:canNetLock,antiSweepGap,positiveNetObjectiveUsd:positiveNetUsd,antiSweepAuthority:'POSITIVE_AFTER_COST_WIDE_NOISE_GAP',support:adaptive?.support??null"
    s=rep(s,old,new,'engine anti sweep telemetry')
    old="const baseLeverage=leverageFor(cfg,setup,preRisk.capital?.capitalBaseUsd||equity,preRisk.multiplier,pos,market),maxProfitLeverage=Math.max(baseLeverage,Math.min(num(cfg?.leverage?.max)||20,num(cfg?.leverage?.profitFloorMax)||num(cfg?.leverage?.max)||20)),leverageCandidates=[baseLeverage,Math.min(maxProfitLeverage,Math.ceil(baseLeverage*1.25)),Math.min(maxProfitLeverage,baseLeverage+4),maxProfitLeverage].map(x=>Math.max(1,Math.round(x))).filter((x,i,a)=>a.indexOf(x)===i),"
    new="const baseLeverage=leverageFor(cfg,setup,preRisk.capital?.capitalBaseUsd||equity,preRisk.multiplier,pos,market,filters),exchangeMaxLeverage=Math.max(baseLeverage,num(filters.maxLeverage)||baseLeverage),maxProfitLeverage=Math.max(baseLeverage,Math.min(exchangeMaxLeverage,num(cfg?.leverage?.max)||exchangeMaxLeverage,num(cfg?.leverage?.profitFloorMax)||exchangeMaxLeverage)),leverageCandidates=[baseLeverage,Math.min(maxProfitLeverage,Math.ceil(baseLeverage*1.30)),Math.min(maxProfitLeverage,baseLeverage+5),Math.min(maxProfitLeverage,Math.ceil(maxProfitLeverage*.50)),Math.min(maxProfitLeverage,Math.ceil(maxProfitLeverage*.75)),maxProfitLeverage].map(x=>Math.max(1,Math.round(x))).sort((a,b)=>a-b).filter((x,i,a)=>a.indexOf(x)===i),"
    s=rep(s,old,new,'engine leverage candidates')
    old="lastAvailableUsd:num(portfolioContext?.availableUsd)||num(state.lastAvailableUsd),symbol:SYMBOL"
    new="lastAvailableUsd:num(portfolioContext?.availableUsd)||num(state.lastAvailableUsd),lastContinuousCapitalUsd:num(portfolioContext?.continuousCapitalUsd)||num(state.lastContinuousCapitalUsd)||equity,symbol:SYMBOL"
    s=rep(s,old,new,'engine continuous context')
    s=s.replace("BYBIT_MULTI_ASSET_ENGINE_V4_3_2_FLOOR_RISK_SLOT_UI","BYBIT_MULTI_ASSET_ENGINE_V4_4_0_ANTI_SWEEP_DYNAMIC_SCALP")
    return s
rw('cloudflare-worker/bybit-symbol-engine.js',patch_engine)

# 7) Multi-asset controller: dynamic Bybit registry + continuous capacity capital.
def patch_controller(s):
    s=rep(s,"import {bybitExecutionMode} from './bybit-auto-config.js';","import {bybitExecutionMode} from './bybit-auto-config.js';\nimport {buildBybitDynamicUniverse} from './bybit-dynamic-universe.js';",'controller import dynamic')
    s=s.replace("function portfolioContext(positions,symbol,balance={}){const others=positions.filter(x=>sym(x)!==symbol),externalActiveRiskUsd=others.reduce((s,x)=>s+positionRisk(x),0),externalMarginUsd=others.reduce((s,x)=>s+Math.max(0,num(x.positionIM)),0);return {externalActiveRiskUsd,externalMarginUsd,highWaterUsd:num(balance?.state?.highWaterUsd),walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd)};}","function portfolioContext(positions,symbol,balance={}){const others=positions.filter(x=>sym(x)!==symbol),externalActiveRiskUsd=others.reduce((s,x)=>s+positionRisk(x),0),externalMarginUsd=others.reduce((s,x)=>s+Math.max(0,num(x.positionIM)),0);return {externalActiveRiskUsd,externalMarginUsd,highWaterUsd:num(balance?.state?.highWaterUsd),walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd),continuousCapitalUsd:num(balance?.state?.continuousCapitalUsd)};}")
    s=s.replace("const row=ranked.find(x=>x.symbol===symbol);if(row&&!row.eligible)return 'UNIVERSE_LIQUIDITY_OR_SPREAD_GATE';","const row=ranked.find(x=>x.symbol===symbol);if(!row)return 'SYMBOL_NOT_IN_DYNAMIC_MARKET_UNIVERSE';if(!row.eligible)return 'DYNAMIC_UNIVERSE_WATCH_ONLY';")
    old="export async function runBybitMultiAssetControlled(env,opts={}){const mode=bybitExecutionMode(env),api=bybitV5(env),balance=await reconcileBtcAccountBalance(env),equity=num(balance?.snapshot?.equityUsd)||num(balance?.state?.lastEquityUsd);let positions=openPos(await api.positions()),ranked=rankUniverse(tickerRows(await api.tickers())),eventSymbol=normalizeBybitSymbol(opts.symbol||'BTCUSDT');"
    new="export async function runBybitMultiAssetControlled(env,opts={}){const mode=bybitExecutionMode(env),api=bybitV5(env),balance=await reconcileBtcAccountBalance(env),equity=num(balance?.snapshot?.equityUsd)||num(balance?.state?.lastEquityUsd),capacityCapital=Math.max(.01,Math.min(equity,num(balance?.state?.continuousCapitalUsd)||equity)),universeState=await buildBybitDynamicUniverse(env,api);let positions=openPos(await api.positions()),ranked=universeState.ranked,eventSymbol=normalizeBybitSymbol(opts.symbol||'BTCUSDT');"
    s=rep(s,old,new,'controller run dynamic')
    s=s.replace("entryBlockFor({symbol,positions,equity,newEntryDone:false,ranked})","entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked})")
    s=s.replace("slotWeight(x,equity)<1","slotWeight(x,capacityCapital)<1")
    s=s.replace("slotWeight(x,equity)}","slotWeight(x,capacityCapital)}")
    s=s.replace("baseMax=maxConcurrentForEquity(equity)","baseMax=maxConcurrentForEquity(capacityCapital)")
    s=s.replace("riskSlotsUsed=slotUsage(positions,equity)","riskSlotsUsed=slotUsage(positions,capacityCapital)")
    s=s.replace("positions.filter(x=>slotWeight(x,equity)<1).length","positions.filter(x=>slotWeight(x,capacityCapital)<1).length")
    s=s.replace("physicalHardCap=baseMax+Math.max(0,Math.floor(num(BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer)||0))","physicalHardCap=Math.ceil(baseMax+Math.max(0,Math.floor(num(BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer)||0)))")
    s=s.replace("universe:BYBIT_TRADE_UNIVERSE,lastEventSymbol:eventSymbol","universe:universeState.tradeSymbols,coreUniverse:BYBIT_TRADE_UNIVERSE,dynamicUniverse:universeState.summary,watchNew:universeState.watchNew.slice(0,30),watchOnly:universeState.watchOnly.slice(0,30),lastEventSymbol:eventSymbol")
    s=s.replace("equityUsd:equity,walletBalanceUsd", "equityUsd:equity,continuousCapacityCapitalUsd:capacityCapital,walletBalanceUsd")
    s=s.replace("return {ok:true,mode,multiAsset:true,eventSymbol,equity,universe:BYBIT_TRADE_UNIVERSE,ranked:","return {ok:true,mode,multiAsset:true,eventSymbol,equity,universe:universeState.tradeSymbols,universeSummary:universeState.summary,ranked:")
    s=s.replace("BYBIT_MULTI_ASSET_CONTROLLER_V3_1_PENDING_SLOT_GUARD_UI_READY","BYBIT_MULTI_ASSET_CONTROLLER_V4_DYNAMIC_UNIVERSE_CONTINUOUS_SLOTS")
    return s
rw('cloudflare-worker/bybit-multi-asset-controller.js',patch_controller)

# 8) Runtime and UI contracts.
Path(CW/'bybit-runtime-contract.js').write_text("""import {BYBIT_TRADE_UNIVERSE} from './bybit-coin-profiles.js';
export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_MULTI_ASSET_RUNTIME_V20_DYNAMIC_SCALP_ANTI_SWEEP';
export const BYBIT_AUTO_VERSION='BYBIT-MULTI-STATEFLOW-4.4.0';
export const BYBIT_EXECUTION_AUTHORITY='BYBIT_DYNAMIC_LINEAR_SCALP_MULTI_ASSET';
export const BYBIT_PRIVATE_TRANSPORT='VPS_BYBIT_PRIVATE_PROXY';
export const BYBIT_MARKET_TRANSPORT='VPS_BYBIT_MARKET_PROXY';
export const BYBIT_HEALTH_ROUTE='/bybit/health';
export const TELEGRAM_HUB_ID='BYBIT_MULTI_ASSET_TRADING_HUB';
export const LEGACY_SIGNAL_RUNTIME_DISABLED=true;export const LEGACY_BYBIT_MULTI_COIN_DISABLED=false;export const LEGACY_FOREX_DISABLED=true;export const LEGACY_MEME_DISABLED=true;export const LEGACY_AI_COUNCIL_DISABLED=true;
export const BYBIT_RUNTIME_CONTRACT={version:BYBIT_RUNTIME_CONTRACT_VERSION,autoVersion:BYBIT_AUTO_VERSION,executionAuthority:BYBIT_EXECUTION_AUTHORITY,privateTransport:BYBIT_PRIVATE_TRANSPORT,marketTransport:BYBIT_MARKET_TRANSPORT,healthRoute:BYBIT_HEALTH_ROUTE,telegramHub:TELEGRAM_HUB_ID,legacySignalRuntimeDisabled:true,legacyBybitMultiCoinDisabled:false,legacyForexDisabled:true,legacyMemeDisabled:true,legacyAiCouncilDisabled:true,symbol:'MULTI_DYNAMIC',symbols:BYBIT_TRADE_UNIVERSE,coreSymbols:BYBIT_TRADE_UNIVERSE,market:'LINEAR_PERPETUAL',multiAsset:true,universeAuthority:'BYBIT_DYNAMIC_LINEAR_SCALP_UNIVERSE_V1',universeClasses:['TRADE_CORE','TRADE_STABLE','TRADE_SCALP_FAST','WATCH_NEW','WATCH_READY','WATCH_THIN','DO_NOT_TRADE'],strategyAuthority:'PER_SYMBOL_COGNITION_MOMENTUM_FOOTPRINT_STATE_FIRST',profileAuthority:'CORE_OVERRIDES_PLUS_CONSERVATIVE_DYNAMIC_PROFILE',portfolioAuthority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V5_CONTINUOUS_RISK_SLOTS',autonomous:true,eventDriven:true,decisionAuthority:'VPS_WS_MARKET_STATE_CHANGE',entryTriggerAuthority:'VPS_BRIDGE_SECRET_ONLY',marketScanAuthority:'DYNAMIC_BYBIT_LINEAR_RANK_ROTATING_DEEP_SCAN',openPositionManagement:'EVENT_DRIVEN_PER_SYMBOL',scheduledExecution:false,timeGate:false,sessionGate:false,cooldownGate:false,dailyTradeQuota:'NONE',microstructureWindows:'1S_3S_5S_15S_60S',entryTierAuthority:'PROBE_CONFIRM_FULL',continuousScale:true,continuousTimeCapitalScale:true,riskAuthority:'GLOBAL_PORTFOLIO_RISK_PLUS_PER_SYMBOL_PROFILE',leverageAuthority:'EXCHANGE_INSTRUMENT_MAX_CAPPED_RISK_GOVERNED',infiniteLeverage:false,exchangeMaxLeverageCap:true,plannedNetProfitFloor:true,plannedNetProfitFloorStartsAtOneUsd:true,continuousProfitFloorScale:true,profitFloorRetentionAfterHit:true,positiveAntiSweepLock:true,positiveLockNeverLiteralEntry:true,positiveLockDelayedUntilNoiseRoom:true,momentumFootprint:true,dynamicBybitScalpUniverse:true,newListingsWatchBeforeTrade:true,watchThinNoNewRisk:true,freshWsRequiredForNewRisk:true,staleDataNativeProtectionHold:true,adaptiveProfileVoteThreshold:true,executionQualityAdaptiveLiquidityGate:true,objectiveCandidateRanking:true,rotatingDeepCoverage:true,protectedStopZeroActiveRisk:true,protectedRiskSlotReuse:true,riskSlotAdmissionIncludesPendingEntry:true,physicalPositionHardBuffer:true,forcedOpportunityReplacement:false,profitFloorLockObjective:true,uiContractReady:true,uiBootstrapPublicReadOnly:true,uiSnapshotAuthenticatedReadOnly:true,realizedProfitGuarantee:false,shortMomentumAloneCanExit:false,profitHarvestRequiresMultiStageInvalidation:true,nativeTpAlways:true,costAwareProfitLock:true,positionExitAuthority:'LOSS_THESIS_INVALIDATION_PLUS_PROFIT_HARVEST_EDGE_EXHAUSTION',instabilityExit:true,reentryAuthority:'FRESH_THESIS_ONLY',recoveryMartingale:false,recoveryAddToLoser:false,runtimeSwitchDeploymentPolicy:'PRESERVE_EXISTING',liveAckDeploymentPolicy:'PRESERVE_EXISTING',liveAckCompatibility:'BYBIT_BTC_LIVE_ACK_IS_GLOBAL_BYBIT_LIVE_ACK'};
""",encoding='utf-8')
Path(CW/'bybit-ui-contract.js').write_text("""export const BYBIT_UI_SCHEMA_VERSION='BYBIT_UI_SCHEMA_V1';
export const BYBIT_UI_CORE_BASELINE='BYBIT-MULTI-STATEFLOW-4.4.0';
export const BYBIT_UI_ROUTES=Object.freeze({bootstrap:'/bybit/ui/bootstrap',snapshot:'/bybit/ui/snapshot',health:'/bybit/health',entryHealth:'/bybit/entry-health',runtimeContract:'/runtime/contract'});
export const BYBIT_UI_CAPABILITIES=Object.freeze({coreBackendFrozenForUiV1:true,readOnlyBootstrap:true,authenticatedReadOnlySnapshot:true,liveAccountSummary:true,activePositions:true,protectedRiskSlots:true,candidateRanking:true,candidateDecisions:true,dynamicMarketUniverse:true,newListingWatchlist:true,antiSweepPositiveLock:true,continuousCapitalScale:true,exchangeCappedLeverage:true,profitObjective:true,leveragePolicy:true,riskPolicy:true,executionWriteControlsExposedToUi:false,realizedProfitGuaranteed:false});
""",encoding='utf-8')

# 9) Control plane exposes dynamic registry and revised leverage semantics to UX/UI.
def patch_control(s):
    s=s.replace("universe:BYBIT_TRADE_UNIVERSE,...uiStaticPolicy(env)","coreUniverse:BYBIT_TRADE_UNIVERSE,universeAuthority:'BYBIT_DYNAMIC_LINEAR_SCALP_UNIVERSE_V1',...uiStaticPolicy(env)")
    s=s.replace("leverage:{min:cfg.leverage.min,max:cfg.leverage.max,profitFloorAdaptive:cfg.leverage.profitFloorAdaptive===true,profitFloorMax:cfg.leverage.profitFloorMax,equityAdaptive:cfg.leverage.equityAdaptive}","leverage:{min:cfg.leverage.min,configuredCeiling:cfg.leverage.max,exchangeInstrumentCapRequired:true,infiniteLeverage:false,profitFloorAdaptive:cfg.leverage.profitFloorAdaptive===true,profitFloorMax:cfg.leverage.profitFloorMax,equityAdaptive:cfg.leverage.equityAdaptive}")
    s=s.replace("candidates:{ranking:controller?.objectiveCandidateRanking||[],decisions:controller?.candidateDecisions||[],bestUniverseSymbol:controller?.bestUniverseSymbol||null,lastEventSymbol:controller?.lastEventSymbol||null}","marketUniverse:controller?.dynamicUniverse||null,watchNew:controller?.watchNew||[],watchOnly:controller?.watchOnly||[],candidates:{ranking:controller?.objectiveCandidateRanking||[],decisions:controller?.candidateDecisions||[],bestUniverseSymbol:controller?.bestUniverseSymbol||null,lastEventSymbol:controller?.lastEventSymbol||null}")
    return s
rw('cloudflare-worker/bybit-control-plane.js',patch_control)

# 10) VPS bridge discovers additional high-liquidity symbols for fresh WS; all remaining Bybit linear symbols remain controller watch-only.
def patch_bridge(s):
    old="""DEFAULT_SYMBOL='BTCUSDT'
DEFAULT_SYMBOLS='BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,SOLUSDT,TRXUSDT,DOGEUSDT,ADAUSDT,LINKUSDT,AVAXUSDT,LTCUSDT,BCHUSDT,XLMUSDT,DOTUSDT,NEARUSDT,UNIUSDT,AAVEUSDT,HBARUSDT'
SYMBOLS=tuple(dict.fromkeys(x.strip().upper() for x in os.environ.get('BYBIT_MULTI_SYMBOLS',DEFAULT_SYMBOLS).split(',') if x.strip()))
EVENT_SYMBOLS=set(x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS','BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ADAUSDT,LINKUSDT,LTCUSDT,TRXUSDT').split(',') if x.strip())
WORKER_WAKE_SEMAPHORE=threading.Semaphore(1)
WS_URL=os.environ.get('BYBIT_PUBLIC_WS','wss://stream.bybit.com/v5/public/linear')
WORKER_URL=(os.environ.get('BYBIT_WORKER_URL') or 'https://trading-v77-scanner.hanlinh227.workers.dev').rstrip('/')
EVENT_ENABLED=str(os.environ.get('BYBIT_EVENT_DRIVER_ENABLED','true')).lower() in ('1','true','yes')
BYBIT_BASES=tuple(dict.fromkeys(x.rstrip('/') for x in [os.environ.get('BYBIT_API_BASE_URL','').strip(),'https://api.bybit.com','https://api.bytick.com'] if x.strip()))
"""
    new="""DEFAULT_SYMBOL='BTCUSDT'
DEFAULT_SYMBOLS='BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,SOLUSDT,TRXUSDT,DOGEUSDT,ADAUSDT,LINKUSDT,AVAXUSDT,LTCUSDT,BCHUSDT,XLMUSDT,DOTUSDT,NEARUSDT,UNIUSDT,AAVEUSDT,HBARUSDT'
WORKER_WAKE_SEMAPHORE=threading.Semaphore(1)
WS_URL=os.environ.get('BYBIT_PUBLIC_WS','wss://stream.bybit.com/v5/public/linear')
WORKER_URL=(os.environ.get('BYBIT_WORKER_URL') or 'https://trading-v77-scanner.hanlinh227.workers.dev').rstrip('/')
EVENT_ENABLED=str(os.environ.get('BYBIT_EVENT_DRIVER_ENABLED','true')).lower() in ('1','true','yes')
BYBIT_BASES=tuple(dict.fromkeys(x.rstrip('/') for x in [os.environ.get('BYBIT_API_BASE_URL','').strip(),'https://api.bybit.com','https://api.bytick.com'] if x.strip()))
AUTO_DISCOVER=str(os.environ.get('BYBIT_DYNAMIC_WS_DISCOVERY','true')).lower() in ('1','true','yes')
MAX_WS_SYMBOLS=max(18,min(40,int(os.environ.get('BYBIT_MAX_WS_SYMBOLS','30'))))
CORE_SYMBOLS=tuple(dict.fromkeys(x.strip().upper() for x in DEFAULT_SYMBOLS.split(',') if x.strip()))
MANUAL_SYMBOLS=tuple(dict.fromkeys(x.strip().upper() for x in os.environ.get('BYBIT_MULTI_SYMBOLS','').split(',') if x.strip()))
def discover_ws_symbols():
    seed=list(dict.fromkeys(list(CORE_SYMBOLS)+list(MANUAL_SYMBOLS)))
    if not AUTO_DISCOVER:return tuple(seed[:MAX_WS_SYMBOLS])
    rows=[]
    for base in BYBIT_BASES:
        try:
            req=urllib.request.Request(base+'/v5/market/tickers?category=linear',headers={'user-agent':'Mozilla/5.0','accept':'application/json'})
            with urllib.request.urlopen(req,timeout=8) as r: data=json.loads(r.read(4_000_000).decode())
            for x in (data.get('result') or {}).get('list') or []:
                s=str(x.get('symbol') or '').upper()
                if not s.endswith('USDT') or s in seed:continue
                try:
                    bid=float(x.get('bid1Price') or 0);ask=float(x.get('ask1Price') or 0);turn=float(x.get('turnover24h') or 0);mid=(bid+ask)/2 if bid>0 and ask>0 else 0;spread=(ask-bid)/mid*10000 if mid>0 and ask>=bid else 999
                except Exception:continue
                if turn>=35_000_000 and spread<=7.0:rows.append((turn,-spread,s))
            if rows:break
        except Exception:continue
    rows.sort(reverse=True)
    for _,__,s in rows:
        if len(seed)>=MAX_WS_SYMBOLS:break
        seed.append(s)
    return tuple(seed)
SYMBOLS=discover_ws_symbols()
_extra=[s for s in SYMBOLS if s not in CORE_SYMBOLS]
_default_events=list(CORE_SYMBOLS[:10])+_extra[:8]
EVENT_SYMBOLS=set(x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS',','.join(_default_events)).split(',') if x.strip() and x.strip().upper() in SYMBOLS)
"""
    s=rep(s,old,new,'bridge dynamic constants')
    s=s.replace("'eventSymbols':sorted(EVENT_SYMBOLS)","'eventSymbols':sorted(EVENT_SYMBOLS),'dynamicWsDiscovery':AUTO_DISCOVER,'maxWsSymbols':MAX_WS_SYMBOLS")
    return s
rw('bybit-live-bridge/bybit_live_bridge.py',patch_bridge)

# 11) Validator rewritten for V4.4 safeguards.
Path(CW/'validate-btc-hyperscale.mjs').write_text("""import fs from 'node:fs';import assert from 'node:assert/strict';import {BYBIT_AUTO_CONFIG,bybitExecutionMode} from './bybit-auto-config.js';import {BYBIT_TRADE_UNIVERSE,BYBIT_PORTFOLIO_POLICY,coinProfileForSymbol,isCoreTradeSymbol,maxConcurrentForEquity} from './bybit-coin-profiles.js';import {selectBybitSymbolSetup} from './bybit-symbol-strategy.js';import {sizeBtcSetup} from './bybit-btc-risk-engine.js';import {BYBIT_RUNTIME_CONTRACT,BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';
const read=f=>fs.readFileSync(f,'utf8'),cfg=BYBIT_AUTO_CONFIG;assert.equal(BYBIT_AUTO_VERSION,'BYBIT-MULTI-STATEFLOW-4.4.0');assert.equal(BYBIT_RUNTIME_CONTRACT.version,'BYBIT_MULTI_ASSET_RUNTIME_V20_DYNAMIC_SCALP_ANTI_SWEEP');assert.ok(BYBIT_TRADE_UNIVERSE.length>=18);assert.ok(isCoreTradeSymbol('BTCUSDT'));assert.ok(coinProfileForSymbol('SOMECOINUSDT')?.dynamicProfile===true);assert.equal(coinProfileForSymbol('USDCUSDT'),null);assert.equal(cfg.risk.martingale,false);assert.equal(cfg.risk.addToLoser,false);assert.equal(cfg.risk.gridRescue,false);assert.equal(cfg.execution.noTimeGate,true);assert.equal(cfg.scalp.requireNetFloorAfterFees,true);assert.ok(cfg.scalp.minPlannedNetProfitUsd>1);assert.equal(cfg.scalp.positiveAntiSweep.enabled,true);assert.ok(cfg.scalp.positiveAntiSweep.minGapTicks>=10);assert.ok(cfg.scalp.positiveAntiSweep.minPreservedNetUsd>0);assert.equal(cfg.leverage.exchangeInstrumentCapRequired,true);assert.ok(cfg.leverage.max>=100);assert.equal(BYBIT_RUNTIME_CONTRACT.infiniteLeverage,false);assert.equal(BYBIT_RUNTIME_CONTRACT.exchangeMaxLeverageCap,true);assert.equal(BYBIT_RUNTIME_CONTRACT.dynamicBybitScalpUniverse,true);assert.equal(BYBIT_RUNTIME_CONTRACT.newListingsWatchBeforeTrade,true);assert.equal(BYBIT_RUNTIME_CONTRACT.positiveAntiSweepLock,true);assert.equal(BYBIT_RUNTIME_CONTRACT.continuousTimeCapitalScale,true);assert.ok(maxConcurrentForEquity(60)>maxConcurrentForEquity(50));assert.ok(maxConcurrentForEquity(500)>maxConcurrentForEquity(100));assert.equal(BYBIT_PORTFOLIO_POLICY.forcedOpportunityReplacement,false);assert.equal(BYBIT_PORTFOLIO_POLICY.protectedRiskSlotReuse,true);assert.ok(BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer>=2);assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true'}),'PAPER');assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'LIVE');
const quant=sizeBtcSetup({setup:{side:'Buy',strength:'STRONG',entryTier:'FULL',entry:80000,sl:79900,cost:{totalCostBps:11}},riskUsd:.50,maxRiskUsd:.62,filters:{qtyStep:.001,minQty:.001,minNotional:5,maxQty:10},leverage:12,equityUsd:39,capitalBaseUsd:39,marginCapPct:78});assert.ok(quant.ok);assert.ok(quant.effectiveLossEstimateUsd<=quant.hardRiskCapUsd+1e-9);
const engine=read('bybit-symbol-engine.js'),controller=read('bybit-multi-asset-controller.js'),strategy=read('bybit-symbol-strategy.js'),dynamic=read('bybit-dynamic-universe.js'),runtime=read('bybit-runtime-contract.js'),ui=read('bybit-ui-contract.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py'),balance=read('bybit-btc-balance-reconciler.js');for(const x of ['BYBIT-MULTI-ASSET-ENGINE-4.4.0-ANTI-SWEEP-DYNAMIC-SCALP','positiveLockReady','antiSweepGap','POSITIVE_AFTER_COST_WIDE_NOISE_GAP','exchangeMaxLeverage','continuousTimeScale'])assert.ok(engine.includes(x),`ENGINE ${x}`);for(const x of ['buildBybitDynamicUniverse','DYNAMIC_UNIVERSE_WATCH_ONLY','continuousCapacityCapitalUsd','pendingEntrySlot=1','BYBIT_MULTI_ASSET_CONTROLLER_V4_DYNAMIC_UNIVERSE_CONTINUOUS_SLOTS'])assert.ok(controller.includes(x),`CONTROLLER ${x}`);for(const x of ['momentumFootprint','FOOTPRINT_SPIKE_WITHOUT_FOLLOW_THROUGH','BYBIT_SYMBOL_COGNITION_V4_MOMENTUM_FOOTPRINT_DYNAMIC_SCALP','PROFILE_MICROSTRUCTURE_STALE_OR_FALLBACK_ONLY'])assert.ok(strategy.includes(x),`STRATEGY ${x}`);for(const x of ['TRADE_CORE','TRADE_STABLE','TRADE_SCALP_FAST','WATCH_NEW','WATCH_THIN','DO_NOT_TRADE','BYBIT_DYNAMIC_LINEAR_SCALP_UNIVERSE_V1'])assert.ok(dynamic.includes(x),`DYNAMIC ${x}`);for(const x of ['BYBIT_MULTI_ASSET_RUNTIME_V20_DYNAMIC_SCALP_ANTI_SWEEP','infiniteLeverage:false','realizedProfitGuarantee:false'])assert.ok(runtime.includes(x),`RUNTIME ${x}`);for(const x of ['dynamicMarketUniverse:true','antiSweepPositiveLock:true','exchangeCappedLeverage:true'])assert.ok(ui.includes(x),`UI ${x}`);for(const x of ['discover_ws_symbols','BYBIT_DYNAMIC_WS_DISCOVERY','MAX_WS_SYMBOLS','x-bybit-symbol'])assert.ok(bridge.includes(x),`BRIDGE ${x}`);assert.ok(balance.includes('TIME_DECAYED_EQUITY_BALANCE_INSTANT_DOWNSIDE'));assert.ok(balance.includes('continuousCapitalUsd'));
console.log('BYBIT_MULTI_ASSET_VALIDATION=PASS');console.log(JSON.stringify({version:BYBIT_AUTO_VERSION,coreSymbols:BYBIT_TRADE_UNIVERSE.length,dynamicUniverse:true,newListingsWatch:true,momentumFootprint:true,positiveAntiSweep:true,plannedMinNetProfitUsd:cfg.scalp.minPlannedNetProfitUsd,exchangeMaxLeverage:true,infiniteLeverage:false,continuousTimeCapital:true,continuousRiskSlots:true,freshWsRequired:true,martingale:false,addToLoser:false,realizedProfitGuaranteed:false},null,2));
""",encoding='utf-8')

print('BYBIT_V440_PATCH_APPLIED')
