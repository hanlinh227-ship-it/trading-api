#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
CW=ROOT/'cloudflare-worker'

def must(text,needle,label):
    if needle not in text: raise SystemExit(f'MISSING_ANCHOR:{label}')

def write(path,text):
    Path(path).write_text(text,encoding='utf-8')

# 1) Fix symbol strategy syntax introduced while it was still unreferenced.
p=CW/'bybit-symbol-strategy.js'; text=p.read_text()
for a,b in {
    "regime==='RANGE'?.86":"regime==='RANGE' ? .86",
    "regime==='REVERSAL'?.98":"regime==='REVERSAL' ? .98",
    "style==='RANGE'?.88":"style==='RANGE' ? .88",
    "p.style==='MOMENTUM'?.060":"p.style==='MOMENTUM' ? .060",
    "p.style==='BURST'?.058":"p.style==='BURST' ? .058",
    "p.style==='TREND'?.064":"p.style==='TREND' ? .064",
    "p.style==='RANGE'?.052":"p.style==='RANGE' ? .052",
    "tier==='PROBE'?.50":"tier==='PROBE' ? .50",
    "tier==='CONFIRM'?.88":"tier==='CONFIRM' ? .88",
}.items(): text=text.replace(a,b)
write(p,text)

# 2) Multi-asset config + larger, slower-to-cut profit envelope.
p=CW/'bybit-auto-config.js'; text=p.read_text()
if "bybit-coin-profiles.js" not in text:
    text="import {BYBIT_TRADE_UNIVERSE,BYBIT_PORTFOLIO_POLICY} from './bybit-coin-profiles.js';\n"+text
text=text.replace("// BYBIT-BTC-STATEFLOW-2.6 configuration.","// BYBIT-MULTI-STATEFLOW-3.0 configuration.")
text=text.replace("symbol:'BTCUSDT',category:'linear',settleCoin:'USDT',","symbol:'BTCUSDT',symbols:BYBIT_TRADE_UNIVERSE,multiAsset:true,portfolio:BYBIT_PORTFOLIO_POLICY,category:'linear',settleCoin:'USDT',")
text=text.replace("profitLockR:.40,\n    trailStartR:.98,\n    trailRange5Pct:.12,\n    trailPricePct:.00100,","profitLockR:.52,\n    trailStartR:1.18,\n    trailRange5Pct:.16,\n    trailPricePct:.00130,")
text=text.replace("probeBaseTargetR:1.70,\n      confirmBaseTargetR:1.92,\n      fullBaseTargetR:2.10,\n      minTargetR:1.25,\n      maxTargetR:2.55,\n      strongExtensionR:.40,\n      weakCompressionR:.24,\n      minTargetMoveR:.14,\n      minLiveGapR:.18,","probeBaseTargetR:1.85,\n      confirmBaseTargetR:2.20,\n      fullBaseTargetR:2.70,\n      minTargetR:1.30,\n      maxTargetR:4.80,\n      strongExtensionR:.65,\n      weakCompressionR:.18,\n      minTargetMoveR:.16,\n      minLiveGapR:.20,\n      peakGivebackActivationR:1.10,\n      peakGivebackR:.65,")
text=text.replace("maxSameDirectionPositions:1000000","maxSameDirectionPositions:3")
text=text.replace("decelerationLockMinR:.48,\n    decelerationPeakMinR:.65,","decelerationLockMinR:.70,\n    decelerationPeakMinR:.95,")
text=text.replace("shortHorizonFlowReversal:true,sampleQualityWeighted:true,tieredEntryRisk:true,adaptiveNativeTpSl:true","shortHorizonFlowReversal:true,sampleQualityWeighted:true,tieredEntryRisk:true,adaptiveNativeTpSl:true,multiAssetUniverse:true,perSymbolCognition:true,portfolioCorrelationGuard:true,peakGivebackProtection:true")
write(p,text)

# 3) Risk engine: global portfolio risk/margin contributions + fee-aware quantized sizing.
p=CW/'bybit-btc-risk-engine.js'; text=p.read_text()
text=text.replace("export function btcRiskDecision({cfg,equityUsd,state={},setup,markPrice,candidateInitialMarginUsd=0,candidateActualRiskUsd=0}){","export function btcRiskDecision({cfg,equityUsd,state={},setup,markPrice,candidateInitialMarginUsd=0,candidateActualRiskUsd=0,externalActiveRiskUsd=0,externalMarginUsd=0}){")
text=text.replace("active=activeRiskUsd(tranches),normalCap=","active=activeRiskUsd(tranches)+Math.max(0,num(externalActiveRiskUsd)),normalCap=")
text=text.replace("const marginCap=capital.capitalBaseUsd*scale.marginCapPct/100,openMargin=(tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN').reduce((s,t)=>s+Math.max(0,num(t.initialMarginUsd)),0),candidateMargin=","const marginCap=capital.capitalBaseUsd*scale.marginCapPct/100,openMargin=(tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN').reduce((s,t)=>s+Math.max(0,num(t.initialMarginUsd)),0)+Math.max(0,num(externalMarginUsd)),candidateMargin=")
start=text.index('export function sizeBtcSetup('); end=text.index('export function addTranche(',start)
new_size=r'''export function sizeBtcSetup({setup,riskUsd,maxRiskUsd=0,filters={},leverage=5,equityUsd=0,capitalBaseUsd=0,marginCapPct=78}){
  const entry=Math.max(0,num(setup?.entry)),stop=Math.abs(entry-num(setup?.sl)),target=Math.max(0,num(riskUsd));if(!(entry>0&&stop>0&&target>0))return {ok:false,reason:'STOP_OR_RISK_INVALID'};
  const step=Math.max(1e-12,num(filters.qtyStep)||.001),minQty=Math.max(step,num(filters.minQty)||step),maxQty=Math.max(minQty,num(filters.maxQty)||1e9),minNotional=Math.max(0,num(filters.minNotional)||5),capital=Math.max(0,num(capitalBaseUsd)||num(equityUsd)),lev=Math.max(1,num(leverage)),marginCapUsd=capital*clamp(num(marginCapPct)||78,30,84)/100,hardRiskCap=Math.max(target,num(maxRiskUsd)||target*1.20),strength=String(setup?.strength||'NORMAL'),tier=String(setup?.entryTier||'CONFIRM'),softMult=tier==='PROBE'?1.16:tier==='CONFIRM'?1.28:strength==='A_PLUS'?1.45:strength==='STRONG'?1.35:1.30,softRiskCap=Math.min(hardRiskCap,target*softMult),costBps=Math.max(0,num(setup?.cost?.totalCostBps||setup?.cost?.baseRoundTripCostBps)),unitCost=entry*costBps/10000,raw=target/stop;
  const minByNotional=ceilStep(minNotional/entry,step),minimum=Math.min(maxQty,Math.max(minQty,minByNotional)),maxByMargin=floorStep(marginCapUsd*lev/entry,step),maxByHard=floorStep(hardRiskCap/Math.max(1e-12,stop+unitCost),step),upper=Math.min(maxQty,maxByMargin,maxByHard),qs=new Set();
  const add=q=>{q=Math.min(maxQty,Math.max(minimum,Math.round(q/step)*step));if(q>=minimum-1e-12)qs.add(Number(q.toFixed(12)));};add(minimum);if(upper>=minimum-1e-12){const count=Math.floor((upper-minimum)/step+1e-9)+1;if(count<=400){for(let i=0;i<count;i++)add(minimum+i*step);}else{add(upper);const center=clamp(raw,minimum,upper);for(let k=-8;k<=8;k++)add(center+k*step);}}
  const candidates=[...qs].sort((a,b)=>a-b).map(q=>{const notional=q*entry,priceRisk=q*stop,initialMargin=notional/lev,costReserve=notional*costBps/10000;return {qty:q,notionalUsd:notional,actualRiskUsd:priceRisk,priceRiskUsd:priceRisk,costReserveUsd:costReserve,effectiveLossEstimateUsd:priceRisk+costReserve,initialMarginUsd:initialMargin,leverage:lev,capitalBaseUsd:capital,marginCapPct};});
  const feasible=candidates.filter(x=>x.actualRiskUsd<=softRiskCap+1e-9&&x.effectiveLossEstimateUsd<=hardRiskCap+1e-9&&x.initialMarginUsd<=marginCapUsd+1e-9);
  if(!feasible.length){const min=candidates[0];if(min&&min.effectiveLossEstimateUsd>hardRiskCap+1e-9)return {ok:false,reason:'MIN_QTY_EXCEEDS_HARD_EFFECTIVE_RISK_CAP',qty:min.qty,actualRiskUsd:min.actualRiskUsd,effectiveLossEstimateUsd:min.effectiveLossEstimateUsd,targetRiskUsd:target,softRiskCapUsd:softRiskCap,hardRiskCapUsd:hardRiskCap};if(min&&min.initialMarginUsd>marginCapUsd+1e-9)return {ok:false,reason:'POSITION_MARGIN_TOO_LARGE',qty:min.qty,initialMarginUsd:min.initialMarginUsd,marginCapUsd,marginCapPct,capitalBaseUsd:capital};return {ok:false,reason:'QUANTIZED_SIZE_OUTSIDE_ADAPTIVE_RISK_BAND',targetRiskUsd:target,softRiskCapUsd:softRiskCap,hardRiskCapUsd:hardRiskCap,candidates};}
  let chosen=[...feasible].sort((a,b)=>Math.abs(a.actualRiskUsd-target)-Math.abs(b.actualRiskUsd-target))[0];if(tier!=='PROBE'&&strength!=='NORMAL'){const balanced=feasible.filter(x=>x.actualRiskUsd>=target*.78).sort((a,b)=>Math.abs(a.actualRiskUsd-target)-Math.abs(b.actualRiskUsd-target));if(balanced.length)chosen=balanced[0];}
  return {ok:true,...chosen,targetRiskUsd:target,softRiskCapUsd:softRiskCap,hardRiskCapUsd:hardRiskCap,quantized:true,qtyStep:step,minQty,entryTier:tier,selectionPolicy:'FEE_AWARE_CONTINUOUS_QUANTIZED_NEAREST_TARGET_WITH_HARD_EFFECTIVE_RISK_AND_MARGIN_CAP'};
}

'''
text=text[:start]+new_size+text[end:]
text=text.replace("const tranches=Array.isArray(state.tranches)?[...state.tranches]:[],id=String(x.id||`BTC-","const tranches=Array.isArray(state.tranches)?[...state.tranches]:[],id=String(x.id||`${String(x.symbol||state.symbol||'BTCUSDT')}-")
text=text.replace("row={symbol:'BTCUSDT',status:'OPEN'","row={symbol:String(x.symbol||state.symbol||'BTCUSDT'),status:'OPEN'")
text=text.replace("BTC_RISK_RECYCLE_V7_TIERED_SMART_QUANTIZED_SIZING","BYBIT_RISK_RECYCLE_V8_PORTFOLIO_FEE_AWARE_SIZING")
write(p,text)

