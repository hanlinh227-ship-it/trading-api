import {binanceUsdm,symbolFilters,roundTick} from "./binance-usdm-client.js";
import {nextManagedStop} from "./binance-scalp-exit.js";

function parseK(rows){return (rows||[]).map(x=>[Number(x[0]),Number(x[1]),Number(x[2]),Number(x[3]),Number(x[4]),Number(x[5])]);}
function atr(rows,n=14){if(rows.length<n+1)return 0;let s=0;for(let i=rows.length-n;i<rows.length;i++){const p=rows[i-1][4],r=rows[i];s+=Math.max(r[2]-r[3],Math.abs(r[2]-p),Math.abs(r[3]-p));}return s/n;}
function structureConfirmed(side,rows){const xs=rows.slice(-6);if(xs.length<6)return false;const a=xs.slice(0,3),b=xs.slice(3);const lowA=Math.min(...a.map(x=>x[3])),lowB=Math.min(...b.map(x=>x[3])),highA=Math.max(...a.map(x=>x[2])),highB=Math.max(...b.map(x=>x[2]));return side==="BUY"?lowB>lowA:highB<highA;}

export async function manageScalpPosition(env,plan){
  if(!plan?.symbol||!plan?.exitPlan)return {managed:false,reason:"NO_MANAGEABLE_PLAN"};
  const api=binanceUsdm(env),[positions,orders,info,k1,book]=await Promise.all([api.positions(),api.openOrders(plan.symbol),api.exchangeInfo(),api.klines(plan.symbol,"1m",80),api.bookTicker(plan.symbol)]);
  const pos=(positions||[]).find(x=>x.symbol===plan.symbol&&Math.abs(Number(x.positionAmt||0))>0);
  if(!pos)return {managed:false,reason:"POSITION_CLOSED"};
  const rows=parseK(k1),a=atr(rows,14),current=plan.side==="BUY"?Number(book.bidPrice):Number(book.askPrice),confirmed=structureConfirmed(plan.side,rows);
  const stopOrders=(orders||[]).filter(x=>String(x.type||"").includes("STOP"));
  const currentStop=Number(stopOrders[0]?.stopPrice||plan.sl),rawNext=nextManagedStop({side:plan.side,entry:Number(plan.entry),current,initialSl:Number(plan.sl),currentSl:currentStop,atr:a,plan:plan.exitPlan,structureConfirmed:confirmed});
  const f=symbolFilters(info,plan.symbol),next=roundTick(rawNext,f?.tickSize||0);
  const improves=plan.side==="BUY"?next>currentStop:next<currentStop;
  if(!Number.isFinite(next)||!improves)return {managed:true,changed:false,reason:"KEEP_STOP",current,currentStop,next,structureConfirmed:confirmed};
  for(const o of stopOrders)await api.cancelOrder(plan.symbol,o.orderId).catch(()=>{});
  const closeSide=plan.side==="BUY"?"SELL":"BUY";
  const replacement=await api.order({symbol:plan.symbol,side:closeSide,type:"STOP_MARKET",stopPrice:next,closePosition:true,workingType:"MARK_PRICE"});
  return {managed:true,changed:true,reason:"STOP_ADVANCED",current,currentStop,newStop:next,structureConfirmed:confirmed,orderId:replacement.orderId};
}
