// BTC-only state-first strategy router.
// No indicator, AI opinion, funding reading, order-book snapshot, or single metric may create an entry by itself.
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function distFloor(s={}){const px=Math.max(1,num(s.price)),r5=Math.max(0,num(s.range5?.width)),r15=Math.max(0,num(s.range15?.width));return Math.max(px*.00115,r5*.11,r15*.032);}
function geometry(side,s={},setup=''){
  const e=num(s.price),floor=distFloor(s),st=s.structure15||{},sw=s.sweep5||{};let sl=0;
  if(side==='Buy')sl=Math.min(num(sw.priorLow)||e-floor,num(st.recentLow)||e-floor,e-floor);else sl=Math.max(num(sw.priorHigh)||e+floor,num(st.recentHigh)||e+floor,e+floor);
  let risk=Math.abs(e-sl);if(risk<floor){risk=floor;sl=side==='Buy'?e-risk:e+risk;}
  const runner=setup.includes('BREAKOUT')?2.7:setup.includes('RANGE')||setup.includes('LIQUIDATION')?1.55:2.25,tp=side==='Buy'?e+risk*runner:e-risk*runner;
  return {entry:e,sl,tp,rr:runner,stopDistance:risk};
}
function evidence(s={}){return {flow15:num(s.trades?.window15s?.imbalance??s.trades?.aggressorImbalance),flow60:num(s.trades?.window60s?.imbalance),flowBurst:num(s.trades?.burst5x),book2:num(s.book?.imbalance2),book5:num(s.book?.imbalance5??s.book?.imbalance),micropriceEdgeBps:num(s.book?.micropriceEdgeBps),oiDelta:num(s.openInterest?.deltaPct),funding:num(s.fundingRate),premiumBps:num(s.premiumBps),liquidationImbalance:num(s.liquidations?.imbalance),liquidationUsd:num(s.liquidations?.totalUsd),source:s.microstructureSource||'UNKNOWN'};}
function make(side,setup,s,why=[],strength='NORMAL') {const g=geometry(side,s,setup);return {symbol:'BTCUSDT',side,setup,strength,regime:s.regime,...g,reason:why,evidence:evidence(s),createdAt:Date.now(),marketStateAt:s.at};}
function breakoutExtensionBps(side,s={}){const e=num(s.price),level=side==='Buy'?num(s.structure15?.priorHigh):num(s.structure15?.priorLow);return e>0&&level>0?Math.abs(e-level)/e*10000:999;}
function liquidationShare(s={}){const liq=Math.max(0,num(s.liquidations?.totalUsd)),flow=Math.max(1,num(s.trades?.notional60s));return liq/flow;}
function supports(side,s={}){
  const f15=num(s.trades?.window15s?.imbalance??s.trades?.aggressorImbalance),f60=num(s.trades?.window60s?.imbalance),b2=num(s.book?.imbalance2),b5=num(s.book?.imbalance5??s.book?.imbalance),mp=num(s.book?.micropriceEdgeBps);
  if(side==='Buy')return f15>.08&&f60>-.08&&b5>-.12&&mp>-.15&&(b2>-.20||f15>.20);
  return f15<-.08&&f60<.08&&b5<.12&&mp<.15&&(b2<.20||f15<-.20);
}

