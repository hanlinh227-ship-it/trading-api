const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;

export const ADAPTIVE_EDGE_VERSION="ADAPTIVE_EDGE_V1_3_SHRUNK_NET_PNL";
export const REGIMES=["TREND_UP","TREND_DOWN","RANGE","BREAKOUT_EXPANSION","HIGH_VOL_CHAOS","LOW_VOL_COMPRESSION"];

function returns(closes=[]){const out=[];for(let i=1;i<closes.length;i++){const a=Number(closes[i-1]),b=Number(closes[i]);if(a>0&&b>0)out.push((b-a)/a);}return out;}
function pearson(a=[],b=[]){const n=Math.min(a.length,b.length);if(n<20)return null;const x=a.slice(-n),y=b.slice(-n),mx=avg(x),my=avg(y);let cov=0,vx=0,vy=0;for(let i=0;i<n;i++){const dx=x[i]-mx,dy=y[i]-my;cov+=dx*dy;vx+=dx*dx;vy+=dy*dy;}const d=Math.sqrt(vx*vy);return d>0?cov/d:null;}
function parseK(p){const rows=p?.result?.list||[];return [...rows].reverse().map(x=>Number(x[4])).filter(Number.isFinite);}

export function betaCluster(symbol=""){
 const s=String(symbol).toUpperCase();
 if(/^BTC/.test(s))return "BTC_BETA";
 if(/^(ETH|ENA|LDO|ARB|OP)/.test(s))return "ETH_ECOSYSTEM";
 if(/^(SOL|JUP|JTO|PYTH|WIF|BONK)/.test(s))return "SOL_ECOSYSTEM";
 if(/^(DOGE|SHIB|PEPE|FLOKI|WIF|BONK|BRETT|MOG)/.test(s))return "MEME_HIGH_BETA";
 if(/^(SUI|APT|SEI|TIA|INJ|AVAX|NEAR|ATOM|DOT)/.test(s))return "ALT_L1_HIGH_BETA";
 if(/^(XRP|XLM|ADA|TRX|TON)/.test(s))return "LARGE_ALT";
 return "GENERAL_ALT";
}

export function classifyRegime({side,breakout=false,price,atr1,atr5,ctxFast,ctxSlow,r1=[],volumeRatio=1}){
 const p=Math.max(Number(price)||0,1e-12),a1=Math.max(Number(atr1)||0,1e-12),a5=Math.max(Number(atr5)||0,a1),trendStrength=Math.abs(Number(ctxFast||0)-Number(ctxSlow||0))/a5,atrPct=a1/p*100;
 const recent=r1.slice(-12),older=r1.slice(-36,-12),rangeAvg=a=>avg(a.map(x=>Math.max(0,Number(x?.[2]||0)-Number(x?.[3]||0))));
 const recentRange=rangeAvg(recent),olderRange=Math.max(rangeAvg(older),1e-12),rangeRatio=recentRange/olderRange,vol=Number(volumeRatio||1);
 let regime;
 if(atrPct>2.0||rangeRatio>2.15)regime="HIGH_VOL_CHAOS";
 else if(breakout&&rangeRatio>1.20&&vol>=1.03)regime="BREAKOUT_EXPANSION";
 else if(rangeRatio<.68&&vol<.92)regime="LOW_VOL_COMPRESSION";
 else if(trendStrength<.31)regime="RANGE";
 else regime=Number(ctxFast)>Number(ctxSlow)?"TREND_UP":"TREND_DOWN";
 const directionFit=regime==="TREND_UP"?(side==="Buy"):regime==="TREND_DOWN"?(side==="Sell"):true;
 return {regime,trendStrength,atrPct,rangeRatio,volumeRatio:vol,directionFit};
}

export function parseRegimeFromStrategy(strategy=""){
 const parts=String(strategy).split(":");const last=parts.at(-1);return REGIMES.includes(last)?last:null;
}

export function learningConfidence(trades=0){const n=Math.max(0,Number(trades)||0);if(n<10)return 0;if(n<30)return .25;if(n<80)return .60;return 1;}
function shrunkEdge(edge=null,priorTrades=20){
 const n=Math.max(0,Number(edge?.trades||0)),prior=Math.max(10,Number(priorTrades||20)),wins=Math.max(0,Number(edge?.wins||0));
 const rawWr=Number(edge?.netWinRate??edge?.winRate??.5),rawNet=Number(edge?.avgNetR??0),weight=n/(n+prior);
 const wr=Number.isFinite(wins)&&n>0?(wins+prior*.5)/(n+prior):.5+(Number.isFinite(rawWr)?rawWr-.5:0)*weight;
 const avgNetR=(Number.isFinite(rawNet)?rawNet:0)*weight;
 return {trades:n,priorTrades:prior,weight,rawWinRate:Number.isFinite(rawWr)?rawWr:null,shrunkWinRate:wr,rawAvgNetR:Number.isFinite(rawNet)?rawNet:null,shrunkAvgNetR:avgNetR};
}

