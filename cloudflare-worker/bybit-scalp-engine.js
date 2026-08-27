import {bybitAutoConfig,BYBIT_AUTO_VERSION} from "./bybit-auto-config.js";
import {bybitV5,normalizeBybitFilter,floorStep} from "./bybit-v5-client.js";
import {symbolProfile} from "./binance-symbol-profiles.js";
import {buildScalpExitPlan} from "./binance-scalp-exit.js";
import {scalpContext,scalpConfluence} from "./binance-scalp-context.js";
import {adaptiveThreshold,assessPortfolioCorrelation,betaCluster,classifyRegime,edgeStatsFor,loadAdaptiveLearning,selectExitProfile} from "./bybit-adaptive-edge.js";

const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0,last=a=>a[a.length-1],clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function ema(a,n){if(!a.length)return 0;const k=2/(n+1);let e=a[0];for(let i=1;i<a.length;i++)e=a[i]*k+e*(1-k);return e;}
function atr(r,n=14){if(r.length<n+1)return 0;const t=[];for(let i=r.length-n;i<r.length;i++){const p=r[i-1][4];t.push(Math.max(r[i][2]-r[i][3],Math.abs(r[i][2]-p),Math.abs(r[i][3]-p)));}return avg(t);}
function parseK(p){const rows=p?.result?.list||[];return [...rows].reverse().map(x=>[Number(x[0]),Number(x[1]),Number(x[2]),Number(x[3]),Number(x[4]),Number(x[5])]).filter(x=>x.slice(1).every(Number.isFinite));}
function interval(tf){const s=String(tf||"1m").toLowerCase();if(s.endsWith("m"))return String(Math.max(1,parseInt(s)||1));if(s.endsWith("h"))return String(Math.max(1,(parseInt(s)||1)*60));return "1";}
function returnsFromRows(r=[]){const c=r.map(x=>Number(x[4])).filter(Number.isFinite),out=[];for(let i=1;i<c.length;i++)if(c[i-1]>0&&c[i]>0)out.push((c[i]-c[i-1])/c[i-1]);return out.slice(-70);}
async function instrumentMap(api){let cursor="",all=[];for(let i=0;i<4;i++){const p=await api.instruments(cursor),r=p?.result||{};all.push(...(r.list||[]));cursor=String(r.nextPageCursor||"");if(!cursor)break;}return new Map(all.map(x=>[x.symbol,x]));}
async function liquidUniverse(env,api,filters){const minCount=Math.max(50,Number(env.BYBIT_MIN_UNIVERSE_COUNT||50)),minTurnover=Math.max(1000000,Number(env.BYBIT_MIN_TURNOVER_24H_USD||5000000)),maxSpread=Math.max(2,Number(env.BYBIT_MAX_UNIVERSE_SPREAD_BPS||12)),t=await api.tickers(),out=[];for(const x of t?.result?.list||[]){const symbol=String(x.symbol||"").toUpperCase(),f=filters.get(symbol);if(!f||f.status!=="Trading"||f.contractType!=="LinearPerpetual"||f.settleCoin!=="USDT")continue;const bid=Number(x.bid1Price),ask=Number(x.ask1Price),mid=(bid+ask)/2,turnover=Number(x.turnover24h||0),spread=mid>0?(ask-bid)/mid*10000:Infinity;if(!(bid>0&&ask>bid)||turnover<minTurnover||spread>maxSpread)continue;out.push({symbol,turnover24h:turnover,spreadBps:spread,bid,ask});}out.sort((a,b)=>b.turnover24h-a.turnover24h);return {ok:out.length>=minCount,reason:out.length>=minCount?null:"INSUFFICIENT_LIQUID_UNIVERSE",count:out.length,symbols:out.map(x=>x.symbol),metrics:out};}