# 4) Generate a symbol-isolated engine from the proven BTC engine. Each symbol gets its own lexical SYMBOL and KV state key.
src=(CW/'bybit-btc-engine.js').read_text()
src=src.replace('import {selectBtcSetup} from "./bybit-btc-strategy.js";','import {selectBybitSymbolSetup as selectBtcSetup} from "./bybit-symbol-strategy.js";')
idx=src.index('const KEY='); imports=src[:idx]; body=src[idx:]
body=body.replace('const KEY="bybit:btc:hyperscale:v2:state";\nconst SYMBOL="BTCUSDT";\n','')
body=body.replace('export async function runBtcHyperscale(env,{entryBlockReason=null}={}){','async function runSymbol(env,{entryBlockReason=null,portfolioContext={}}={}){')
body=body.replace('export async function getBtcHyperscaleState(env){return get(env);}','async function getState(env){return get(env);}')
body=re.sub(r'export const BTC_HYPERSCALE_ENGINE_VERSION=.*?;\s*$','',body,flags=re.S)
body=body.replace('const foreign=foreignPositions(positions);','const foreign=[];')
body=body.replace('highWaterUsd:Math.max(equity,num(state.highWaterUsd)),lastEquityUsd:equity,','highWaterUsd:Math.max(equity,num(state.highWaterUsd),num(portfolioContext?.highWaterUsd)),lastEquityUsd:equity,lastWalletBalanceUsd:num(portfolioContext?.walletBalanceUsd)||num(state.lastWalletBalanceUsd)||equity,lastAvailableUsd:num(portfolioContext?.availableUsd)||num(state.lastAvailableUsd),symbol:SYMBOL,')
body=body.replace('btcRiskDecision({cfg,equityUsd:equity,state,setup,markPrice:market.mark||market.price})','btcRiskDecision({cfg,equityUsd:equity,state,setup,markPrice:market.mark||market.price,externalActiveRiskUsd:num(portfolioContext?.externalActiveRiskUsd),externalMarginUsd:num(portfolioContext?.externalMarginUsd)})')
body=body.replace('candidateInitialMarginUsd:sized.initialMarginUsd,candidateActualRiskUsd:sized.actualRiskUsd})','candidateInitialMarginUsd:sized.initialMarginUsd,candidateActualRiskUsd:sized.actualRiskUsd,externalActiveRiskUsd:num(portfolioContext?.externalActiveRiskUsd),externalMarginUsd:num(portfolioContext?.externalMarginUsd)})')
body=body.replace('let x=Math.min(base,num(p.max)||globalMax,globalMax);','let x=Math.min(base,num(p.max)||globalMax,globalMax);x*=clamp(num(setup?.coinProfile?.leverageMult)||1,.45,1.15);')
body=body.replace('state=addTranche(state,{orderId,side:setup.side,qty:f.qty,','state=addTranche(state,{symbol:SYMBOL,coinProfile:setup.coinProfile,orderId,side:setup.side,qty:f.qty,')
body=body.replace('BYBIT-BTC-HYPERSCALE-2.9-ULTRAFAST-TIERED','BYBIT-MULTI-ASSET-ENGINE-3.0-PROFILED')
# Profile-aware adaptive target so a strong trend target is not shrunk back to BTC defaults.
body=body.replace("function adaptiveTargetPlan(side,latest,mark,market,stability,cfg,d,tick,r){const ap=cfg?.scalp?.adaptiveProtection||{},tier=String(latest?.entryTier||\"CONFIRM\"),base=tier===\"PROBE\"?num(ap.probeBaseTargetR)||1.65:tier===\"FULL\"?num(ap.fullBaseTargetR)||2:num(ap.confirmBaseTargetR)||1.85,minR=Math.max(.8,num(ap.minTargetR)||1.15),maxR=Math.max(minR,num(ap.maxTargetR)||2.35),",
"function adaptiveTargetPlan(side,latest,mark,market,stability,cfg,d,tick,r){const ap=cfg?.scalp?.adaptiveProtection||{},tier=String(latest?.entryTier||\"CONFIRM\"),cp=latest?.coinProfile||{},targetMult=clamp(num(cp.targetMult)||1,.75,1.35),base=(tier===\"PROBE\"?num(ap.probeBaseTargetR)||1.85:tier===\"FULL\"?num(ap.fullBaseTargetR)||2.70:num(ap.confirmBaseTargetR)||2.20)*targetMult,minR=Math.max(.8,num(ap.minTargetR)||1.30),maxR=Math.min(Math.max(minR,num(ap.maxTargetR)||4.80),Math.max(minR,num(cp.runnerMaxR)||num(ap.maxTargetR)||4.80)),")
body=body.replace('state.positionPeakR=Math.max(num(state.positionPeakR),r);let desired=currentStop,phase=null;','state.positionPeakR=Math.max(num(state.positionPeakR),r);const cp=latest?.coinProfile||{},holdMult=clamp(num(cp.holdMult)||1,.75,1.50),peakGiveback=Math.max(.35,num(cfg?.scalp?.adaptiveProtection?.peakGivebackR)||.65)*holdMult,peakActivation=Math.max(.8,num(cfg?.scalp?.adaptiveProtection?.peakGivebackActivationR)||1.10);let desired=currentStop,phase=null;')
body=body.replace('phase="SCALP_TRAIL";}desired=roundTick(desired,filters.tickSize);','phase="SCALP_TRAIL";}if(state.positionPeakR>=peakActivation&&canNetLock&&r<=state.positionPeakR-peakGiveback){const lockPeakR=Math.max(.05,state.positionPeakR-peakGiveback),gap=Math.max(filters.tickSize*5,d*.10),raw=side==="Buy"?num(latest.entry)+d*lockPeakR:num(latest.entry)-d*lockPeakR,lock=side==="Buy"?Math.min(raw,mark-gap):Math.max(raw,mark+gap);desired=tighten(side,desired,lock);phase=phase||"PEAK_GIVEBACK_LOCK";}desired=roundTick(desired,filters.tickSize);')
wrapped=imports+"\nfunction createSymbolEngine(SYMBOL){\n  const KEY=SYMBOL==='BTCUSDT'?'bybit:btc:hyperscale:v2:state':`bybit:asset:${SYMBOL}:state`;\n"+body+"\n  return {runSymbol,getState};\n}\nconst ENGINE_CACHE=new Map();\nfunction norm(s){const x=String(s||'BTCUSDT').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');if(!x.endsWith('USDT'))throw new Error('BYBIT_SYMBOL_INVALID');return x;}\nfunction engineFor(symbol){const s=norm(symbol);if(!ENGINE_CACHE.has(s))ENGINE_CACHE.set(s,createSymbolEngine(s));return ENGINE_CACHE.get(s);}\nexport async function runBybitSymbolEngine(env,opts={}){const symbol=norm(opts.symbol||'BTCUSDT'),rest={...opts};delete rest.symbol;return engineFor(symbol).runSymbol(env,rest);}\nexport async function getBybitSymbolState(env,symbol='BTCUSDT'){return engineFor(norm(symbol)).getState(env);}\nexport async function runBtcHyperscale(env,opts={}){return runBybitSymbolEngine(env,{...opts,symbol:'BTCUSDT'});}\nexport async function getBtcHyperscaleState(env){return getBybitSymbolState(env,'BTCUSDT');}\nexport const BTC_HYPERSCALE_ENGINE_VERSION='BYBIT-MULTI-ASSET-ENGINE-3.0-PROFILED';\n"
write(CW/'bybit-symbol-engine.js',wrapped)

