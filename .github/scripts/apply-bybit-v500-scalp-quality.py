from pathlib import Path
import re

ROOT = Path('cloudflare-worker')

def rw(name):
    p = ROOT / name
    return p, p.read_text()

def save(p, s):
    p.write_text(s)

def rep(s, old, new, label):
    if old not in s:
        raise SystemExit(f'MISSING:{label}')
    return s.replace(old, new, 1)

def sub(s, pattern, new, label):
    out, n = re.subn(pattern, new, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'REGEX_MISSING:{label}:{n}')
    return out

# V5.0 principle:
# - keep scalp TP distances short
# - improve hit-rate by refusing weak entries, not by stretching TP
# - require a real edge after taker fees/spread/slippage
# - no PROBE / TRANSITION new risk while live edge is being re-qualified
# - preserve risk caps, native TP/SL, no martingale, no add-to-loser

# 1) Runtime/config declarations.
p, s = rw('bybit-runtime-contract.js')
s = rep(s, "BYBIT_MULTI_ASSET_RUNTIME_V27_SCALP_FIRST_MULTI_ENTRY", "BYBIT_MULTI_ASSET_RUNTIME_V28_SCALP_QUALITY_POSITIVE_EDGE", 'runtime contract version')
s = rep(s, "BYBIT-MULTI-STATEFLOW-4.9.0", "BYBIT-MULTI-STATEFLOW-5.0.0", 'auto version')
s = rep(s, "scalpVelocityCandidateRanking:true,", "scalpVelocityCandidateRanking:true,entryQualityPositiveNetEdge:true,shortHorizonPriceConfirmation:true,probeNewRiskDisabled:true,transitionNewRiskDisabled:true,positiveExpectancyGovernorV2:true,", 'runtime scalp quality flags')
save(p, s)

p, s = rw('bybit-auto-config.js')
s = rep(s, "strategyAuthority:'STATE_FIRST_ULTRAFAST_FLOW_STRUCTURE_LIQUIDITY_DERIVATIVES_PER_SYMBOL'", "strategyAuthority:'SCALP_QUALITY_SHORT_HORIZON_CONFIRMATION_POSITIVE_NET_EDGE_PER_SYMBOL'", 'strategy authority')
s = rep(s, "authority:'SCALP_FIRST_REALISTIC_TARGET_FAST_TURNOVER_PROFIT_LOCK'", "authority:'SCALP_QUALITY_REALISTIC_TARGET_POSITIVE_NET_EDGE_FAST_TURNOVER'", 'scalp authority')
s = rep(s, "entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true,squeezeRelease:true,momentumEarlyRelease:true,rangeMicroReclaimScalp:true,transitionWsScalp:true,shortHorizonReversal:true,sampleQualityGuard:true,probeConfirmFull:true}", "entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true,squeezeRelease:true,momentumEarlyRelease:true,rangeMicroReclaimScalp:true,transitionWsScalp:false,shortHorizonReversal:true,sampleQualityGuard:true,probeConfirmFull:false,confirmOrFullOnly:true,shortHorizonPriceConfirmation:true,positiveNetEdgeRequired:true}", 'entry mode flags')
s = rep(s, "BYBIT-MULTI-STATEFLOW-4.9.0", "BYBIT-MULTI-STATEFLOW-5.0.0", 'config version')
save(p, s)