export function selectBtcSetup(s={}){
  if(!s?.quality?.freshBook||!s?.quality?.freshTrades||!s?.quality?.spreadOk)return {ok:false,reason:'MICROSTRUCTURE_STALE_OR_SPREAD_WIDE'};
  const flow=num(s.trades?.window15s?.imbalance??s.trades?.aggressorImbalance),flow60=num(s.trades?.window60s?.imbalance),burst=num(s.trades?.burst5x),book2=num(s.book?.imbalance2),book5=num(s.book?.imbalance5??s.book?.imbalance),mp=num(s.book?.micropriceEdgeBps),oi=num(s.openInterest?.deltaPct),d5=num(s.direction5),d15=num(s.direction15),d60=num(s.direction60),eff=num(s.efficiency15),longHeavy=!!s.crowding?.longHeavy,shortHeavy=!!s.crowding?.shortHeavy,downSweep=!!s.sweep5?.downSweep,upSweep=!!s.sweep5?.upSweep,liqImb=num(s.liquidations?.imbalance),liqShare=liquidationShare(s);
  if(s.regime==='HIGH_VOL_SHOCK')return {ok:false,reason:'HIGH_VOL_SHOCK_NO_NEW_RISK'};

  // Liquidation exhaustion: forced flow must coincide with a liquidity sweep and visible absorption/recovery.
  if(downSweep&&liqShare>.06&&liqImb>.20&&flow>-.10&&book2>.08&&mp>=-.05)return {ok:true,setup:make('Buy','LIQUIDATION_EXHAUSTION_RECLAIM',s,['LONG_LIQUIDATION_BURST','SELLSIDE_SWEEP','NEAR_TOUCH_BID_ABSORPTION','FLOW_STABILIZED'],flow>.12?'STRONG':'NORMAL')};
  if(upSweep&&liqShare>.06&&liqImb<-.20&&flow<.10&&book2<-.08&&mp<=.05)return {ok:true,setup:make('Sell','LIQUIDATION_EXHAUSTION_RECLAIM',s,['SHORT_LIQUIDATION_BURST','BUYSIDE_SWEEP','NEAR_TOUCH_OFFER_ABSORPTION','FLOW_STABILIZED'],flow<-.12?'STRONG':'NORMAL')};

  if(s.regime==='BREAKOUT_UP'){
    const ext=breakoutExtensionBps('Buy',s);if(supports('Buy',s)&&d5>.08&&oi>-.35&&!longHeavy&&ext<18&&burst>.35)return {ok:true,setup:make('Buy','BREAKOUT_RETEST_FLOW_CONFIRM',s,['STRUCTURE_BREAK_UP','EXECUTED_BUY_FLOW','NEAR_TOUCH_LIQUIDITY_SUPPORT','NOT_OVEREXTENDED','NO_LONG_CROWDING'],flow>.26&&oi>.18&&book2>.08?'A_PLUS':'STRONG')};
    return {ok:false,reason:'BREAKOUT_UP_WAIT_RETEST_OR_FLOW_CONFIRMATION'};
  }
  if(s.regime==='BREAKOUT_DOWN'){
    const ext=breakoutExtensionBps('Sell',s);if(supports('Sell',s)&&d5<-.08&&oi>-.35&&!shortHeavy&&ext<18&&burst>.35)return {ok:true,setup:make('Sell','BREAKOUT_RETEST_FLOW_CONFIRM',s,['STRUCTURE_BREAK_DOWN','EXECUTED_SELL_FLOW','NEAR_TOUCH_LIQUIDITY_RESISTANCE','NOT_OVEREXTENDED','NO_SHORT_CROWDING'],flow<-.26&&oi>.18&&book2<-.08?'A_PLUS':'STRONG')};
    return {ok:false,reason:'BREAKOUT_DOWN_WAIT_RETEST_OR_FLOW_CONFIRMATION'};
  }

  if(s.regime==='TREND_UP'){
    if(downSweep&&flow>-.10&&flow60>-.12&&book2>.05&&mp>-.08)return {ok:true,setup:make('Buy','TREND_PULLBACK_LIQUIDITY_RECLAIM',s,['UP_STRUCTURE','SELLSIDE_SWEEP_RECLAIM','NEAR_TOUCH_BID_ABSORPTION','EXECUTED_FLOW_NOT_COLLAPSING'],oi>.10?'STRONG':'NORMAL')};
    if(d5>.10&&supports('Buy',s)&&eff>.34&&!longHeavy&&burst>.30)return {ok:true,setup:make('Buy','TREND_CONTINUATION_FLOW',s,['UP_STRUCTURE','EXECUTED_BUY_FLOW','NEAR_TOUCH_SUPPORT','MICROPRICE_NOT_ADVERSE','NO_LONG_CROWDING'],oi>.20&&flow>.20?'STRONG':'NORMAL')};
    return {ok:false,reason:'UPTREND_WAIT_FOR_PULLBACK_OR_REAL_FLOW'};
  }
  if(s.regime==='TREND_DOWN'){
    if(upSweep&&flow<.10&&flow60<.12&&book2<-.05&&mp<.08)return {ok:true,setup:make('Sell','TREND_PULLBACK_LIQUIDITY_RECLAIM',s,['DOWN_STRUCTURE','BUYSIDE_SWEEP_RECLAIM','NEAR_TOUCH_OFFER_ABSORPTION','EXECUTED_FLOW_NOT_COLLAPSING'],oi>.10?'STRONG':'NORMAL')};
    if(d5<-.10&&supports('Sell',s)&&eff>.34&&!shortHeavy&&burst>.30)return {ok:true,setup:make('Sell','TREND_CONTINUATION_FLOW',s,['DOWN_STRUCTURE','EXECUTED_SELL_FLOW','NEAR_TOUCH_RESISTANCE','MICROPRICE_NOT_ADVERSE','NO_SHORT_CROWDING'],oi>.20&&flow<-.20?'STRONG':'NORMAL')};
    return {ok:false,reason:'DOWNTREND_WAIT_FOR_PULLBACK_OR_REAL_FLOW'};
  }

  if(s.regime==='RANGE'||s.regime==='SQUEEZE'){
    // Contrarian only after a sweep: aggressive traders hit one side while near-touch liquidity absorbs them.
    if(downSweep&&flow<-.05&&book2>.12&&book5>.05&&mp>-.08)return {ok:true,setup:make('Buy','RANGE_SELLSIDE_SWEEP_ABSORPTION',s,['SELLSIDE_SWEEP','AGGRESSIVE_SELLING','BID_ABSORPTION','RECLAIM'],'NORMAL')};
    if(upSweep&&flow>.05&&book2<-.12&&book5<-.05&&mp<.08)return {ok:true,setup:make('Sell','RANGE_BUYSIDE_SWEEP_ABSORPTION',s,['BUYSIDE_SWEEP','AGGRESSIVE_BUYING','OFFER_ABSORPTION','REJECTION'],'NORMAL')};
    return {ok:false,reason:'RANGE_NO_SWEEP_ABSORPTION'};
  }

  if((s.regime==='REVERSAL'||s.regime==='TRANSITION')&&d15>0&&d60>=0&&flow>.24&&flow60>.08&&book2>.10&&mp>0&&oi>.08&&!longHeavy)return {ok:true,setup:make('Buy','STRUCTURE_TRANSITION_CONFIRM',s,['HTF_STRUCTURE_RECOVERY','STRONG_EXECUTED_BUY_FLOW','NEAR_TOUCH_BID_DOMINANCE','OI_EXPANSION'],'STRONG')};
  if((s.regime==='REVERSAL'||s.regime==='TRANSITION')&&d15<0&&d60<=0&&flow<-.24&&flow60<-.08&&book2<-.10&&mp<0&&oi>.08&&!shortHeavy)return {ok:true,setup:make('Sell','STRUCTURE_TRANSITION_CONFIRM',s,['HTF_STRUCTURE_BREAKDOWN','STRONG_EXECUTED_SELL_FLOW','NEAR_TOUCH_OFFER_DOMINANCE','OI_EXPANSION'],'STRONG')};
  return {ok:false,reason:'NO_STATE_FIRST_NON_INDICATOR_EDGE'};
}

export const BTC_STRATEGY_VERSION='BTC_STATE_FIRST_MICROSTRUCTURE_V2';