# 5) Multi-asset controller/orchestrator: rank whole universe cheaply, deep-evaluate only event/open/top liquid symbols.
controller=r'''import {runBybitSymbolEngine,getBybitSymbolState} from './bybit-symbol-engine.js';
import {reconcileBtcAccountBalance} from './bybit-btc-balance-reconciler.js';
import {bybitV5} from './bybit-v5-client.js';
import {bybitExecutionMode} from './bybit-auto-config.js';
import {telegramApiRequest} from './providers/telegram-client.js';
import {BYBIT_TRADE_UNIVERSE,BYBIT_PORTFOLIO_POLICY,coinProfileForSymbol,isSupportedTradeSymbol,maxConcurrentForEquity,correlationCapForEquity,normalizeBybitSymbol} from './bybit-coin-profiles.js';

const CONTROL_KEY='bybit:auto:v1:controller';const num=v=>Number.isFinite(Number(v))?Number(v):0;const iso=()=>new Date().toISOString();
async function get(env,k,d={}){try{return await env.TRADING_STATE?.get(k,{type:'json'})??d}catch{return d}}async function put(env,k,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(k,JSON.stringify(x));}
const openPos=p=>(p?.result?.list||[]).filter(x=>num(x.size)>0);const sym=x=>normalizeBybitSymbol(x?.symbol||'');
function positionRisk(x={}){const q=Math.abs(num(x.size)),e=num(x.avgPrice),sl=num(x.stopLoss),m=Math.max(0,num(x.positionIM));return sl>0&&e>0?q*Math.abs(e-sl):m*.60;}
function portfolioContext(positions,symbol,balance={}){const others=positions.filter(x=>sym(x)!==symbol),externalActiveRiskUsd=others.reduce((s,x)=>s+positionRisk(x),0),externalMarginUsd=others.reduce((s,x)=>s+Math.max(0,num(x.positionIM)),0);return {externalActiveRiskUsd,externalMarginUsd,highWaterUsd:num(balance?.state?.highWaterUsd),walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd)};}
function tickerRows(raw={}){return (raw?.result?.list||[]).map(x=>({symbol:normalizeBybitSymbol(x.symbol),last:num(x.lastPrice),bid:num(x.bid1Price),ask:num(x.ask1Price),turnover:num(x.turnover24h),change:num(x.price24hPcnt),oiValue:num(x.openInterestValue)}));}
function rankUniverse(rows=[]){return rows.filter(x=>isSupportedTradeSymbol(x.symbol)).map(x=>{const p=coinProfileForSymbol(x.symbol),mid=x.bid>0&&x.ask>0?(x.bid+x.ask)/2:x.last,spread=mid>0&&x.ask>x.bid?(x.ask-x.bid)/mid*10000:999,liquid=x.turnover>=num(p.minTurnoverUsd),spreadOk=spread<=num(p.maxSpreadBps),score=(num(p.priority)/100)*.34+Math.log10(Math.max(10,x.turnover))/12*.42+clamp(Math.abs(x.change)*4,0,.12)+clamp(Math.log10(Math.max(10,x.oiValue))/12,0,.12);return {...x,profile:p,spreadBps:spread,eligible:liquid&&spreadOk,score};}).sort((a,b)=>Number(b.eligible)-Number(a.eligible)||b.score-a.score);}
function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
function groupCount(positions,group){return positions.filter(x=>coinProfileForSymbol(sym(x))?.correlationGroup===group).length;}
function entryBlockFor({symbol,positions,equity,newEntryDone,ranked}){const p=coinProfileForSymbol(symbol),existing=positions.find(x=>sym(x)===symbol);if(!p)return 'SYMBOL_NOT_IN_MAJOR_CAP_UNIVERSE';if(existing)return newEntryDone?'EVENT_NEW_RISK_ALREADY_USED':null;const row=ranked.find(x=>x.symbol===symbol);if(row&&!row.eligible)return 'UNIVERSE_LIQUIDITY_OR_SPREAD_GATE';if(newEntryDone)return 'EVENT_NEW_RISK_ALREADY_USED';if(positions.length>=maxConcurrentForEquity(equity))return 'PORTFOLIO_CONCURRENT_POSITION_CAP';if(groupCount(positions,p.correlationGroup)>=correlationCapForEquity(equity))return 'PORTFOLIO_CORRELATION_CAP';return null;}
function compact(v){const n=num(v);return n>=100?n.toFixed(2):n>=1?n.toFixed(4):n.toFixed(6)}
async function sendEntry(env,r){if(!(r?.executed&&r?.mode==='LIVE'&&r?.plan))return null;const p=r.plan,s=String(p.symbol||r.market?.symbol||'BTCUSDT'),side=String(p.side)==='Buy'?'MUA':'BÁN',icon=side==='MUA'?'🟢':'🔴',net=num(p.plannedNetProfitUsd),risk=num(p.riskUsd);try{await telegramApiRequest(env,'sendMessage',{chat_id:env.TELEGRAM_CHAT_ID,parse_mode:'HTML',disable_web_page_preview:true,text:[`${icon} <b>${s.replace('USDT','')} ${side} · THẬT</b>`,`<code>VÀO ${compact(p.entry)} · TP ${compact(p.tp)} +$${Math.max(0,net).toFixed(2)} · SL ${compact(p.sl)} -$${Math.abs(risk).toFixed(2)}</code>`,`<code>${num(p.qty)} · ${num(p.leverage)}x · ${String(p.entryTier||'CONFIRM')}</code>`,`<i>${String(p.setup||'PROFILE_EDGE')} · ${String(p.regime||'')}</i>`].join('\n')});return {sent:true,symbol:s,orderId:p.orderId||null}}catch(e){return {sent:false,symbol:s,error:String(e?.message||e)}}}
async function sendLifecycle(env,r){const out=[];for(const x of r?.lifecycles||[]){if(!(x.cutExecuted||x.verdict==='CUT'||x.verdict==='TIGHTEN'))continue;const s=String(x.symbol||r.market?.symbol||'');const msg=x.cutExecuted||x.verdict==='CUT'?`✂️ <b>${s.replace('USDT','')} CẮT CÓ XÁC NHẬN</b>\n<code>${compact(x.markPrice)} · R ${num(x.r).toFixed(2)}</code>`:`🛡️ <b>${s.replace('USDT','')} ${String(x.phase||'BẢO VỆ')}</b>\n<code>SL ${compact(x.nextSl)} · R ${num(x.r).toFixed(2)}</code>`;try{await telegramApiRequest(env,'sendMessage',{chat_id:env.TELEGRAM_CHAT_ID,text:msg,parse_mode:'HTML'});out.push({sent:true,symbol:s,action:x.verdict})}catch(e){out.push({sent:false,symbol:s,error:String(e?.message||e)})}}return out;}

export async function runBybitMultiAssetControlled(env,opts={}){const mode=bybitExecutionMode(env),api=bybitV5(env),balance=await reconcileBtcAccountBalance(env),equity=num(balance?.snapshot?.equityUsd)||num(balance?.state?.lastEquityUsd);let positions=openPos(await api.positions()),ranked=rankUniverse(tickerRows(await api.tickers())),eventSymbol=normalizeBybitSymbol(opts.symbol||'BTCUSDT');if(!isSupportedTradeSymbol(eventSymbol))eventSymbol='BTCUSDT';const unmanaged=positions.filter(x=>!isSupportedTradeSymbol(sym(x)));const openSymbols=[...new Set(positions.filter(x=>isSupportedTradeSymbol(sym(x))).map(sym))],deep=ranked.filter(x=>x.eligible).slice(0,Math.max(1,num(BYBIT_PORTFOLIO_POLICY.deepScanCount)||3)).map(x=>x.symbol),targets=[...new Set([...openSymbols,eventSymbol,...deep])],results=[];let newEntryDone=false;if(unmanaged.length){const ctl={executionMode:mode,multiAsset:true,lastCycleAt:iso(),lastCycleReason:'UNMANAGED_SYMBOL_POSITION_PRESENT',unmanagedPositions:unmanaged.map(x=>({symbol:x.symbol,side:x.side,size:num(x.size)})),universe:BYBIT_TRADE_UNIVERSE,runtimeRevision:String(env.RUNTIME_REVISION||'UNKNOWN')};await put(env,CONTROL_KEY,ctl);return {ok:false,mode,reason:'UNMANAGED_SYMBOL_POSITION_PRESENT',unmanagedPositions:unmanaged,controller:ctl,results:[]};}
for(const symbol of targets){const block=entryBlockFor({symbol,positions,equity,newEntryDone,ranked}),ctx=portfolioContext(positions,symbol,balance),r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:block,portfolioContext:ctx});results.push(r);if(r?.executed){newEntryDone=true;positions=openPos(await api.positions());}await sendEntry(env,r);await sendLifecycle(env,r);}
const active=positions.map(x=>({symbol:x.symbol,side:x.side,size:num(x.size),avgPrice:num(x.avgPrice),markPrice:num(x.markPrice),unrealisedPnl:num(x.unrealisedPnl),stopLoss:num(x.stopLoss),takeProfit:num(x.takeProfit),leverage:num(x.leverage),positionIM:num(x.positionIM)})),best=ranked.find(x=>x.eligible)||null,last=results.at(-1)||{},previous=await get(env,CONTROL_KEY,{}),ctl={...previous,executionMode:mode,requestedLive:String(env.BYBIT_AUTO_LIVE||'').toLowerCase()==='true',btcLiveAck:String(env.BYBIT_BTC_LIVE_ACK||'').toLowerCase()==='true',liveAuthority:mode==='LIVE'?'MULTI_ASSET_MAJOR_CAP':'PAPER',multiAsset:true,legacyMultiCoinDisabled:false,eventDriven:true,timeGate:false,sessionGate:false,cooldownGate:false,unlimitedDailyEntries:true,maxNewEntriesPerEvent:1,decisionAuthority:'VPS_WS_MARKET_STATE_CHANGE',profileAuthority:'PER_SYMBOL_COGNITION_V1',portfolioAuthority:BYBIT_PORTFOLIO_POLICY.authority,universe:BYBIT_TRADE_UNIVERSE,lastEventSymbol:eventSymbol,activePositions:active,activePositionCount:active.length,maxConcurrent:maxConcurrentForEquity(equity),rankedUniverse:ranked.slice(0,8).map(x=>({symbol:x.symbol,eligible:x.eligible,score:Number(x.score.toFixed(4)),spreadBps:Number(x.spreadBps.toFixed(3)),turnover24h:x.turnover,style:x.profile.style})),bestUniverseSymbol:best?.symbol||null,equityUsd:equity,walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd),lastCycleAt:iso(),lastCycleReason:String(last?.reason||'MULTI_ASSET_CYCLE_COMPLETE'),lastCycleExecuted:results.some(x=>x?.executed),lastSymbolResults:results.slice(-5).map(x=>({symbol:x?.market?.symbol||x?.plan?.symbol||null,reason:x?.reason||null,executed:!!x?.executed,regime:x?.market?.regime||null,setup:x?.scan?.best?.setup||null,entryTier:x?.scan?.best?.entryTier||null})),runtimeRevision:String(env.RUNTIME_REVISION||'UNKNOWN')};await put(env,CONTROL_KEY,ctl);return {ok:true,mode,multiAsset:true,eventSymbol,equity,universe:BYBIT_TRADE_UNIVERSE,ranked:ctl.rankedUniverse,activePositions:active,results,controller:ctl};}
export async function getMultiAssetControllerState(env){return get(env,CONTROL_KEY,{});}
export const BYBIT_MULTI_ASSET_CONTROLLER_VERSION='BYBIT_MULTI_ASSET_CONTROLLER_V1_EVENT_DRIVEN';
'''
write(CW/'bybit-multi-asset-controller.js',controller)

