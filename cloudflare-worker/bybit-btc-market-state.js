// BTC-only non-indicator market-state engine.
// Strategy authority: price structure + executed flow + book/liquidity + derivatives positioning + realized volatility.
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const sum=a=>a.reduce((s,x)=>s+x,0);
const avg=a=>a.length?sum(a)/a.length:0;
const std=a=>{if(a.length<2)return 0;const m=avg(a);return Math.sqrt(avg(a.map(x=>(x-m)**2)));};

function rows(p={}){
  return [...(p?.result?.list||[])].reverse().map(x=>({t:num(x[0]),o:num(x[1]),h:num(x[2]),l:num(x[3]),c:num(x[4]),v:num(x[5]),turnover:num(x[6])})).filter(x=>x.c>0);
}
function closes(r=[]){return r.map(x=>x.c);}
function logReturns(r=[]){const c=closes(r),out=[];for(let i=1;i<c.length;i++)if(c[i-1]>0&&c[i]>0)out.push(Math.log(c[i]/c[i-1]));return out;}
function realizedVol(r=[],n=24){const x=logReturns(r).slice(-n);return std(x)*Math.sqrt(Math.max(1,x.length));}
function efficiency(r=[],n=24){const c=closes(r).slice(-Math.max(3,n));if(c.length<3)return 0;const path=sum(c.slice(1).map((x,i)=>Math.abs(x-c[i])));return path>0?Math.abs(c.at(-1)-c[0])/path:0;}
function direction(r=[],n=18){const c=closes(r).slice(-Math.max(4,n));if(c.length<4)return 0;const net=c.at(-1)-c[0],noise=sum(c.slice(1).map((x,i)=>Math.abs(x-c[i])));return noise>0?net/noise:0;}
function recentRange(r=[],n=24){const x=r.slice(-n);if(!x.length)return {hi:0,lo:0,width:0};const hi=Math.max(...x.map(z=>z.h)),lo=Math.min(...x.map(z=>z.l));return {hi,lo,width:Math.max(0,hi-lo)};}
function structure(r=[]){
  if(r.length<16)return {bias:0,hh:false,hl:false,ll:false,lh:false,breakUp:false,breakDown:false};
  const a=r.slice(-16,-8),b=r.slice(-8),ahi=Math.max(...a.map(x=>x.h)),alo=Math.min(...a.map(x=>x.l)),bhi=Math.max(...b.map(x=>x.h)),blo=Math.min(...b.map(x=>x.l)),last=b.at(-1)?.c||0;
  const hh=bhi>ahi,hl=blo>alo,ll=blo<alo,lh=bhi<ahi,breakUp=last>ahi,breakDown=last<alo;
  const bias=(breakUp||(hh&&hl))?1:(breakDown||(ll&&lh))?-1:0;
  return {bias,hh,hl,ll,lh,breakUp,breakDown,priorHigh:ahi,priorLow:alo,recentHigh:bhi,recentLow:blo};
}
function sweepState(r=[]){
  if(r.length<24)return {upSweep:false,downSweep:false};
  const prior=r.slice(-24,-2),x=r.at(-1),hi=Math.max(...prior.map(z=>z.h)),lo=Math.min(...prior.map(z=>z.l));
  return {upSweep:x.h>hi&&x.c<hi,downSweep:x.l<lo&&x.c>lo,priorHigh:hi,priorLow:lo};
}
function bookState(book={}){
  const d=book?.result||{},bids=(d.b||[]).slice(0,25),asks=(d.a||[]).slice(0,25),bidNotional=bids.map(x=>num(x[0])*num(x[1])),askNotional=asks.map(x=>num(x[0])*num(x[1])),bid=sum(bidNotional),ask=sum(askNotional),den=bid+ask;
  const bb=num(bids[0]?.[0]),bs=num(bids[0]?.[1]),ba=num(asks[0]?.[0]),as=num(asks[0]?.[1]),topDen=bs+as;
  return {bidDepth:bid,askDepth:ask,imbalance:den>0?(bid-ask)/den:0,bestBid:bb,bestAsk:ba,spreadBps:bb>0&&ba>bb?(ba-bb)/((ba+bb)/2)*10000:999,microprice:topDen>0?(ba*bs+bb*as)/topDen:(bb+ba)/2,updateTime:num(d.ts||book?.time)};
}
function tradeState(trades={}){
  const list=trades?.result?.list||[];let buy=0,sell=0,buyN=0,sellN=0;
  for(const x of list){const q=num(x.size||x.v),p=num(x.price||x.p),n=q*p;if(String(x.side||x.S)==="Buy"){buy+=q;buyN+=n;}else{sell+=q;sellN+=n;}}
  const den=buyN+sellN;return {buyQty:buy,sellQty:sell,buyNotional:buyN,sellNotional:sellN,deltaNotional:buyN-sellN,aggressorImbalance:den>0?(buyN-sellN)/den:0,trades:list.length};
}
function oiState(oi={}){const l=oi?.result?.list||[];if(!l.length)return {current:0,previous:0,deltaPct:0};const a=num(l[0]?.openInterest),b=num(l[1]?.openInterest||a);return {current:a,previous:b,deltaPct:b>0?(a-b)/b*100:0};}
function ratioState(ratio={}){const x=ratio?.result?.list?.[0]||{};return {buyRatio:num(x.buyRatio),sellRatio:num(x.sellRatio),timestamp:num(x.timestamp)};}
function tickerState(t={}){const x=t?.result?.list?.[0]||{};return {last:num(x.lastPrice),mark:num(x.markPrice),index:num(x.indexPrice),fundingRate:num(x.fundingRate),openInterest:num(x.openInterest),openInterestValue:num(x.openInterestValue),basis:num(x.basis),turnover24h:num(x.turnover24h)};}