# 2) BTC/base setup admission: quality first, costs first, no weak probes.
p, s = rw('bybit-btc-strategy.js')
s = rep(s, "return s?.quality?.wsFastPath?.55:.40;", "return s?.quality?.wsFastPath?.28:.15;", 'missing sample quality fallback')
s = rep(s,
    "function flowState(side,s={}){const sign=side==='Buy'?1:-1,f1=num(s.trades?.window1s?.imbalance??s.ultraFast?.flow1),f3=num(s.trades?.window3s?.imbalance??s.ultraFast?.flow3),f5=num(s.trades?.window5s?.imbalance),f15=num(s.trades?.window15s?.imbalance??s.trades?.aggressorImbalance),f60=num(s.trades?.window60s?.imbalance),shortFlow=.12*f1+.18*f3+.25*f5+.45*f15,reversalPressure=shortFlow-.40*f60;return {sign,f1,f3,f5,f15,f60,shortFlow,reversalPressure,dirF1:sign*f1,dirF3:sign*f3,dirF5:sign*f5,dirF15:sign*f15,dirF60:sign*f60,dirShort:sign*shortFlow,dirReversal:sign*reversalPressure};}",
    "function flowState(side,s={}){const sign=side==='Buy'?1:-1,f1=num(s.trades?.window1s?.imbalance??s.ultraFast?.flow1),f3=num(s.trades?.window3s?.imbalance??s.ultraFast?.flow3),f5=num(s.trades?.window5s?.imbalance),f15=num(s.trades?.window15s?.imbalance??s.trades?.aggressorImbalance),f60=num(s.trades?.window60s?.imbalance),shortFlow=.12*f1+.18*f3+.25*f5+.45*f15,reversalPressure=shortFlow-.40*f60;return {sign,f1,f3,f5,f15,f60,shortFlow,reversalPressure,dirF1:sign*f1,dirF3:sign*f3,dirF5:sign*f5,dirF15:sign*f15,dirF60:sign*f60,dirShort:sign*shortFlow,dirReversal:sign*reversalPressure};}\nfunction shortPriceConfirmation(side,s={}){const sign=side==='Buy'?1:-1,t=s.trades||{},p1=sign*num(t.window1s?.priceChangeBps??t.priceChange1sBps),p3=sign*num(t.window3s?.priceChangeBps??t.priceChange3sBps),p5=sign*num(t.window5s?.priceChangeBps??t.priceChange5sBps),votes=[p1>0,p3>0,p5>0].filter(Boolean).length;return {ok:votes>=2&&p3>-.8&&p5>-1.0,votes,p1,p3,p5};}",
    'short horizon price confirmation helper')
s = rep(s,
    "minNetBps=Math.max(tier==='PROBE'?3.0:4.0,totalCostBps*(tier==='PROBE'?.28:.36)),minNetRR=tier==='PROBE'?.30:.38;",
    "minNetBps=Math.max(tier==='PROBE'?6.0:6.5,totalCostBps*(tier==='PROBE'?.55:.60)),minNetRR=tier==='PROBE'?.70:.78;",
    'btc post cost edge')
s = rep(s,
    "function candidate(side,setup,s,why=[],strength='NORMAL',entryTier='CONFIRM'){const x=make(side,setup,s,why,strength,entryTier);return x.cost.ok?{ok:true,setup:x}:{ok:false,reason:'EDGE_INSUFFICIENT_AFTER_FEES_FUNDING',cost:x.cost,candidate:x};}",
    "function candidate(side,setup,s,why=[],strength='NORMAL',entryTier='CONFIRM'){const x=make(side,setup,s,why,strength,entryTier);if(entryTier==='PROBE')return {ok:false,reason:'V50_PROBE_DISABLED_FOR_LIVE_SCALP',candidate:x};return x.cost.ok?{ok:true,setup:x}:{ok:false,reason:'EDGE_INSUFFICIENT_AFTER_FEES_FUNDING',cost:x.cost,candidate:x};}",
    'disable probe admission')