# 6) Control plane becomes symbol-aware and no longer treats legitimate universe positions as foreign blockers.
control=r'''import {getBybitSymbolState} from './bybit-symbol-engine.js';
import {runBybitMultiAssetControlled,getMultiAssetControllerState} from './bybit-multi-asset-controller.js';
import {buildBtcMarketState} from './bybit-btc-market-state.js';
import {selectBybitSymbolSetup} from './bybit-symbol-strategy.js';
import {bybitCredentials,bybitExecutionMode} from './bybit-auto-config.js';
import {bybitV5} from './bybit-v5-client.js';
import {BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';
import {BYBIT_TRADE_UNIVERSE,isSupportedTradeSymbol,normalizeBybitSymbol} from './bybit-coin-profiles.js';
const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});const on=v=>String(v||'').toLowerCase()==='true';
function authState(req,env){const action=String(env.GPT_5AI_ACTION_KEY||''),bridge=String(env.V11_AI_BRIDGE_SECRET||env.BYBIT_VPS_BRIDGE_SECRET||''),raw=String(req.headers.get('x-action-key')||req.headers.get('authorization')||''),got=raw.replace(/^Bearer\s+/i,''),source=got&&action&&got===action?'ACTION_KEY':got&&bridge&&got===bridge?'VPS_BRIDGE_SECRET':null;return {ok:!!source,source,actionKeyPresent:!!action,bridgeKeyPresent:!!bridge,requestKeyPresent:!!got};}function unauthorized(req,env){const a=authState(req,env);return json({ok:false,error:'unauthorized',authDiagnostics:{actionKeyPresent:a.actionKeyPresent,bridgeKeyPresent:a.bridgeKeyPresent,requestKeyPresent:a.requestKeyPresent}},401);}
async function runtimePreflight(env){const mode=bybitExecutionMode(env),creds=bybitCredentials(env),enabled=on(env.BYBIT_AUTO_ENABLED),btcAck=on(env.BYBIT_BTC_LIVE_ACK),requestedLive=on(env.BYBIT_AUTO_LIVE),api=bybitV5(env);let account=null,positions=[],orders=[],accountError=null;try{const [w,p,o]=await Promise.all([api.wallet(),api.positions(),api.openOrders()]),acct=w?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==='USDT')||{};account={totalEquity:Number(acct.totalEquity||coin.equity||0),walletBalance:Number(acct.totalWalletBalance||coin.walletBalance||0),availableBalance:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0),initialMargin:Number(acct.totalInitialMargin||0)};positions=(p?.result?.list||[]).filter(x=>Number(x.size||0)>0).map(x=>({symbol:x.symbol,side:x.side,size:Number(x.size),avgPrice:Number(x.avgPrice||0),stopLoss:Number(x.stopLoss||0),takeProfit:Number(x.takeProfit||0),unrealisedPnl:Number(x.unrealisedPnl||0)}));orders=(o?.result?.list||[]).filter(x=>!['Filled','Cancelled','Rejected','Deactivated'].includes(String(x.orderStatus)));}catch(e){accountError=String(e?.message||e);}const unmanaged=positions.filter(x=>!isSupportedTradeSymbol(x.symbol)),blockers=[];if(requestedLive&&!btcAck)blockers.push('LIVE_ACK_MISSING');if(!enabled)blockers.push('BYBIT_ENGINE_DISABLED');if(!(creds.apiKey&&creds.apiSecret))blockers.push('BYBIT_CREDENTIALS_MISSING');if(!account||!(account.totalEquity>0))blockers.push('LIVE_ACCOUNT_UNAVAILABLE');if(unmanaged.length)blockers.push('UNMANAGED_SYMBOL_POSITION_PRESENT');return {ok:blockers.length===0,exchange:'BYBIT',version:BYBIT_AUTO_VERSION,mode,requestedLive,btcLiveAck:btcAck,enabled,multiAsset:true,universe:BYBIT_TRADE_UNIVERSE,eventDriven:true,timeGate:false,scheduledExecution:false,decisionAuthority:'VPS_WS_MARKET_STATE_CHANGE',entryTriggerAuthority:'VPS_BRIDGE_SECRET_ONLY',credentialSource:creds.source,account,accountError,positions,openOrders:orders.length,unmanagedPositions:unmanaged,blockers,runtimeRevision:String(env.RUNTIME_REVISION||'UNKNOWN'),checkedAt:new Date().toISOString()};}
async function scan(env,symbol){const s=normalizeBybitSymbol(symbol||'BTCUSDT');if(!isSupportedTradeSymbol(s))return {ok:false,reason:'SYMBOL_NOT_IN_MAJOR_CAP_UNIVERSE',symbol:s};const api=bybitV5(env),market=await buildBtcMarketState(env,api,s),selected=selectBybitSymbolSetup(market);return {ok:true,exchange:'BYBIT',version:BYBIT_AUTO_VERSION,symbol:s,market,selected,eventDriven:true,timeGate:false,execution:false,scannedAt:new Date().toISOString()};}
export async function handleBybitControlApi(req,env){const u=new URL(req.url);if(u.pathname==='/bybit/auth/health'&&req.method==='GET'){const a=authState(req,env);return json({ok:true,exchange:'BYBIT',authDiagnostics:{actionKeyPresent:a.actionKeyPresent,bridgeKeyPresent:a.bridgeKeyPresent,requestKeyPresent:a.requestKeyPresent,authorized:a.ok,source:a.source},entryTriggerAuthority:'VPS_BRIDGE_SECRET_ONLY'});}if(u.pathname==='/bybit/entry-health'&&req.method==='GET'){try{const p=await runtimePreflight(env);return json({...p,status:p.ok?'BYBIT_MULTI_ENTRY_INFRA_READY':'BYBIT_MULTI_ENTRY_BLOCKED',strategyAuthority:'PER_SYMBOL_STATEFLOW_COGNITION'},p.ok?200:503)}catch(e){return json({ok:false,reason:'BYBIT_ENTRY_HEALTH_FAILED',error:String(e?.message||e)},502)}}if(u.pathname==='/bybit/runtime/preflight'&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);const p=await runtimePreflight(env);return json(p,p.ok?200:503)}if(u.pathname==='/bybit/scan'&&req.method==='GET'){try{return json(await scan(env,u.searchParams.get('symbol')||'BTCUSDT'))}catch(e){return json({ok:false,reason:'BYBIT_SCAN_FAILED',error:String(e?.message||e)},502)}}if(u.pathname==='/bybit/auto/state'&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);const symbol=normalizeBybitSymbol(u.searchParams.get('symbol')||'BTCUSDT');return json({ok:true,exchange:'BYBIT',version:BYBIT_AUTO_VERSION,symbol,state:await getBybitSymbolState(env,symbol),controller:await getMultiAssetControllerState(env)})}if(u.pathname==='/bybit/auto/run'&&req.method==='POST'){const a=authState(req,env);if(!a.ok)return unauthorized(req,env);if(a.source!=='VPS_BRIDGE_SECRET')return json({ok:false,reason:'BYBIT_ENTRY_TRIGGER_REQUIRES_VPS_WS_DRIVER'},409);if(!on(env.BYBIT_AUTO_ENABLED))return json({ok:false,reason:'BYBIT_ENGINE_DISABLED'},409);const symbol=normalizeBybitSymbol(req.headers.get('x-bybit-symbol')||'BTCUSDT');try{return json({exchange:'BYBIT',triggerSource:a.source,eventDriven:true,...(await runBybitMultiAssetControlled(env,{symbol}))})}catch(e){return json({ok:false,exchange:'BYBIT',reason:'BYBIT_MULTI_AUTO_RUN_FAILED',error:String(e?.message||e)},502)}}if(['/bybit/ai/health','/bybit/learning/state','/bybit/evolution/build'].includes(u.pathname))return json({ok:false,error:'RETIRED_LEGACY_COMPONENT',replacement:'BYBIT_MULTI_ASSET_STATEFLOW'},410);return null;}
'''
write(CW/'bybit-control-plane.js',control)