export function adaptiveThreshold({base=68,regime="RANGE",strategy="",edge=null,spreadBps=0,priorTrades=20}){
 let penalty=0;
 if(regime==="HIGH_VOL_CHAOS")penalty+=6;
 else if(regime==="RANGE"&&String(strategy).includes("BREAKOUT"))penalty+=4;
 else if(regime==="LOW_VOL_COMPRESSION"&&String(strategy).includes("TREND_PULLBACK"))penalty+=2;
 else if(regime==="BREAKOUT_EXPANSION"&&String(strategy).includes("BREAKOUT"))penalty-=2;
 const spread=Number(spreadBps||0);if(spread>10)penalty+=3;else if(spread>8)penalty+=1;
 const conf=learningConfidence(edge?.trades||0),shrunk=shrunkEdge(edge,priorTrades),avgNetR=shrunk.shrunkAvgNetR,wr=shrunk.shrunkWinRate;
 let edgeModifier=0;
 if(conf>0){edgeModifier+=clamp(-avgNetR*4,-4,4)*conf;edgeModifier+=clamp((.5-wr)*6,-2,2)*conf;}
 const threshold=clamp(Math.round((Number(base)||68)+penalty+edgeModifier),66,84);
 return {threshold,base:Number(base)||68,regimePenalty:penalty,edgeModifier,confidence:conf,sampleSize:Number(edge?.trades||0),bounded:[66,84],learningAuthority:"STRICT_NET_PNL_V2",shrinkage:shrunk};
}

export function edgeKey(symbol,strategy,regime){return `${String(symbol||"").toUpperCase()}|${String(strategy||"")}|${String(regime||"")}`;}
export function edgeStatsFor(summary={},symbol,strategy,regime){
 const exact=summary?.bySymbolStrategyRegime?.[edgeKey(symbol,strategy,regime)];if(exact)return exact;
 return summary?.bySymbol?.[String(symbol||"").toUpperCase()]||null;
}

export function selectExitProfile(edge=null,regime="RANGE",minSamples=30){
 const n=Math.max(0,Number(edge?.trades||0)),conf=learningConfidence(n);if(n<Math.max(20,Number(minSamples||30)))return {profile:"BALANCED",confidence:conf,reason:"INSUFFICIENT_ROBUST_SAMPLE"};
 const mfe=Number(edge?.avgMfeR||0),mae=Number(edge?.avgMaeR||0),shrunk=shrunkEdge(edge,20),wr=shrunk.shrunkWinRate;
 if(["TREND_UP","TREND_DOWN","BREAKOUT_EXPANSION"].includes(regime)&&mfe>=1.7&&mae<=.8)return {profile:"TREND_RUNNER",confidence:conf,reason:"PROVEN_MFE",shrinkage:shrunk};
 if((mfe>0&&mfe<1.05)||(wr>0&&wr<.44))return {profile:"DEFENSIVE",confidence:conf,reason:"LOW_NET_EXTENSION",shrinkage:shrunk};
 return {profile:"BALANCED",confidence:conf,reason:"DEFAULT_BOUNDED",shrinkage:shrunk};
}

export async function loadAdaptiveLearning(env){
 try{return await env.TRADING_STATE?.get("bybit:learning:v2:state",{type:"json"})||{summary:{},dataIntegrityVersion:"BYBIT_LEARNING_NET_PNL_V2"};}catch{return {summary:{},dataIntegrityVersion:"BYBIT_LEARNING_NET_PNL_V2"};}
}

export async function assessPortfolioCorrelation(api,candidate,positions=[],opts={}){
 const hard=Number(opts.hard??.94),soft=Number(opts.soft??.84),sameSide=(positions||[]).filter(p=>String(p.side)===String(candidate.side)&&String(p.symbol)!==String(candidate.symbol));
 if(!sameSide.length)return {ok:true,maxCorrelation:null,checks:[],reason:"NO_SAME_SIDE_EXPOSURE"};
 const candidateReturns=Array.isArray(candidate.returns1m)?candidate.returns1m:[];const checks=[];
 for(const p of sameSide.slice(0,3)){
  try{const k=await api.kline(String(p.symbol),"1",70),r=returns(parseK(k)),corr=pearson(candidateReturns,r),clusterMatch=betaCluster(p.symbol)===betaCluster(candidate.symbol);checks.push({symbol:p.symbol,correlation:corr,clusterMatch});}
  catch{checks.push({symbol:p.symbol,correlation:null,clusterMatch:betaCluster(p.symbol)===betaCluster(candidate.symbol)});}
 }
 const finite=checks.map(x=>x.correlation).filter(Number.isFinite),maxCorrelation=finite.length?Math.max(...finite):null;
 if(Number.isFinite(maxCorrelation)&&maxCorrelation>=hard)return {ok:false,reason:"CORRELATION_HARD_CAP",maxCorrelation,hard,soft,checks};
 const clusterStack=checks.some(x=>x.clusterMatch&&Number.isFinite(x.correlation)&&x.correlation>=soft);
 if(clusterStack)return {ok:false,reason:"CORRELATION_CLUSTER_CAP",maxCorrelation,hard,soft,checks};
 return {ok:true,reason:Number.isFinite(maxCorrelation)&&maxCorrelation>=soft?"CORRELATION_SOFT_WARNING":"DIVERSIFIED",maxCorrelation,hard,soft,checks};
}