export function classifyBtcRegime(s={}){
  const d15=num(s.structure15?.bias),d60=num(s.structure60?.bias),dir15=num(s.direction15),eff15=num(s.efficiency15),volRatio=num(s.volRatio),book=num(s.book?.imbalance),flow=num(s.trades?.aggressorImbalance),px=num(s.price),r=num(s.range15?.width),priorHi=num(s.structure15?.priorHigh),priorLo=num(s.structure15?.priorLow);
  if(volRatio>2.2)return "HIGH_VOL_SHOCK";
  const brokeUp=px>priorHi&&priorHi>0,brokeDn=px<priorLo&&priorLo>0;
  if(brokeUp&&flow>.08&&book>-.25)return "BREAKOUT_UP";
  if(brokeDn&&flow<-.08&&book<.25)return "BREAKOUT_DOWN";
  if(volRatio<.72&&eff15<.28)return "SQUEEZE";
  if(d15>0&&d60>=0&&dir15>.16&&eff15>.34)return "TREND_UP";
  if(d15<0&&d60<=0&&dir15<-.16&&eff15>.34)return "TREND_DOWN";
  if(eff15<.32&&r>0)return "RANGE";
  if((d15>0&&d60<0)||(d15<0&&d60>0))return "REVERSAL";
  return "TRANSITION";
}

export async function buildBtcMarketState(env,api,symbol="BTCUSDT"){
  const [k5,k15,k60,book,trades,oi,ratio,ticker]=await Promise.all([
    api.kline(symbol,"5",160),api.kline(symbol,"15",160),api.kline(symbol,"60",120),
    api.market("/v5/market/orderbook",{category:"linear",symbol,limit:50}),
    api.market("/v5/market/recent-trade",{category:"linear",symbol,limit:500}),
    api.market("/v5/market/open-interest",{category:"linear",symbol,intervalTime:"5min",limit:3}),
    api.market("/v5/market/account-ratio",{category:"linear",symbol,period:"5min",limit:3}),
    api.ticker(symbol)
  ]);
  const r5=rows(k5),r15=rows(k15),r60=rows(k60),b=bookState(book),tr=tradeState(trades),o=oiState(oi),ra=ratioState(ratio),tk=tickerState(ticker),rv5=realizedVol(r5,24),rvBase=realizedVol(r5,96),price=tk.last||((b.bestBid+b.bestAsk)/2);
  const state={symbol,at:Date.now(),price,mark:tk.mark,index:tk.index,fundingRate:tk.fundingRate,basis:tk.basis,turnover24h:tk.turnover24h,book:b,trades:tr,openInterest:o,longShort:ra,structure5:structure(r5),structure15:structure(r15),structure60:structure(r60),sweep5:sweepState(r5),sweep15:sweepState(r15),direction5:direction(r5,18),direction15:direction(r15,20),direction60:direction(r60,16),efficiency5:efficiency(r5,18),efficiency15:efficiency(r15,20),efficiency60:efficiency(r60,16),realizedVol5:rv5,realizedVolBase:rvBase,volRatio:rvBase>0?rv5/rvBase:1,range5:recentRange(r5,24),range15:recentRange(r15,24),range60:recentRange(r60,24)};
  state.regime=classifyBtcRegime(state);
  state.crowding={longHeavy:ra.buyRatio>.58||tk.fundingRate>.00035,shortHeavy:ra.sellRatio>.58||tk.fundingRate<-.00035,oiExpanding:o.deltaPct>.25,oiContracting:o.deltaPct<-.25};
  state.quality={freshBook:Date.now()-b.updateTime<5000||b.updateTime===0,spreadOk:b.spreadBps<=8,liquid:tk.turnover24h>0};
  return state;
}

export const BTC_MARKET_STATE_VERSION="BTC_MARKET_STATE_V1";
