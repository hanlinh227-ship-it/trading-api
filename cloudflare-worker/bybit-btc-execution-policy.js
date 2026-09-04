// BTCUSDT fast execution policy. This module defines order-type choice and freshness/cost gates.
// Live signing/transport remains delegated to the existing Bybit V5 clients.

const n=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

export function executionDecision({setupType,spreadBps=0,slippageBps=0,quoteAgeMs=0,expectedEdgeBps=0,bookStable=true}={}){
  const spread=Math.max(0,n(spreadBps)),slip=Math.max(0,n(slippageBps)),age=Math.max(0,n(quoteAgeMs)),edge=Math.max(0,n(expectedEdgeBps));
  if(age>1200)return {ok:false,reason:"STALE_QUOTE"};
  if(!bookStable)return {ok:false,reason:"ORDERBOOK_UNSTABLE"};
  const cost=spread+slip;
  if(edge<=cost*1.5)return {ok:false,reason:"EDGE_DOES_NOT_CLEAR_COST",costBps:cost,expectedEdgeBps:edge};
  const breakout=String(setupType||"").includes("BREAKOUT");
  if(breakout&&spread<=8)return {ok:true,orderType:"MarketOrIOC",costBps:cost,maxChaseBps:Math.max(6,clamp(edge*.18,6,20))};
  return {ok:true,orderType:"PostOnlyOrLimit",costBps:cost,maxChaseBps:Math.max(4,clamp(edge*.12,4,12))};
}

export function protectionAckRequired(){
  return {httpAckIsNotEnough:true,requirePrivateOrderOrExecutionEvent:true,requirePositionReconciliation:true,requireStopGeometryValidation:true};
}