function analyze(symbol,r1,r5,bid,ask,cfg,metrics,learningSummary={}){
 const profile=symbolProfile(symbol,{quoteVolume:metrics.turnover24h,spreadBps:metrics.spreadBps}),c1=r1.map(x=>x[4]),c5=r5.map(x=>x[4]),p=(bid+ask)/2,a1=atr(r1,profile.atrPeriod),a5=atr(r5,profile.atrPeriod),eFast=ema(c1,profile.emaFast),eSlow=ema(c1,profile.emaSlow),ctxFast=ema(c5,profile.ctxFast),ctxSlow=ema(c5,profile.ctxSlow),spreadBps=(ask-bid)/p*10000,atrPct=a1/p*100;
 if(!(a1>0)||atrPct<cfg.filters.minAtrPct||atrPct>cfg.filters.maxAtrPct||spreadBps>profile.maxSpreadBps)return null;
 const c=last(r1),pr=r1[r1.length-2],trend=ctxFast>ctxSlow?1:ctxFast<ctxSlow?-1:0,impUp=c[4]>c[1]&&c[4]>pr[2],impDn=c[4]<c[1]&&c[4]<pr[3],near=Math.min(Math.abs(p-eFast),Math.abs(p-eSlow))<=a1*.60,look=r1.slice(-26,-3),hi=Math.max(...look.map(x=>x[2])),lo=Math.min(...look.map(x=>x[3]));
 let side=null,setupType=null,score=0,breakout=false;
 if(trend>0&&near&&impUp){side="Buy";setupType="TREND_PULLBACK";score=78;}else if(trend<0&&near&&impDn){side="Sell";setupType="TREND_PULLBACK";score=78;}else if(c[4]>hi&&c[4]-hi<=a1*profile.maxChaseAtr){side="Buy";setupType="BREAKOUT";score=75;breakout=true;}else if(c[4]<lo&&lo-c[4]<=a1*profile.maxChaseAtr){side="Sell";setupType="BREAKOUT";score=75;breakout=true;}if(!side)return null;
 const sideUpper=side==="Buy"?"BUY":"SELL",ctx=scalpContext(r1,p,a1),conf=scalpConfluence(sideUpper,ctx,{breakout}),vwapAligned=ctx.vwap>0&&(side==="Buy"?p>=ctx.vwap:p<=ctx.vwap);
 if(vwapAligned)score+=4;else if(ctx.distanceFromVwapAtr>1.6)score-=3;score+=conf.score;score+=clamp(Math.abs(ctxFast-ctxSlow)/Math.max(a5,1e-9)*8,0,10);
 if(breakout&&ctx.volumeRatio<1.05)return null;if(ctx.distanceFromVwapAtr>2.4)return null;
 const regimeState=classifyRegime({side,breakout,price:p,atr1:a1,atr5:a5,ctxFast,ctxSlow,r1,volumeRatio:ctx.volumeRatio});
 if((regimeState.regime==="TREND_UP"||regimeState.regime==="TREND_DOWN")&&!regimeState.directionFit)return null;
 const strategyBase=`SCALP:${profile.family}:${setupType}`,strategy=`${strategyBase}:${regimeState.regime}`,edge=edgeStatsFor(learningSummary,symbol,strategy,regimeState.regime),threshold=adaptiveThreshold({base:Math.max(Number(cfg.adaptive?.baseScore||70),Number(profile.minScore||70)),regime:regimeState.regime,strategy,edge,spreadBps});
 if(score<threshold.threshold)return null;
 const entry=side==="Buy"?ask:bid,exitPlan=buildScalpExitPlan({side:sideUpper,entry,atr:a1,r1,rrFloor:Number(cfg.risk.minRR||1),preferredRR:Number(cfg.risk.preferredRR||2),rrCap:Number(cfg.risk.maxRR||5)});if(!exitPlan||Number(exitPlan.rr||0)<cfg.risk.minRR)return null;
 const exitSelection=selectExitProfile(edge,regimeState.regime),edgeConfidence=Number(threshold.confidence||0),edgeNetR=Number(edge?.avgNetR??edge?.avgR??0),rankingScore=score-threshold.threshold+clamp(edgeNetR*3,-3,3)*edgeConfidence+Math.min(3,Number(exitPlan.rr||0));
 return {symbol,side,strategy,strategyBase,setupType,profile:profile.family,score:Math.round(score),adaptiveThreshold:threshold.threshold,rankingScore,entry,sl:exitPlan.sl,tp:exitPlan.tp,rr:exitPlan.rr,atr1:a1,spreadBps,exitPlan,regime:regimeState.regime,regimeState,betaCluster:betaCluster(symbol),exitProfile:exitSelection.profile,exitProfileReason:exitSelection.reason,edge:{trades:Number(edge?.trades||0),winRate:edge?.winRate??null,avgR:edge?.avgR??null,avgNetR:edge?.avgNetR??null,avgMfeR:edge?.avgMfeR??null,avgMaeR:edge?.avgMaeR??null,confidence:edgeConfidence},returns1m:returnsFromRows(r1),context:{...ctx,vwapAligned,confluence:conf.reasons},liquidity:{turnover24h:metrics.turnover24h,spreadBps:metrics.spreadBps}};
}