# 7) Runtime contract + index advertise the real multi-asset authority.
runtime=r'''import {BYBIT_TRADE_UNIVERSE} from './bybit-coin-profiles.js';
export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_MULTI_ASSET_RUNTIME_V13_PROFILED_STATEFLOW';
export const BYBIT_AUTO_VERSION='BYBIT-MULTI-STATEFLOW-3.0';
export const BYBIT_EXECUTION_AUTHORITY='BYBIT_MAJOR_CAP_MULTI_ASSET';
export const BYBIT_PRIVATE_TRANSPORT='VPS_BYBIT_PRIVATE_PROXY';
export const BYBIT_MARKET_TRANSPORT='VPS_BYBIT_MARKET_PROXY';
export const BYBIT_HEALTH_ROUTE='/bybit/health';
export const TELEGRAM_HUB_ID='BYBIT_MULTI_ASSET_TRADING_HUB';
export const LEGACY_SIGNAL_RUNTIME_DISABLED=true;export const LEGACY_BYBIT_MULTI_COIN_DISABLED=false;export const LEGACY_FOREX_DISABLED=true;export const LEGACY_MEME_DISABLED=true;export const LEGACY_AI_COUNCIL_DISABLED=true;
export const BYBIT_RUNTIME_CONTRACT={version:BYBIT_RUNTIME_CONTRACT_VERSION,autoVersion:BYBIT_AUTO_VERSION,executionAuthority:BYBIT_EXECUTION_AUTHORITY,privateTransport:BYBIT_PRIVATE_TRANSPORT,marketTransport:BYBIT_MARKET_TRANSPORT,healthRoute:BYBIT_HEALTH_ROUTE,telegramHub:TELEGRAM_HUB_ID,legacySignalRuntimeDisabled:true,legacyBybitMultiCoinDisabled:false,legacyForexDisabled:true,legacyMemeDisabled:true,legacyAiCouncilDisabled:true,symbol:'MULTI',symbols:BYBIT_TRADE_UNIVERSE,market:'LINEAR_PERPETUAL',multiAsset:true,universeAuthority:'MAJOR_CAP_PLUS_BYBIT_LIQUIDITY_ALLOWLIST',strategyAuthority:'PER_SYMBOL_COGNITION_STATE_FIRST_FLOW_STRUCTURE_LIQUIDITY_DERIVATIVES',profileAuthority:'PER_SYMBOL_COGNITION_V1',portfolioAuthority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V1',autonomous:true,eventDriven:true,decisionAuthority:'VPS_WS_MARKET_STATE_CHANGE',entryTriggerAuthority:'VPS_BRIDGE_SECRET_ONLY',marketScanAuthority:'EVENT_DRIVEN_RANK_THEN_DEEP_SCAN',openPositionManagement:'EVENT_DRIVEN_PER_SYMBOL',cronRole:'NONE_EVENT_DRIVER_ONLY',scheduledExecution:false,timeGate:false,sessionGate:false,cooldownGate:false,timedPause:false,lossStreakTimeGate:false,strategyCooldown:'NONE',dailyTradeQuota:'NONE',microstructureWindows:'1S_3S_5S_15S_60S',entryTierAuthority:'PROBE_CONFIRM_FULL',continuousScale:true,riskAuthority:'GLOBAL_PORTFOLIO_RISK_PLUS_PER_SYMBOL_PROFILE',leverageAuthority:'EQUITY_TAPERED_PROFILED_LEVERAGE',scalpAuthority:'REGIME_AND_PROFILE_ADAPTIVE_NET_EDGE',peakGivebackProtection:true,adaptiveOrderRouting:true,plannedNetProfitFloor:true,nativeTpAlways:true,costAwareProfitLock:true,positionExitAuthority:'MULTI_STAGE_STRUCTURE_FLOW_STABILITY_EXIT',instabilityExit:true,reentryAuthority:'FRESH_THESIS_ONLY',recoveryMartingale:false,recoveryAddToLoser:false,runtimeSwitchDeploymentPolicy:'PRESERVE_EXISTING',liveAckDeploymentPolicy:'PRESERVE_EXISTING',liveAckCompatibility:'BYBIT_BTC_LIVE_ACK_IS_GLOBAL_BYBIT_LIVE_ACK'};
'''
write(CW/'bybit-runtime-contract.js',runtime)
index=r'''import autoHub from './bybit-auto-hub.js';
import {handleBybitReadonlyHealth} from './bybit-readonly-health.js';
import {handleBybitControlApi} from './bybit-control-plane.js';
import {BYBIT_AUTO_VERSION,bybitExecutionMode} from './bybit-auto-config.js';
import {BYBIT_RUNTIME_CONTRACT,BYBIT_EXECUTION_AUTHORITY,TELEGRAM_HUB_ID,BYBIT_HEALTH_ROUTE} from './bybit-runtime-contract.js';
import {BYBIT_TRADE_UNIVERSE} from './bybit-coin-profiles.js';
const VERSION=BYBIT_AUTO_VERSION,SERVICE='Bybit Major-Cap Multi-Asset StateFlow';const envBool=v=>String(v||'').toLowerCase()==='true';const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});const RETIRED_PREFIXES=['/v11/','/forex/','/meme-auto/','/binance/','/hyro/'];
export default {async fetch(req,env,ctx){const h=await handleBybitReadonlyHealth(req,env);if(h)return h;const c=await handleBybitControlApi(req,env);if(c)return c;const hub=await autoHub.fetch(req,env,ctx);if(hub)return hub;const u=new URL(req.url);if(u.pathname==='/runtime/contract')return json({ok:true,...BYBIT_RUNTIME_CONTRACT,runtimeRevision:String(env.RUNTIME_REVISION||'')});if(u.pathname==='/status')return json({ok:true,version:VERSION,service:SERVICE,executionAuthority:BYBIT_EXECUTION_AUTHORITY,runtimeContract:BYBIT_RUNTIME_CONTRACT,telegramHub:TELEGRAM_HUB_ID,legacyBotsDisabled:true,bybit:{multiAsset:true,symbols:BYBIT_TRADE_UNIVERSE,market:'LINEAR_PERPETUAL',mode:bybitExecutionMode(env),enabled:envBool(env.BYBIT_AUTO_ENABLED),requestedLive:envBool(env.BYBIT_AUTO_LIVE),liveAck:envBool(env.BYBIT_BTC_LIVE_ACK),readonlyHealth:BYBIT_HEALTH_ROUTE,strategyAuthority:'PER_SYMBOL_COGNITION_STATEFLOW',decisionTrigger:'VPS_WS_MARKET_STATE_CHANGE',scheduledExecution:false,timeGate:false,hardDailyTradeQuota:false,martingale:false,addToLoser:false,winnerPyramiding:true}});if(RETIRED_PREFIXES.some(p=>u.pathname.startsWith(p))||['/mcp','/mcp/health','/gpt-5ai/action','/internal/multi-ai/review','/bybit/ai/latest-review'].includes(u.pathname))return json({ok:false,error:'RETIRED_OLD_BOT_ROUTE',replacement:'BYBIT_MULTI_ASSET_STATEFLOW',authority:BYBIT_EXECUTION_AUTHORITY},410);return json({ok:false,error:'BYBIT_HUB_ENDPOINT_NOT_FOUND',runtimeContract:'/runtime/contract'},404);}};
'''
write(CW/'index.js',index)