s = sub(s,
    r"function confirmedMomentum\(side,s=\{\},threshold=\.105\)\{.*?\}\nfunction fullMomentum",
    "function confirmedMomentum(side,s={},threshold=.105){if(!s?.quality?.wsFastPath||String(s.microstructureSource)!=='VPS_BYBIT_WS')return false;const f=flowState(side,s),q=sampleQuality(s),sign=f.sign,acc=sign*num(s.ultraFast?.flowAcceleration),pressure=sign*num(s.ultraFast?.pressureScore),imp=sign*num(s.ultraFast?.impulseScore),b2=sign*num(s.book?.imbalance2),mp=sign*num(s.book?.micropriceEdgeBps),p=pulseFor(side,s),m=momentumScore(side,s),pc=shortPriceConfirmation(side,s),flowCore=f.dirF15>.10&&f.dirShort>.13&&(f.dirF60>-.20||f.dirReversal>.34),fastPush=acc>.045||imp>.065||f.dirF3>.13||f.dirF5>.14||p.speed>.18,microOk=b2>-.06&&mp>-.08,persistence=num(s.ultraFast?.signPersistence)>=1||pressure>.065||p.agreement>.60;return q>.42&&m>Math.max(threshold,.16)&&flowCore&&fastPush&&microOk&&persistence&&pc.ok;}\nfunction fullMomentum",
    'confirmed momentum quality')
s = sub(s,
    r"function fullMomentum\(side,s=\{\}\)\{.*?\}\nfunction squeezeRelease",
    "function fullMomentum(side,s={}){const f=flowState(side,s),p=pulseFor(side,s),m=momentumScore(side,s),sign=f.sign,book=sign*num(s.book?.imbalance2),pressure=sign*num(s.ultraFast?.pressureScore),imp=sign*num(s.ultraFast?.impulseScore),pc=shortPriceConfirmation(side,s);return confirmedMomentum(side,s,.19)&&sampleQuality(s)>.55&&m>.23&&f.dirF15>.16&&(f.dirF60>-.12||f.dirReversal>.42)&&book>-.02&&(pressure>.085||imp>.095||p.confidence>.52)&&p.conflict<.48&&pc.ok;}\nfunction squeezeRelease",
    'full momentum quality')
s = sub(s,
    r"function squeezeRelease\(side,s=\{\}\)\{.*?\}\nfunction rangeEdge",
    "function squeezeRelease(side,s={}){if(!s?.quality?.wsFastPath||String(s.microstructureSource)!=='VPS_BYBIT_WS')return false;const f=flowState(side,s),sign=f.sign,break5=side==='Buy'?!!s.structure5?.breakUp:!!s.structure5?.breakDown,p=pulseFor(side,s),pc=shortPriceConfirmation(side,s),aligned=f.dirF15>.12&&(f.dirF60>-.16||f.dirReversal>.34)&&sign*num(s.ultraFast?.pressureScore)>.06&&sign*num(s.book?.imbalance2)>-.03&&sign*num(s.book?.micropriceEdgeBps)>-.07,acceleration=sign*num(s.ultraFast?.flowAcceleration)>.045||f.dirF3>.13||f.dirF5>.14||p.speed>.18;return break5&&sampleQuality(s)>.46&&aligned&&acceleration&&directionalScore(side,s)>.10&&pc.ok;}\nfunction rangeEdge",
    'squeeze quality')
s = sub(s,
    r"function rangeMicroReclaim\(side,s=\{\}\)\{.*?\}\nexport function selectBtcSetup",
    "function rangeMicroReclaim(side,s={}){if(!s?.quality?.wsFastPath||String(s.microstructureSource)!=='VPS_BYBIT_WS'||!rangeEdge(side,s))return false;const f=flowState(side,s),sign=f.sign,p=pulseFor(side,s),m=momentumScore(side,s),pc=shortPriceConfirmation(side,s);return sampleQuality(s)>.44&&f.dirF3>.14&&f.dirF5>.15&&f.dirF15>.07&&(f.dirReversal>.24||sign*num(s.ultraFast?.impulseScore)>.07||p.score>.08)&&sign*num(s.book?.imbalance2)>.00&&sign*num(s.book?.micropriceEdgeBps)>-.05&&m>.11&&pc.ok;}\nexport function selectBtcSetup",
    'range reclaim quality')