export async function scanBybitAuto(env){
 const cfg=bybitAutoConfig(env),api=bybitV5(env),[imap,learning]=await Promise.all([instrumentMap(api),loadAdaptiveLearning(env)]),filters=new Map([...imap].map(([s,x])=>[s,normalizeBybitFilter(x)])),universe=await liquidUniverse(env,api,filters);
 if(!universe.ok)return {version:BYBIT_AUTO_VERSION,best:null,candidates:[],universe,reason:universe.reason,adaptive:{enabled:true},scannedAt:Date.now()};
 const mm=new Map(universe.metrics.map(x=>[x.symbol,x])),out=[],errors=[],concurrency=Math.max(4,Math.min(16,Number(env.BYBIT_SCAN_CONCURRENCY||8)));
 for(let i=0;i<universe.symbols.length;i+=concurrency){const batch=universe.symbols.slice(i,i+concurrency),rows=await Promise.all(batch.map(async symbol=>{const f=filters.get(symbol),m=mm.get(symbol);try{const profile=symbolProfile(symbol,{quoteVolume:m.turnover24h,spreadBps:m.spreadBps}),[k1,k5]=await Promise.all([api.kline(symbol,interval(profile.tfFast),160),api.kline(symbol,interval(profile.tfContext),160)]),setup=analyze(symbol,parseK(k1),parseK(k5),m.bid,m.ask,cfg,m,learning?.summary||{});return setup?{...setup,filters:f}:null;}catch(e){errors.push({symbol,error:String(e?.message||e).slice(0,140)});return null;}}));for(const r of rows)if(r)out.push(r);}
 out.sort((a,b)=>b.rankingScore-a.rankingScore||b.score-a.score||b.rr-a.rr||b.liquidity.turnover24h-a.liquidity.turnover24h);
 let positions=[];if(String(env.BYBIT_AUTO_LIVE||"").toLowerCase()==="true"){try{positions=(await api.positions())?.result?.list?.filter(x=>Number(x.size||0)>0)||[];}catch(e){return {version:BYBIT_AUTO_VERSION,best:null,candidates:out,universe:{ok:true,count:universe.count,symbols:universe.symbols},analyzed:universe.symbols.length,qualified:out.length,reason:"CORRELATION_POSITION_FETCH_FAILED",adaptive:{enabled:true,regime:true,perSymbolEdge:true,correlation:true,autoPromote:false},errors:[...errors,{symbol:"PORTFOLIO",error:String(e?.message||e).slice(0,140)}].slice(0,20),scannedAt:Date.now()};}}
 const eligible=[],correlationRejected=[];
 for(const candidate of out){if(positions.some(p=>String(p.symbol)===candidate.symbol))continue;const correlation=await assessPortfolioCorrelation(api,candidate,positions,{soft:cfg.adaptive?.correlationSoft,hard:cfg.adaptive?.correlationHard});const enriched={...candidate,correlation};if(correlation.ok)eligible.push(enriched);else correlationRejected.push({symbol:candidate.symbol,side:candidate.side,reason:correlation.reason,maxCorrelation:correlation.maxCorrelation,checks:correlation.checks});}
 return {version:BYBIT_AUTO_VERSION,best:eligible[0]||null,candidates:eligible,rawCandidates:out.length,universe:{ok:true,count:universe.count,symbols:universe.symbols},analyzed:universe.symbols.length,qualified:eligible.length,correlationRejected:correlationRejected.slice(0,12),adaptive:{enabled:true,regime:true,perSymbolEdge:true,adaptiveThresholdBounds:[64,82],correlationSoft:cfg.adaptive?.correlationSoft,correlationHard:cfg.adaptive?.correlationHard,netExpectancy:true,exitProfiles:true,autoPromote:false},errors:errors.slice(0,20),scannedAt:Date.now()};
}