# 8) Microstructure client must reject cross-symbol data instead of ever feeding BTC book to an alt.
p=CW/'bybit-btc-microstructure-client.js'; text=p.read_text()
text=text.replace("if(!r.ok)return null;const j=await r.json().catch(()=>null);return j?.ok?j:null;","if(!r.ok)return null;const j=await r.json().catch(()=>null),got=String(j?.data?.symbol||j?.result?.symbol||'').toUpperCase();if(got&&got!==String(symbol).toUpperCase())return null;return j?.ok?j:null;")
text=text.replace("export const BTC_MICROSTRUCTURE_CLIENT_VERSION='BTC_VPS_MICROSTRUCTURE_CLIENT_V1';","export const BTC_MICROSTRUCTURE_CLIENT_VERSION='BYBIT_MULTI_SYMBOL_VPS_MICROSTRUCTURE_CLIENT_V2';")
write(p,text)

# 9) Bridge: one proven Microstructure object per symbol. Event symbols are a liquid subset; all profiles still have live WS microstructure for deep scans.
p=ROOT/'bybit-live-bridge/bybit_live_bridge.py'; text=p.read_text()
text=text.replace("SYMBOL='BTCUSDT'","DEFAULT_SYMBOL='BTCUSDT'\nDEFAULT_SYMBOLS='BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,SOLUSDT,TRXUSDT,DOGEUSDT,ADAUSDT,LINKUSDT,AVAXUSDT,LTCUSDT,BCHUSDT,XLMUSDT,DOTUSDT,NEARUSDT,UNIUSDT,AAVEUSDT,HBARUSDT'\nSYMBOLS=tuple(dict.fromkeys(x.strip().upper() for x in os.environ.get('BYBIT_MULTI_SYMBOLS',DEFAULT_SYMBOLS).split(',') if x.strip()))\nEVENT_SYMBOLS=set(x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS','BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT').split(',') if x.strip())\nWORKER_WAKE_SEMAPHORE=threading.Semaphore(1)")
cs=text.index('class Microstructure:'); ce=text.index('\nMICRO=Microstructure()',cs); cls=text[cs:ce]
cls=cls.replace('SYMBOL','self.symbol')
cls=cls.replace('def __init__(self):','def __init__(self,symbol):\n        self.symbol=str(symbol).upper()')
cls=cls.replace("name='bybit-btc-public-ws'","name=f'bybit-{self.symbol.lower()}-public-ws'")
cls=cls.replace("f'header = \"x-btc-trigger: VPS_WS_EVENT\"',f'header = \"x-btc-trigger-reason: {reason}\"',","f'header = \"x-btc-trigger: VPS_WS_EVENT\"',f'header = \"x-bybit-symbol: {self.symbol}\"',f'header = \"x-btc-trigger-reason: {reason}\"',")
cls=cls.replace("'x-action-key':SECRET,'x-btc-trigger':'VPS_WS_EVENT','x-btc-trigger-reason':str(reason)[:120]})","'x-action-key':SECRET,'x-btc-trigger':'VPS_WS_EVENT','x-bybit-symbol':self.symbol,'x-btc-trigger-reason':str(reason)[:120]})")
cls=cls.replace('def _wake_worker(self,reason):\n        self.event_last_wake=', 'def _wake_worker(self,reason):\n        WORKER_WAKE_SEMAPHORE.acquire()\n        self.event_last_wake=')
cls=cls.replace("if rerun:self._spawn_wake('COALESCED_LATEST_STATE')","WORKER_WAKE_SEMAPHORE.release()\n            if rerun:self._spawn_wake('COALESCED_LATEST_STATE')")
cls=cls.replace('def _maybe_wake(self,topic):\n        fp=', "def _maybe_wake(self,topic):\n        if self.symbol not in EVENT_SYMBOLS:return\n        fp=")
cls=cls.replace("return {'integrated':True,","return {'symbol':self.symbol,'integrated':True,")
text=text[:cs]+cls+text[ce:]
text=text.replace('MICRO=Microstructure()','MICROS={s:Microstructure(s) for s in SYMBOLS}')
old="""        if u.path=='/health':
            snap=MICRO.snapshot();return self.sendj(200,{'ok':True,'service':'BYBIT_BTC_LIVE_BRIDGE','privateProxy':True,'microstructure':{'ready':bool(snap.get('ok')),'connected':bool(snap.get('connected')),'reason':snap.get('reason'),'error':snap.get('error')},'eventDriver':MICRO.event_status(),'legacyAiCouncil':False,'forex':False,'meme':False,'timestamp':int(time.time()*1000)})
        if u.path=='/bybit/microstructure':
            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
            q=urllib.parse.parse_qs(u.query);symbol=str((q.get('symbol') or [SYMBOL])[0]).upper()
            if symbol!=SYMBOL:return self.sendj(400,{'ok':False,'error':'BTCUSDT_ONLY'})
            snap=MICRO.snapshot();return self.sendj(200 if snap.get('ok') else 503,snap)
        return self.sendj(404,{'ok':False,'error':'NOT_FOUND'})"""
