// BTC-only strategy router. No indicator is allowed to create an entry by itself.
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function distFloor(s={}){const px=Math.max(1,num(s.price)),r5=Math.max(0,num(s.range5?.width)),r15=Math.max(0,num(s.range15?.width));return Math.max(px*.0012,r5*.12,r15*.035);}
function geometry(side,s={},setup=""){
  const e=num(s.price),floor=distFloor(s),st=s.structure15||{},sw=s.sweep5||{};let sl=0;
  if(side==="Buy")sl=Math.min(num(sw.priorLow)||e-floor,num(st.recentLow)||e-floor,e-floor);else sl=Math.max(num(sw.priorHigh)||e+floor,num(st.recentHigh)||e+floor,e+floor);
  let risk=Math.abs(e-sl);if(risk<floor){risk=floor;sl=side==="Buy"?e-risk:e+risk;}
  const runner=setup.includes("BREAKOUT")?2.8:setup.includes("RANGE")?1.45:2.2,tp=side==="Buy"?e+risk*runner:e-risk*runner;
  return {entry:e,sl,tp,rr:runner,stopDistance:risk};
}
function baseEvidence(s={}){
  return {freshBook:s.quality?.freshBook===true,spreadOk:s.quality?.spreadOk===true,flow:num(s.trades?.aggressorImbalance),book:num(s.book?.imbalance),oiDelta:num(s.openInterest?.deltaPct),funding:num(s.fundingRate),longRatio:num(s.longShort?.buyRatio),shortRatio:num(s.longShort?.sellRatio)};
}
function make(side,setup,s,why=[],strength="NORMAL"){
  const g=geometry(side,s,setup),e=baseEvidence(s);return {symbol:"BTCUSDT",side,setup,strength,regime:s.regime,...g,reason:why,evidence:e,createdAt:Date.now(),marketStateAt:s.at};
}