# Liquidation exhaustion now needs an actual fast reversal, not merely non-catastrophic opposing flow.
s = rep(s,
    "if(downSweep&&liqShare>.04&&liqImb>.15&&flow>-.20&&book2>-.01&&mp>=-.16)return candidate('Buy','LIQUIDATION_EXHAUSTION_RECLAIM',s,['LONG_LIQUIDATION_BURST','SELLSIDE_SWEEP','BID_ABSORPTION','FLOW_STABILIZED'],scoreBuy>.15?'STRONG':'NORMAL','CONFIRM');",
    "if(downSweep&&liqShare>.05&&liqImb>.18&&q>.44&&flow>.02&&book2>.01&&mp>=-.08&&fastReversal('Buy',s))return candidate('Buy','LIQUIDATION_EXHAUSTION_RECLAIM',s,['LONG_LIQUIDATION_BURST','SELLSIDE_SWEEP','FAST_BUY_REVERSAL','BID_ABSORPTION'],scoreBuy>.18?'STRONG':'NORMAL','CONFIRM');",
    'long liquidation reclaim')
s = rep(s,
    "if(upSweep&&liqShare>.04&&liqImb<-.15&&flow<.20&&book2<.01&&mp<=.16)return candidate('Sell','LIQUIDATION_EXHAUSTION_RECLAIM',s,['SHORT_LIQUIDATION_BURST','BUYSIDE_SWEEP','OFFER_ABSORPTION','FLOW_STABILIZED'],scoreSell>.15?'STRONG':'NORMAL','CONFIRM');",
    "if(upSweep&&liqShare>.05&&liqImb<-.18&&q>.44&&flow<-.02&&book2<-.01&&mp<=.08&&fastReversal('Sell',s))return candidate('Sell','LIQUIDATION_EXHAUSTION_RECLAIM',s,['SHORT_LIQUIDATION_BURST','BUYSIDE_SWEEP','FAST_SELL_REVERSAL','OFFER_ABSORPTION'],scoreSell>.18?'STRONG':'NORMAL','CONFIRM');",
    'short liquidation reclaim')

# Breakout: no early probe; OI and short-horizon flow must confirm.
s = sub(s,
    r"if\(s\.regime==='BREAKOUT_UP'\)\{.*?return \{ok:false,reason:'BREAKOUT_UP_WAIT_MOMENTUM_CONFIRMATION'.*?\};\}",
    "if(s.regime==='BREAKOUT_UP'){const ext=breakoutExtensionBps('Buy',s);if(ext<28&&!longHeavy&&d5>.010&&oi>-.12&&fullMomentum('Buy',s))return candidate('Buy','BREAKOUT_MOMENTUM_FLOW_CONFIRM',s,['STRUCTURE_BREAK_UP','FULL_WS_MOMENTUM','OI_STABLE','PRICE_FOLLOW_THROUGH'],'A_PLUS','FULL');if(ext<22&&!longHeavy&&d5>.006&&oi>-.08&&confirmedMomentum('Buy',s,.13)&&(burst>.08||fastReversal('Buy',s)))return candidate('Buy','BREAKOUT_MOMENTUM_FLOW_CONFIRM',s,['STRUCTURE_BREAK_UP','FAST_WS_CONFIRM','OI_STABLE','NOT_OVEREXTENDED'],'STRONG','CONFIRM');return {ok:false,reason:'BREAKOUT_UP_WAIT_HIGH_QUALITY_CONFIRMATION',diagnostic:{scoreBuy,momBuy,burst,oi,ext,q,reversal:buyFlow.dirReversal}};}",
    'breakout up')
