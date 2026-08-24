// Binance-native execution guard for Futures scalping.
// Source of truth for execution price is Binance USD-M book/fill data only.

const n=v=>Number(v);
const finite=v=>Number.isFinite(n(v));
const bps=(a,b)=>a>0&&b>0?Math.abs(a-b)/a*10000:Infinity;

export async function preflightExecution(api,setup,env={}){
  const book=await api.bookTicker(setup.symbol);
  const bid=n(book?.bidPrice),ask=n(book?.askPrice),mid=(bid+ask)/2;
  if(!(bid>0)||!(ask>0)||ask<=bid)return {ok:false,reason:"INVALID_BINANCE_BOOK",book};
  const executable=setup.side==="BUY"?ask:bid;
  const spreadBps=(ask-bid)/mid*10000;
  const chaseAtr=finite(setup.atr1)&&n(setup.atr1)>0?Math.abs(executable-n(setup.entry))/n(setup.atr1):Infinity;
  const maxSpreadBps=Math.max(1,n(env.BINANCE_EXEC_MAX_SPREAD_BPS||Math.min(8,n(setup?.liquidity?.universeSpreadBps||8)+2)));
  const maxChaseAtr=Math.max(.05,n(env.BINANCE_EXEC_MAX_CHASE_ATR||.28));
  if(spreadBps>maxSpreadBps)return {ok:false,reason:"EXEC_SPREAD_TOO_WIDE",bid,ask,executable,spreadBps,maxSpreadBps,chaseAtr};
  if(chaseAtr>maxChaseAtr)return {ok:false,reason:"EXEC_PRICE_CHASED",bid,ask,executable,spreadBps,chaseAtr,maxChaseAtr};
  return {ok:true,bid,ask,mid,executable,spreadBps,chaseAtr,checkedAt:Date.now()};
}

export async function resolveMarketFill(api,symbol,orderResult){
  let x=orderResult||{};
  let avg=n(x.avgPrice),qty=n(x.executedQty);
  if((!(avg>0)||!(qty>0))&&x.orderId!=null){
    try{x=await api.queryOrder(symbol,x.orderId);avg=n(x.avgPrice);qty=n(x.executedQty);}catch{}
  }
  if(!(avg>0)||!(qty>0))return {ok:false,reason:"MARKET_FILL_UNCONFIRMED",order:x};
  return {ok:true,avgPrice:avg,executedQty:qty,orderId:x.orderId,status:x.status,order:x};
}

export function validateFillAgainstPlan({setup,preflight,fill,env={}}){
  const side=setup.side,avg=n(fill.avgPrice),expected=n(preflight.executable),sl=n(setup.sl),tp=n(setup.tp);
  const slippageBps=bps(expected,avg);
  const maxSlippageBps=Math.max(.5,n(env.BINANCE_EXEC_MAX_SLIPPAGE_BPS||6));
  const risk=Math.abs(avg-sl),reward=Math.abs(tp-avg),actualRR=risk>0?reward/risk:0;
  const minRR=Math.max(1,n(env.BINANCE_EXEC_MIN_POSTFILL_RR||1.15));
  const slValid=side==="BUY"?sl<avg:sl>avg;
  const tpValid=side==="BUY"?tp>avg:tp<avg;
  if(slippageBps>maxSlippageBps)return {ok:false,reason:"POSTFILL_SLIPPAGE_TOO_HIGH",avgPrice:avg,expectedPrice:expected,slippageBps,maxSlippageBps,actualRR};
  if(!slValid||!tpValid)return {ok:false,reason:"POSTFILL_PROTECTION_INVALID",avgPrice:avg,sl,tp,actualRR};
  if(actualRR<minRR)return {ok:false,reason:"POSTFILL_RR_DEGRADED",avgPrice:avg,sl,tp,actualRR,minRR,slippageBps};
  return {ok:true,avgPrice:avg,sl,tp,actualRR,slippageBps};
}