export function sizeBybitAuto(setup,cfg,equityUsd=50){
  const f=setup.filters||{},equity=Math.max(0,Number(equityUsd||0)),entry=Number(setup.entry||0),sl=Number(setup.sl||0),structureTp=Number(setup.tp||0);
  const base=Math.max(1,Number(cfg.risk.baseBalanceUsd||50)),stepUsd=Math.max(1,Number(cfg.risk.balanceStepUsd||10));
  const scaleEquity=Math.round(equity*100)/100,delta=scaleEquity-base,signedSteps=delta>=0?Math.floor((delta+1e-9)/stepUsd):Math.ceil((delta-1e-9)/stepUsd);
  const minRiskFloor=Math.max(3,Number(cfg.risk.minRiskUsd||3)),absoluteMinReward=Math.max(.25,Number(cfg.risk.minRewardUsd||3));
  const hardMaxRewardUsd=Math.max(absoluteMinReward,Math.min(10,Number(cfg.risk.maxRewardUsd||10)));
  const rawRiskLadderUsd=Math.max(minRiskFloor,Number(cfg.risk.baseRiskUsd||5)+signedSteps*Number(cfg.risk.riskStepUsd||1));
  const rawMaxRewardUsd=Number(cfg.risk.baseRewardUsd||8)+signedSteps*Number(cfg.risk.rewardStepUsd||1);
  const ladderMaxRewardUsd=Math.min(hardMaxRewardUsd,Math.max(absoluteMinReward,rawMaxRewardUsd));
  const requestedMinRewardUsd=Math.max(absoluteMinReward,Number(cfg.risk.baseMinRewardUsd||5)+signedSteps*Number(cfg.risk.minRewardStepUsd||1));
  const ladderMinRewardUsd=Math.min(ladderMaxRewardUsd,requestedMinRewardUsd);
  const minRR=Math.max(1,Number(cfg.risk.minRR||1.5));
  const rrCompatibleRiskCapUsd=ladderMaxRewardUsd/minRR;
  const ladderMaxLossUsd=Math.max(minRiskFloor,Math.min(rawRiskLadderUsd,rrCompatibleRiskCapUsd));
  const requestedEffectiveRiskUsd=Math.max(minRiskFloor,Number(cfg.risk.baseMinEffectiveRiskUsd||3)+signedSteps*Number(cfg.risk.effectiveRiskStepUsd||1));
  const ladderMinEffectiveRiskUsd=Math.min(ladderMaxLossUsd,requestedEffectiveRiskUsd);
  const equityRiskCapUsd=equity*Number(cfg.risk.maxRiskPctOfEquity||8)/100;
  const riskBudgetUsd=Math.min(ladderMaxLossUsd,equityRiskCapUsd),dist=Math.abs(entry-sl);
  if(!(equity>0&&entry>0&&dist>0&&riskBudgetUsd>0))return {ok:false,reason:"RISK_BUDGET_OR_GEOMETRY_INVALID",riskBudgetUsd,equityUsd:equity,riskLadderStep:signedSteps};
  if(riskBudgetUsd+1e-9<minRiskFloor)return {ok:false,reason:"ACCOUNT_TOO_SMALL_FOR_3USD_SL_FLOOR",riskBudgetUsd,equityRiskCapUsd,minRiskFloor,equityUsd:equity,riskLadderStep:signedSteps};
  const configuredMax=Math.max(1,Number(cfg.maxLeverage||10)),symbolMax=Number(f.maxLeverage||0)>0?Math.min(configuredMax,Number(f.maxLeverage)):configuredMax,symbolMin=Math.max(1,Number(f.minLeverage||1));
  const leverage=Math.max(symbolMin,symbolMax);
  const reservePct=clamp(Number(cfg.risk.minFreeReservePct||20),15,40),feeBufferPct=clamp(Number(cfg.risk.feeBufferPct||5),2,12);
  const slotCeilingPct=Math.min(Number(cfg.risk.maxMarginPerPositionPct||40),100-reservePct);
  const grossMarginBudgetUsd=equity*slotCeilingPct/100,marginBudgetUsd=grossMarginBudgetUsd*(1-feeBufferPct/100);
  const riskQty=riskBudgetUsd/dist,capitalQty=marginBudgetUsd*leverage/entry;
  const qty=floorStep(Math.min(riskQty,capitalQty,Number(f.maxQty||Infinity)),Number(f.qtyStep||0)),notional=qty*entry;
  if(!(qty>=Number(f.minQty||0))||notional<Math.max(5,Number(f.minNotional||5)))return {ok:false,reason:"MIN_NOTIONAL_OR_QTY",qty,notional,riskBudgetUsd,marginBudgetUsd,riskLadderStep:signedSteps};
  const initialMarginUsd=notional/leverage;
  if(initialMarginUsd>marginBudgetUsd+1e-9)return {ok:false,reason:"PER_POSITION_MARGIN_CAP",qty,notional,leverage,initialMarginUsd,marginBudgetUsd,equityUsd:equity};
  const riskUsd=qty*dist,structureRewardUsd=structureTp>0?qty*Math.abs(structureTp-entry):Infinity;
  if(riskUsd+1e-9<ladderMinEffectiveRiskUsd)return {ok:false,reason:"EFFECTIVE_RISK_TOO_SMALL",qty,notional,riskUsd,riskBudgetUsd,ladderMinEffectiveRiskUsd,initialMarginUsd,marginBudgetUsd,capitalLimited:capitalQty<riskQty,riskLadderStep:signedSteps};
  if(riskUsd+1e-9<minRiskFloor)return {ok:false,reason:"SL_RISK_BELOW_3USD_HARD_FLOOR",qty,notional,riskUsd,minRiskFloor,riskLadderStep:signedSteps};
  if(structureRewardUsd+1e-9<ladderMinRewardUsd)return {ok:false,reason:"STRUCTURE_REWARD_BELOW_LADDER_MIN",qty,notional,riskUsd,structureRewardUsd,ladderMinRewardUsd,ladderMaxRewardUsd,riskLadderStep:signedSteps};
  const rewardUsd=Math.min(ladderMaxRewardUsd,structureRewardUsd),targetRR=riskUsd>0?rewardUsd/riskUsd:null;
  if(rewardUsd>hardMaxRewardUsd+1e-9)return {ok:false,reason:"TP_REWARD_ABOVE_10USD_HARD_CAP",rewardUsd,hardMaxRewardUsd};
  if(!(riskUsd>0&&rewardUsd>=ladderMinRewardUsd&&targetRR>=minRR))return {ok:false,reason:"SIZED_RR_BELOW_MIN",qty,notional,riskUsd,rewardUsd,targetRR,structureRewardUsd,ladderMinRewardUsd,ladderMaxRewardUsd,hardMaxRewardUsd};
  return {ok:true,qty,notional,riskUsd,riskBudgetUsd,rewardUsd,rewardBudgetUsd:ladderMaxRewardUsd,structureRewardUsd,targetRR,riskLadderStep:signedSteps,rawRiskLadderUsd,ladderMaxLossUsd,ladderMinEffectiveRiskUsd,requestedEffectiveRiskUsd,ladderMinRewardUsd,ladderMaxRewardUsd,hardMaxRewardUsd,rrCompatibleRiskCapUsd,equityRiskCapUsd,equityUsd:equity,scaleEquityUsd:scaleEquity,scaleRule:"PLUS_MINUS_1_USD_PER_10_USD_EQUITY_FROM_50_USD_BASE",leverage,requiredLeverage:leverage,maxLeverage:symbolMax,capitalMode:"BALANCE_SCALED_TP_SL_BAND_ALLOCATOR_V184",reservePct,feeBufferPct,slotMarginPct:slotCeilingPct,grossMarginBudgetUsd,marginBudgetUsd,initialMarginUsd,capitalLimited:capitalQty<riskQty,riskUtilizationPct:riskBudgetUsd>0?riskUsd/riskBudgetUsd*100:null,marginUtilizationPct:marginBudgetUsd>0?initialMarginUsd/marginBudgetUsd*100:null,adaptive:{regime:setup.regime||null,betaCluster:setup.betaCluster||null,exitProfile:setup.exitProfile||"BALANCED",threshold:setup.adaptiveThreshold||null,edge:setup.edge||null,correlation:setup.correlation||null}};
}