s = sub(s,
    r"if\(s\.regime==='BREAKOUT_DOWN'\)\{.*?return \{ok:false,reason:'BREAKOUT_DOWN_WAIT_MOMENTUM_CONFIRMATION'.*?\};\}",
    "if(s.regime==='BREAKOUT_DOWN'){const ext=breakoutExtensionBps('Sell',s);if(ext<28&&!shortHeavy&&d5<-.010&&oi>-.12&&fullMomentum('Sell',s))return candidate('Sell','BREAKOUT_MOMENTUM_FLOW_CONFIRM',s,['STRUCTURE_BREAK_DOWN','FULL_WS_MOMENTUM','OI_STABLE','PRICE_FOLLOW_THROUGH'],'A_PLUS','FULL');if(ext<22&&!shortHeavy&&d5<-.006&&oi>-.08&&confirmedMomentum('Sell',s,.13)&&(burst>.08||fastReversal('Sell',s)))return candidate('Sell','BREAKOUT_MOMENTUM_FLOW_CONFIRM',s,['STRUCTURE_BREAK_DOWN','FAST_WS_CONFIRM','OI_STABLE','NOT_OVEREXTENDED'],'STRONG','CONFIRM');return {ok:false,reason:'BREAKOUT_DOWN_WAIT_HIGH_QUALITY_CONFIRMATION',diagnostic:{scoreSell,momSell,burst,oi,ext,q,reversal:sellFlow.dirReversal}};}",
    'breakout down')

# Trend pullbacks must show a real reclaim. Continuations need stronger WS confirmation.
s = sub(s,
    r"if\(s\.regime==='TREND_UP'\)\{.*?return \{ok:false,reason:'UPTREND_WAIT_FOR_PULLBACK_OR_MOMENTUM'.*?\};\}",
    "if(s.regime==='TREND_UP'){if(downSweep&&q>.44&&flow>.035&&flow60>-.18&&book2>.00&&mp>-.10&&d5>-.006&&confirmedMomentum('Buy',s,.12))return candidate('Buy','TREND_PULLBACK_LIQUIDITY_RECLAIM',s,['UP_STRUCTURE','SELLSIDE_SWEEP_RECLAIM','FAST_BUY_RECOVERY','PRICE_CONFIRM'],scoreBuy>.16?'STRONG':'NORMAL','CONFIRM');if(d5>.014&&fullMomentum('Buy',s)&&eff>.12&&!longHeavy)return candidate('Buy','TREND_MOMENTUM_CONTINUATION',s,['UP_STRUCTURE','FULL_WS_MOMENTUM','PULSE_ALIGNED'],'A_PLUS','FULL');if(d5>.006&&confirmedMomentum('Buy',s,.12)&&eff>.10&&!longHeavy)return candidate('Buy','TREND_MOMENTUM_CONTINUATION',s,['UP_STRUCTURE','FAST_WS_CONFIRM','PRICE_FOLLOW_THROUGH'],'STRONG','CONFIRM');return {ok:false,reason:'UPTREND_WAIT_HIGH_QUALITY_RECLAIM_OR_MOMENTUM',diagnostic:{scoreBuy,momBuy,burst,eff,q,reversal:buyFlow.dirReversal}};}",
    'trend up')
s = sub(s,
    r"if\(s\.regime==='TREND_DOWN'\)\{.*?return \{ok:false,reason:'DOWNTREND_WAIT_FOR_PULLBACK_OR_MOMENTUM'.*?\};\}",
    "if(s.regime==='TREND_DOWN'){if(upSweep&&q>.44&&flow<-.035&&flow60<.18&&book2<.00&&mp<.10&&d5<.006&&confirmedMomentum('Sell',s,.12))return candidate('Sell','TREND_PULLBACK_LIQUIDITY_RECLAIM',s,['DOWN_STRUCTURE','BUYSIDE_SWEEP_RECLAIM','FAST_SELL_RECOVERY','PRICE_CONFIRM'],scoreSell>.16?'STRONG':'NORMAL','CONFIRM');if(d5<-.014&&fullMomentum('Sell',s)&&eff>.12&&!shortHeavy)return candidate('Sell','TREND_MOMENTUM_CONTINUATION',s,['DOWN_STRUCTURE','FULL_WS_MOMENTUM','PULSE_ALIGNED'],'A_PLUS','FULL');if(d5<-.006&&confirmedMomentum('Sell',s,.12)&&eff>.10&&!shortHeavy)return candidate('Sell','TREND_MOMENTUM_CONTINUATION',s,['DOWN_STRUCTURE','FAST_WS_CONFIRM','PRICE_FOLLOW_THROUGH'],'STRONG','CONFIRM');return {ok:false,reason:'DOWNTREND_WAIT_HIGH_QUALITY_RECLAIM_OR_MOMENTUM',diagnostic:{scoreSell,momSell,burst,eff,q,reversal:sellFlow.dirReversal}};}",
    'trend down')