export function selectBtcSetup(s={}){
  if(!s?.quality?.freshBook||!s?.quality?.spreadOk)return {ok:false,reason:"MICROSTRUCTURE_NOT_FRESH_OR_SPREAD_WIDE"};
  const flow=num(s.trades?.aggressorImbalance),book=num(s.book?.imbalance),oi=num(s.openInterest?.deltaPct),d5=num(s.direction5),d15=num(s.direction15),d60=num(s.direction60),eff=num(s.efficiency15),longHeavy=!!s.crowding?.longHeavy,shortHeavy=!!s.crowding?.shortHeavy,downSweep=!!s.sweep5?.downSweep,upSweep=!!s.sweep5?.upSweep;

  if(s.regime==="HIGH_VOL_SHOCK")return {ok:false,reason:"HIGH_VOL_SHOCK_NO_NEW_RISK"};

  if(s.regime==="BREAKOUT_UP"){
    if(flow>.12&&book>-.10&&d5>.10&&oi>-.35&&!longHeavy)return {ok:true,setup:make("Buy","BREAKOUT_RETEST",s,["STRUCTURE_BREAK_UP","TAKER_BUY_FLOW","BOOK_NOT_OFFER_HEAVY","NO_LONG_CROWDING"],flow>.28&&oi>.20?"A_PLUS":"STRONG")};
    return {ok:false,reason:"BREAKOUT_UP_NOT_CONFIRMED_BY_EXECUTED_FLOW"};
  }
  if(s.regime==="BREAKOUT_DOWN"){
    if(flow<-.12&&book<.10&&d5<-.10&&oi>-.35&&!shortHeavy)return {ok:true,setup:make("Sell","BREAKOUT_RETEST",s,["STRUCTURE_BREAK_DOWN","TAKER_SELL_FLOW","BOOK_NOT_BID_HEAVY","NO_SHORT_CROWDING"],flow<-.28&&oi>.20?"A_PLUS":"STRONG")};
    return {ok:false,reason:"BREAKOUT_DOWN_NOT_CONFIRMED_BY_EXECUTED_FLOW"};
  }

  if(s.regime==="TREND_UP"){
    if(downSweep&&flow>-.08&&book>.05)return {ok:true,setup:make("Buy","TREND_PULLBACK_LIQUIDITY_RECLAIM",s,["UP_STRUCTURE","SELLSIDE_LIQUIDITY_SWEEP_RECLAIM","BID_ABSORPTION"],oi>.10?"STRONG":"NORMAL")};
    if(d5>.10&&flow>.10&&book>-.05&&eff>.34&&!longHeavy)return {ok:true,setup:make("Buy","TREND_CONTINUATION",s,["UP_STRUCTURE","EXECUTED_BUY_FLOW","ORDERBOOK_SUPPORT","NO_LONG_CROWDING"],oi>.20?"STRONG":"NORMAL")};
    return {ok:false,reason:"UPTREND_WAIT_FOR_PULLBACK_OR_REAL_FLOW"};
  }
  if(s.regime==="TREND_DOWN"){
    if(upSweep&&flow<.08&&book<-.05)return {ok:true,setup:make("Sell","TREND_PULLBACK_LIQUIDITY_RECLAIM",s,["DOWN_STRUCTURE","BUYSIDE_LIQUIDITY_SWEEP_RECLAIM","OFFER_ABSORPTION"],oi>.10?"STRONG":"NORMAL")};
    if(d5<-.10&&flow<-.10&&book<.05&&eff>.34&&!shortHeavy)return {ok:true,setup:make("Sell","TREND_CONTINUATION",s,["DOWN_STRUCTURE","EXECUTED_SELL_FLOW","ORDERBOOK_RESISTANCE","NO_SHORT_CROWDING"],oi>.20?"STRONG":"NORMAL")};
    return {ok:false,reason:"DOWNTREND_WAIT_FOR_PULLBACK_OR_REAL_FLOW"};
  }

  if(s.regime==="RANGE"||s.regime==="SQUEEZE"){
    // Absorption logic deliberately wants taker pressure into a sweep while resting/returning liquidity resists it.
    if(downSweep&&flow<-.05&&book>.12)return {ok:true,setup:make("Buy","RANGE_SELLSIDE_SWEEP_ABSORPTION",s,["SELLSIDE_SWEEP","AGGRESSIVE_SELLING","BID_ABSORPTION","RECLAIM"],"NORMAL")};
    if(upSweep&&flow>.05&&book<-.12)return {ok:true,setup:make("Sell","RANGE_BUYSIDE_SWEEP_ABSORPTION",s,["BUYSIDE_SWEEP","AGGRESSIVE_BUYING","OFFER_ABSORPTION","REJECTION"],"NORMAL")};
    return {ok:false,reason:"RANGE_NO_SWEEP_ABSORPTION"};
  }

  // Transition/reversal: require unusually strong agreement instead of guessing a turn.
  if((s.regime==="REVERSAL"||s.regime==="TRANSITION")&&d15>0&&d60>=0&&flow>.25&&book>.12&&oi>.10&&!longHeavy)return {ok:true,setup:make("Buy","STRUCTURE_TRANSITION_CONFIRM",s,["HTF_STRUCTURE_RECOVERY","STRONG_BUY_FLOW","BID_DOMINANCE","OI_EXPANSION"],"STRONG")};
  if((s.regime==="REVERSAL"||s.regime==="TRANSITION")&&d15<0&&d60<=0&&flow<-.25&&book<-.12&&oi>.10&&!shortHeavy)return {ok:true,setup:make("Sell","STRUCTURE_TRANSITION_CONFIRM",s,["HTF_STRUCTURE_BREAKDOWN","STRONG_SELL_FLOW","OFFER_DOMINANCE","OI_EXPANSION"],"STRONG")};
  return {ok:false,reason:"NO_NON_INDICATOR_EDGE"};
}

export const BTC_STRATEGY_VERSION="BTC_STRUCTURE_FLOW_V1";