new="""        if u.path=='/health':
            snaps={s:m.snapshot() for s,m in MICROS.items()};ready=[s for s,x in snaps.items() if x.get('ok')];drivers={s:m.event_status() for s,m in MICROS.items()};btc=MICROS.get(DEFAULT_SYMBOL);return self.sendj(200,{'ok':True,'service':'BYBIT_MULTI_ASSET_LIVE_BRIDGE','privateProxy':True,'symbols':list(SYMBOLS),'readySymbols':ready,'eventSymbols':sorted(EVENT_SYMBOLS),'microstructure':{'ready':DEFAULT_SYMBOL in ready,'connected':bool(snaps.get(DEFAULT_SYMBOL,{}).get('connected'))},'eventDriver':btc.event_status() if btc else {},'eventDrivers':drivers,'legacyAiCouncil':False,'forex':False,'meme':False,'timestamp':int(time.time()*1000)})
        if u.path=='/bybit/microstructure':
            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
            q=urllib.parse.parse_qs(u.query);symbol=str((q.get('symbol') or [DEFAULT_SYMBOL])[0]).upper();m=MICROS.get(symbol)
            if not m:return self.sendj(400,{'ok':False,'error':'SYMBOL_NOT_IN_MULTI_ASSET_BRIDGE','symbol':symbol})
            snap=m.snapshot();return self.sendj(200 if snap.get('ok') else 503,snap)
        return self.sendj(404,{'ok':False,'error':'NOT_FOUND'})"""
if old not in text: raise SystemExit('BRIDGE_HANDLER_ANCHOR_MISSING')
text=text.replace(old,new,1)
text=text.replace("MICRO.start();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()","[m.start() for m in MICROS.values()];ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()")
text=text.replace('"""BTC-only Bybit VPS bridge.','"""Multi-asset Bybit VPS bridge.')
text=text.replace('Single BTCUSDT VPS authority','Single VPS authority')
write(p,text)