# Squeeze/range: eliminate probe entries and require reversal/follow-through at edges.
s = rep(s, "confirmedMomentum('Buy',s,.075)", "confirmedMomentum('Buy',s,.12)", 'squeeze buy confirmation')
s = rep(s, "confirmedMomentum('Sell',s,.075)", "confirmedMomentum('Sell',s,.12)", 'squeeze sell confirmation')
s = rep(s,
    "if(downSweep&&flow<.02&&book2>.04&&book5>-.02&&mp>-.14)return candidate('Buy','RANGE_SELLSIDE_SWEEP_ABSORPTION',s,['SELLSIDE_SWEEP','BID_ABSORPTION','RECLAIM'],'NORMAL','CONFIRM');",
    "if(downSweep&&q>.44&&flow>.015&&book2>.04&&book5>.00&&mp>-.08&&fastReversal('Buy',s))return candidate('Buy','RANGE_SELLSIDE_SWEEP_ABSORPTION',s,['SELLSIDE_SWEEP','BID_ABSORPTION','FAST_REJECTION_CONFIRM'],'NORMAL','CONFIRM');",
    'range buy absorption')
s = rep(s,
    "if(upSweep&&flow>-.02&&book2<-.04&&book5<.02&&mp<.14)return candidate('Sell','RANGE_BUYSIDE_SWEEP_ABSORPTION',s,['BUYSIDE_SWEEP','OFFER_ABSORPTION','REJECTION'],'NORMAL','CONFIRM');",
    "if(upSweep&&q>.44&&flow<-.015&&book2<-.04&&book5<.00&&mp<.08&&fastReversal('Sell',s))return candidate('Sell','RANGE_BUYSIDE_SWEEP_ABSORPTION',s,['BUYSIDE_SWEEP','OFFER_ABSORPTION','FAST_REJECTION_CONFIRM'],'NORMAL','CONFIRM');",
    'range sell absorption')

# Transition is too ambiguous for a hit-rate recovery regime. Reversal remains available only at FULL quality.
s = sub(s,
    r"  if\(\(s\.regime==='REVERSAL'\|\|s\.regime==='TRANSITION'\).*?  return \{ok:false,reason:'NO_STATE_FIRST_NON_INDICATOR_EDGE'",
    "  if(s.regime==='TRANSITION')return {ok:false,reason:'V50_TRANSITION_NO_NEW_RISK',diagnostic:{q,scoreBuy,scoreSell,momBuy,momSell}};\n  if(s.regime==='REVERSAL'&&q>.55&&d15>0&&d60>=0&&d5>.008&&oi>-.08&&scoreBuy>.14&&flow>.08&&flow60>-.08&&book2>.00&&!longHeavy&&fullMomentum('Buy',s))return candidate('Buy','REVERSAL_FULL_CONFIRM',s,['HTF_STRUCTURE_RECOVERY','FULL_WS_REVERSAL','PRICE_FOLLOW_THROUGH','OI_STABLE'],'STRONG','FULL');\n  if(s.regime==='REVERSAL'&&q>.55&&d15<0&&d60<=0&&d5<-.008&&oi>-.08&&scoreSell>.14&&flow<-.08&&flow60<.08&&book2<.00&&!shortHeavy&&fullMomentum('Sell',s))return candidate('Sell','REVERSAL_FULL_CONFIRM',s,['HTF_STRUCTURE_BREAKDOWN','FULL_WS_REVERSAL','PRICE_FOLLOW_THROUGH','OI_STABLE'],'STRONG','FULL');\n  return {ok:false,reason:'NO_STATE_FIRST_NON_INDICATOR_EDGE'",
    'transition/reversal admission')
s = rep(s, "BTC_STATE_FIRST_MICROSTRUCTURE_V9_SCALP_ONLY_FAST_TURNOVER", "BTC_STATE_FIRST_MICROSTRUCTURE_V10_SCALP_QUALITY_POSITIVE_EDGE", 'btc strategy version')
save(p, s)

# 3) All other symbols: raise quality and post-cost edge, remove transition/probe admission.
p, s = rw('bybit-symbol-strategy.js')
s = rep(s,
    "minNet=Math.max(3.5,total*.32)*Math.max(.92,num(profile.qualityThresholdMult)||1);return {ok:net>=minNet&&rr>=.35",
    "minNet=Math.max(6.0,total*.55)*Math.max(.96,num(profile.qualityThresholdMult)||1);return {ok:net>=minNet&&rr>=.72",
    'symbol post cost gate')
s = rep(s,
    "qualityMin=.23*Math.max(.85,num(p.qualityThresholdMult)||1)",
    "qualityMin=.38*Math.max(.90,num(p.qualityThresholdMult)||1)",
    'symbol quality floor')
s = rep(s,
    "strongConsensus=abs>=threshold*1.70&&q>=qualityMin*1.08&&footprint>-.03,minVotes=strongConsensus?4:5",
    "strongConsensus=abs>=threshold*2.00&&q>=qualityMin*1.12&&footprint>.04&&fp.priceFollow>-.02,minVotes=strongConsensus?5:6",
    'symbol consensus votes')
s = rep(s,
    "if(q<qualityMin||abs<threshold||votes<minVotes)return {ok:false,reason:'PROFILE_EDGE_NOT_CONFIRMED'",
    "if(q<qualityMin||abs<threshold*1.18||votes<minVotes||footprint<=0||fp.priceFollow<-.04)return {ok:false,reason:'PROFILE_EDGE_NOT_CONFIRMED'",
    'symbol quality confirmation')
s = rep(s,
    "if(flow15<-.05*flowMult||flow60<-.58||book<-.20*bookTol)return {ok:false,reason:'PROFILE_MULTI_HORIZON_CONFLICT'};",
    "if(flow15<-.02*flowMult||flow60<-.30||book<-.14*bookTol)return {ok:false,reason:'PROFILE_MULTI_HORIZON_CONFLICT'};",
    'symbol horizon conflict')
s = rep(s,
    "const tier=abs>.16&&q>.38?'FULL':abs>.095&&q>.30?'CONFIRM':'PROBE'",
    "const tier=abs>.19&&q>.52&&votes>=7?'FULL':'CONFIRM'",
    'symbol no probe tier')
s = rep(s,
    "const strength=abs>.18&&q>.42?'A_PLUS':abs>.11?'STRONG':'NORMAL'",
    "const strength=abs>.22&&q>.56&&votes>=7?'A_PLUS':abs>.14&&q>.44?'STRONG':'NORMAL'",
    'symbol strength quality')
s = rep(s,
    "export function selectBybitSymbolSetup(s={}){const symbol=normalizeBybitSymbol(s.symbol||'BTCUSDT'),p=coinProfileForSymbol(symbol);",
    "export function selectBybitSymbolSetup(s={}){const symbol=normalizeBybitSymbol(s.symbol||'BTCUSDT'),p=coinProfileForSymbol(symbol);if(String(s.regime||'')==='TRANSITION')return {ok:false,reason:'V50_TRANSITION_NO_NEW_RISK',symbol};",
    'symbol transition block')
s = rep(s, "BYBIT_SYMBOL_COGNITION_V6_SCALP_VELOCITY_TARGET_CAP", "BYBIT_SYMBOL_COGNITION_V7_SCALP_QUALITY_POSITIVE_EDGE", 'symbol strategy version')
save(p, s)