# 10) Replace validator with a compact multi-asset contract test.
validator=r'''import fs from 'node:fs';import assert from 'node:assert/strict';import {BYBIT_AUTO_CONFIG,bybitExecutionMode} from './bybit-auto-config.js';import {BYBIT_TRADE_UNIVERSE,BYBIT_COIN_PROFILES,BYBIT_PORTFOLIO_POLICY,coinProfileForSymbol} from './bybit-coin-profiles.js';import {selectBybitSymbolSetup} from './bybit-symbol-strategy.js';import {sizeBtcSetup} from './bybit-btc-risk-engine.js';
const read=f=>fs.readFileSync(f,'utf8'),cfg=BYBIT_AUTO_CONFIG;assert.ok(cfg.multiAsset);assert.ok(BYBIT_TRADE_UNIVERSE.length>=15);assert.equal(new Set(BYBIT_TRADE_UNIVERSE).size,BYBIT_TRADE_UNIVERSE.length);for(const s of BYBIT_TRADE_UNIVERSE){const p=coinProfileForSymbol(s);assert.ok(p&&p.symbol===s);assert.ok(['TREND','MOMENTUM','BURST','RANGE','BALANCED'].includes(p.style));assert.ok(p.riskMult>0&&p.riskMult<=1);assert.ok(p.runnerMaxR>=2.5);assert.ok(p.minTurnoverUsd>0);}assert.equal(cfg.risk.martingale,false);assert.equal(cfg.risk.gridRescue,false);assert.equal(cfg.risk.addToLoser,false);assert.equal(cfg.risk.pyramidWinner,true);assert.ok(cfg.risk.absoluteSingleEntryRiskPct<=1.6);assert.ok(cfg.risk.maxSameDirectionPositions<=3);assert.equal(cfg.scan.timeGate,false);assert.equal(cfg.scan.sessionGate,false);assert.equal(cfg.scan.cooldownGate,false);assert.equal(cfg.execution.noTimeGate,true);assert.equal(BYBIT_PORTFOLIO_POLICY.maxNewEntriesPerEvent,1);assert.equal(BYBIT_PORTFOLIO_POLICY.noDailyQuota,true);assert.ok(cfg.scalp.adaptiveProtection.maxTargetR>=4.5);assert.ok(cfg.scalp.trailStartR>=1);assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true'}),'PAPER');assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'LIVE');
const quant=sizeBtcSetup({setup:{side:'Buy',strength:'STRONG',entryTier:'FULL',entry:80000,sl:79900,cost:{totalCostBps:11}},riskUsd:.50,maxRiskUsd:.62,filters:{qtyStep:.001,minQty:.001,minNotional:5,maxQty:10},leverage:12,equityUsd:39,capitalBaseUsd:39,marginCapPct:78});assert.ok(quant.ok);assert.ok(quant.effectiveLossEstimateUsd<=quant.hardRiskCapUsd+1e-9);
const engine=read('bybit-symbol-engine.js'),controller=read('bybit-multi-asset-controller.js'),control=read('bybit-control-plane.js'),runtime=read('bybit-runtime-contract.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py'),strategy=read('bybit-symbol-strategy.js'),index=read('index.js');for(const x of ['createSymbolEngine','portfolioContext','externalActiveRiskUsd','PEAK_GIVEBACK_LOCK','BYBIT-MULTI-ASSET-ENGINE-3.0-PROFILED'])assert.ok(engine.includes(x),`ENGINE ${x}`);for(const x of ['rankUniverse','PORTFOLIO_CORRELATION_CAP','maxNewEntriesPerEvent:1','PER_SYMBOL_COGNITION_V1'])assert.ok(controller.includes(x),`CONTROLLER ${x}`);for(const x of ['BYBIT_TRADE_UNIVERSE','x-bybit-symbol','BYBIT_MULTI_ENTRY_INFRA_READY'])assert.ok(control.includes(x),`CONTROL ${x}`);for(const x of ['BYBIT_MULTI_ASSET_RUNTIME_V13_PROFILED_STATEFLOW','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST'])assert.ok(runtime.includes(x),`RUNTIME ${x}`);for(const x of ['BYBIT_MULTI_ASSET_LIVE_BRIDGE','BYBIT_MULTI_SYMBOLS','EVENT_SYMBOLS','self.symbol','x-bybit-symbol','WORKER_WAKE_SEMAPHORE'])assert.ok(bridge.includes(x),`BRIDGE ${x}`);assert.ok(strategy.includes('BYBIT_SYMBOL_COGNITION_V1_PROFILED_STATEFLOW'));assert.ok(index.includes('Bybit Major-Cap Multi-Asset StateFlow'));for(const old of ['claude','deepseek','codex','FOREX_CONNECTIVITY'])assert.ok(!bridge.toLowerCase().includes(old.toLowerCase()));
console.log('BYBIT_MULTI_ASSET_VALIDATION=PASS');console.log(JSON.stringify({version:'BYBIT-MULTI-STATEFLOW-3.0',symbols:BYBIT_TRADE_UNIVERSE.length,perSymbolCognition:true,portfolioRisk:true,correlationGuard:true,eventDriven:true,timeGate:false,dailyQuota:false,martingale:false,addToLoser:false,feeAwareSizing:true,profileAdaptiveTargets:true,peakGiveback:true},null,2));
'''
write(CW/'validate-btc-hyperscale.mjs',validator)

# 11) Bridge deployment workflow verifies representative symbols and serialized event wake.
bridgewf=r'''name: Deploy Bybit Multi-Asset Live Bridge
on:
  push:
    branches: [main]
    paths: ['bybit-live-bridge/**','.github/workflows/deploy-bybit-btc-bridge.yml']
  workflow_dispatch:
permissions: {contents: read}
concurrency: {group: bybit-multi-asset-live-bridge-production, cancel-in-progress: true}
jobs:
  deploy:
    runs-on: [self-hosted, trading-vps]
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
        with: {ref: main, fetch-depth: 1}
      - name: Validate multi-asset VPS authority
        shell: bash
        run: |
          set -euo pipefail
          python3 -m py_compile bybit-live-bridge/bybit_live_bridge.py
          test -f /etc/trading-v11-ai.env
          ! grep -qi 'claude\|codex\|deepseek\|FOREX_CONNECTIVITY' bybit-live-bridge/bybit_live_bridge.py
          grep -q 'BYBIT_MULTI_SYMBOLS' bybit-live-bridge/bybit_live_bridge.py
          grep -q 'WORKER_WAKE_SEMAPHORE' bybit-live-bridge/bybit_live_bridge.py
          grep -q 'x-bybit-symbol' bybit-live-bridge/bybit_live_bridge.py
      - name: Ensure WebSocket dependency
        run: |
          python3 -c 'import websocket' 2>/dev/null || python3 -m pip install --disable-pip-version-check --break-system-packages websocket-client
      - name: Install bridge
        run: |
          sudo install -m 0755 bybit-live-bridge/bybit_live_bridge.py /usr/local/bin/v11-manual-ai-bridge
          sudo systemctl disable --now bybit-btc-event-driver.service 2>/dev/null || true
          sudo systemctl daemon-reload
          sudo systemctl restart v11-manual-ai-bridge.service
          sudo systemctl is-active --quiet v11-manual-ai-bridge.service
      - name: Verify representative live WS symbols
        shell: bash
        run: |
          set -euo pipefail
          set -a; source /etc/trading-v11-ai.env; set +a
          for i in $(seq 1 60); do
            OK=1
            curl -fsS --max-time 8 http://127.0.0.1:8789/health >/tmp/bybit-multi-health.json || OK=0
            for S in BTCUSDT ETHUSDT SOLUSDT XRPUSDT LINKUSDT; do curl -fsS --max-time 8 -H "Authorization: Bearer $V11_AI_BRIDGE_SECRET" "http://127.0.0.1:8789/bybit/microstructure?symbol=$S" >"/tmp/$S.json" || OK=0; done
            if [ "$OK" = 1 ] && python3 - <<'PY'
          import json,time
          h=json.load(open('/tmp/bybit-multi-health.json'));assert h.get('ok') is True and h.get('service')=='BYBIT_MULTI_ASSET_LIVE_BRIDGE';assert len(h.get('symbols') or [])>=15
          now=int(time.time()*1000)
          for s in ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','LINKUSDT']:
            d=json.load(open('/tmp/'+s+'.json'));x=d.get('data') or {};t=x.get('trades') or {};b=x.get('book') or {};assert x.get('symbol')==s and x.get('source')=='VPS_BYBIT_WS';assert t.get('lastPrice',0)>0 and b.get('bestBid',0)>0 and b.get('bestAsk',0)>0;assert now-int(t.get('lastTradeTime',0))<8000
          PY
            then exit 0; fi
            sleep 1
          done
          cat /tmp/bybit-multi-health.json || true
          journalctl -u v11-manual-ai-bridge.service -n 120 --no-pager || true
          exit 1
      - name: Verify event wake reaches Worker
        shell: bash
        run: |
          set -euo pipefail
          for i in $(seq 1 90); do
            curl -fsS --max-time 15 https://trading-v77-scanner.hanlinh227.workers.dev/bybit/entry-health >/tmp/bybit-entry.json || true
            curl -fsS --max-time 8 http://127.0.0.1:8789/health >/tmp/bybit-multi-health.json || true
            if python3 - <<'PY' 2>/dev/null
          import json
          h=json.load(open('/tmp/bybit-multi-health.json'));e=json.load(open('/tmp/bybit-entry.json'));d=h.get('eventDriver') or {};assert d.get('lastSuccessAt',0)>0 and d.get('lastHttpStatus')==200;assert e.get('multiAsset') is True and len(e.get('universe') or [])>=15
          PY
            then echo BYBIT_MULTI_ASSET_EVENT_WAKE=PASS; exit 0; fi
            sleep 1
          done
          exit 1
'''
write(ROOT/'.github/workflows/deploy-bybit-btc-bridge.yml',bridgewf)

print('BYBIT_MULTI_ASSET_PATCH=READY')