# 4) Performance governor: weak realized edge is no longer treated as acceptable.
p, s = rw('bybit-performance-governor.js')
s = rep(s,
    "const strength=String(candidate.strength||'NORMAL'),tier=String(candidate.entryTier||'CONFIRM'),quality=num(candidate.quality),edge=num(candidate.edgeScore),rr=num(candidate.netRR),aligned=candidate.localCounterTrend!==true||candidate.reversalValidated===true,exceptional=strength==='A_PLUS'&&tier==='FULL'&&quality>=.38&&edge>=.075&&rr>=2.20&&aligned;",
    "const strength=String(candidate.strength||'NORMAL'),tier=String(candidate.entryTier||'CONFIRM'),quality=num(candidate.quality),edge=num(candidate.edgeScore),rr=num(candidate.netRR),aligned=candidate.localCounterTrend!==true||candidate.reversalValidated===true,exceptional=strength==='A_PLUS'&&tier==='FULL'&&quality>=.58&&edge>=.16&&rr>=.80&&aligned;",
    'exceptional edge definition')
s = rep(s,
    "if(num(g24.trades)>=4&&num(g24.expectancy)<-.04&&num(g24.consecutiveLosses)>=3&&!exceptional)block='GLOBAL_NEGATIVE_EXPECTANCY_GUARD';\n  if(num(s72.trades)>=3&&num(s72.expectancy)<-.035&&!exceptional)block='SYMBOL_NEGATIVE_EXPECTANCY_QUARANTINE';",
    "if(num(g24.trades)>=8&&((num(g24.expectancy)<=0&&num(g24.profitFactor)<1.02)||num(g24.profitFactor)<.90)&&!exceptional)block='GLOBAL_POSITIVE_EDGE_REQUALIFICATION';\n  if(num(g72.trades)>=12&&num(g72.expectancy)<=0&&num(g72.profitFactor)<1.03&&!exceptional)block='GLOBAL_72H_POSITIVE_EDGE_REQUALIFICATION';\n  if(num(s72.trades)>=6&&(num(s72.expectancy)<=0||num(s72.profitFactor)<1.00)&&!exceptional)block='SYMBOL_POSITIVE_EDGE_QUARANTINE';",
    'positive expectancy blocks')
s = rep(s,
    "if(num(g24.trades)>=3&&num(g24.expectancy)<0)riskMult*=.82;\n  if(num(s72.trades)>=2&&num(s72.expectancy)<0)riskMult*=.68;\n  else if(num(s72.trades)>=2&&num(s72.expectancy)>0&&num(s72.profitFactor)>=1.25)riskMult*=1.00;",
    "if(num(g24.trades)>=6&&(num(g24.expectancy)<=0||num(g24.profitFactor)<1.02))riskMult*=.72;\n  if(num(s72.trades)>=4&&(num(s72.expectancy)<=0||num(s72.profitFactor)<1.00))riskMult*=.55;\n  else if(num(s72.trades)>=6&&num(s72.expectancy)>0&&num(s72.profitFactor)>=1.20)riskMult*=1.00;",
    'performance risk multipliers')
s = rep(s, "riskMult=clamp(riskMult,.40,1.00);", "riskMult=clamp(riskMult,.25,1.00);", 'risk multiplier clamp')
s = rep(s, "authority:'REALIZED_NET_EXPECTANCY_CAPITAL_PRESERVATION'", "authority:'REALIZED_NET_POSITIVE_EDGE_SCALP_QUALITY_V2'", 'performance authority')
s = rep(s, "BYBIT_PERFORMANCE_GOVERNOR_V1_REALIZED_NET_EXPECTANCY", "BYBIT_PERFORMANCE_GOVERNOR_V2_POSITIVE_EDGE_SCALP_QUALITY", 'performance version')
save(p, s)

print('BYBIT_V500_SCALP_QUALITY_PATCH_APPLIED')
