from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
DYN=ROOT/'cloudflare-worker/bybit-dynamic-universe.js'
CTRL=ROOT/'cloudflare-worker/bybit-multi-asset-controller.js'
PROFILES=ROOT/'cloudflare-worker/bybit-coin-profiles.js'
RUNTIME=ROOT/'cloudflare-worker/bybit-runtime-contract.js'


def rep(text, old, new, label):
    if old not in text:
        raise SystemExit(f'MISSING_MARKER:{label}')
    return text.replace(old,new,1)

# Portfolio policy: keep trade deep scans and add a separate watch/promotion lane.
p=PROFILES.read_text()
p=rep(p,"deepScanCount:6,","deepScanCount:6,promotionScanCount:4,",'promotion_scan_policy')
PROFILES.write_text(p)

# Dynamic universe: persistent promotion evidence + candidate discovery.
d=DYN.read_text()
d=rep(d,"const META_TTL_MS=15*60*1000;","const META_TTL_MS=15*60*1000;\nconst PROMOTION_KEY='bybit:dynamic:promotion:evidence:v1';\nconst PROMOTION_EVIDENCE_TTL_MS=45*60*1000;",'promotion_constants')
helper=r'''
function promotionPotential(row={}){const turnoverScore=clamp(num(row.turnover)/40_000_000,0,1),spreadScore=clamp(1-num(row.spreadBps)/9,0,1),oiScore=clamp(num(row.oiValue)/20_000_000,0,1),moveScore=clamp(Math.abs(num(row.change))/.02,0,1);return .34*turnoverScore+.30*spreadScore+.22*oiScore+.14*moveScore;}
function promotionSummary(ev={},row={},now=Date.now()){const hist=(Array.isArray(ev.history)?ev.history:[]).filter(x=>now-num(x.at)<=6*60*60*1000),good=hist.filter(x=>x.good).length,fresh=hist.filter(x=>x.fresh).length,goodRatio=hist.length?good/hist.length:0,freshRatio=hist.length?fresh/hist.length:0,lastGoodAt=Math.max(0,...hist.filter(x=>x.good).map(x=>num(x.at))),recent=now-num(ev.lastAt)<=PROMOTION_EVIDENCE_TTL_MS,currentMarketOk=row.classification==='WATCH_READY'&&num(row.turnover)>=25_000_000&&num(row.spreadBps)<=7.5&&num(row.oiValue)>=8_000_000&&promotionPotential(row)>=.68,qualified=recent&&currentMarketOk&&hist.length>=4&&good>=3&&goodRatio>=.70&&fresh>=3&&freshRatio>=.75&&now-lastGoodAt<=20*60*1000;return {qualified,observations:hist.length,good,fresh,goodRatio:Number(goodRatio.toFixed(3)),freshRatio:Number(freshRatio.toFixed(3)),lastAt:num(ev.lastAt)||null,lastGoodAt:lastGoodAt||null,potential:Number(promotionPotential(row).toFixed(4))};}
function applyPromotion(row={},ev={},now=Date.now()){const promotion=promotionSummary(ev,row,now);if(promotion.qualified)return {...row,classification:'TRADE_PROMOTED',eligible:true,reason:null,promotion};return {...row,promotion};}
export async function updateBybitPromotionEvidence(env,observations=[]){const now=Date.now(),bucket=Math.floor(now/(5*60*1000)),state=await get(env,PROMOTION_KEY,{symbols:{}}),symbols={...(state.symbols||{})};for(const o of observations){const symbol=normalizeBybitSymbol(o.symbol||'');if(!validLinearSymbol(symbol))continue;const prev=symbols[symbol]||{},history=(Array.isArray(prev.history)?prev.history:[]).filter(x=>now-num(x.at)<=6*60*60*1000&&num(x.bucket)!==bucket),fresh=o.fresh===true,setupOk=o.setupOk===true,quality=num(o.quality),edge=num(o.edgeScore),netRR=num(o.netRR),directionOk=o.localCounterTrend!==true||o.reversalValidated===true,good=fresh&&setupOk&&directionOk&&quality>=.30&&edge>=.055&&netRR>=1.35;history.push({bucket,at:now,fresh,good,setupOk,quality:Number(quality.toFixed(4)),edge:Number(edge.toFixed(4)),netRR:Number(netRR.toFixed(3))});symbols[symbol]={lastAt:now,history:history.slice(-12)};}const out={at:now,symbols};await put(env,PROMOTION_KEY,out);return out;}
'''
d=rep(d,"export async function buildBybitDynamicUniverse(env,api){",helper+"\nexport async function buildBybitDynamicUniverse(env,api){",'promotion_helpers')
old="const now=Date.now(),[tickers,metaState]=await Promise.all([api.tickers(),loadInstrumentMeta(env,api)]),metaMap=new Map((metaState.rows||[]).map(x=>[normalizeBybitSymbol(x.symbol),x])),rows=(tickers?.result?.list||[]).filter(x=>validLinearSymbol(x.symbol)).map(x=>rowFromTicker(x,metaMap.get(normalizeBybitSymbol(x.symbol))||{},now)).sort((a,b)=>Number(b.eligible)-Number(a.eligible)||b.score-a.score||b.turnover-a.turnover),trade=rows.filter(x=>x.eligible),watchNew=rows.filter(x=>x.classification==='WATCH_NEW'),watchOnly=rows.filter(x=>!x.eligible&&x.classification!=='WATCH_NEW'&&x.classification!=='DO_NOT_TRADE'),blocked=rows.filter(x=>x.classification==='DO_NOT_TRADE'),counts={};for(const r of rows)counts[r.classification]=(counts[r.classification]||0)+1;"
new="const now=Date.now(),[tickers,metaState,promotionState]=await Promise.all([api.tickers(),loadInstrumentMeta(env,api),get(env,PROMOTION_KEY,{symbols:{}})]),metaMap=new Map((metaState.rows||[]).map(x=>[normalizeBybitSymbol(x.symbol),x])),rawRows=(tickers?.result?.list||[]).filter(x=>validLinearSymbol(x.symbol)).map(x=>rowFromTicker(x,metaMap.get(normalizeBybitSymbol(x.symbol))||{},now)),rows=rawRows.map(x=>applyPromotion(x,promotionState.symbols?.[x.symbol]||{},now)).sort((a,b)=>Number(b.eligible)-Number(a.eligible)||b.score-a.score||b.turnover-a.turnover),trade=rows.filter(x=>x.eligible),watchNew=rows.filter(x=>x.classification==='WATCH_NEW'),watchOnly=rows.filter(x=>!x.eligible&&x.classification!=='WATCH_NEW'&&x.classification!=='DO_NOT_TRADE'),promotionCandidates=watchOnly.filter(x=>x.ageDays===null||x.ageDays>=14).filter(x=>x.turnover>=8_000_000&&x.spreadBps<=9.5&&promotionPotential(x)>=.48).sort((a,b)=>b.promotion.potential-a.promotion.potential||b.score-a.score),blocked=rows.filter(x=>x.classification==='DO_NOT_TRADE'),counts={};for(const r of rows)counts[r.classification]=(counts[r.classification]||0)+1;"
d=rep(d,old,new,'build_universe_promotion')
old_return="return {authority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2',at:now,cryptoOnly:true,coreSymbols:BYBIT_TRADE_UNIVERSE,tradeSymbols:trade.map(x=>x.symbol),ranked:rows,watchNew,watchOnly,blocked,summary:{authority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2',cryptoOnly:true,totalLinearUsdt:rows.length,tradeableNow:trade.length,watchNew:watchNew.length,watchOnly:watchOnly.length,doNotTrade:blocked.length,counts,topTrade:trade.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,score:Number(x.score.toFixed(4)),spreadBps:Number(x.spreadBps.toFixed(3)),turnover24h:x.turnover,maxLeverage:x.maxLeverage,style:x.style,symbolType:x.symbolType})),newListings:watchNew.slice(0,20).map(x=>({symbol:x.symbol,ageDays:x.ageDays===null?null:Number(x.ageDays.toFixed(2)),turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),reason:x.reason,symbolType:x.symbolType})),watch:watchOnly.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,reason:x.reason,turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),symbolType:x.symbolType})),blockedNonCrypto:blocked.filter(x=>String(x.reason||'').startsWith('NON_CRYPTO_LINEAR_PRODUCT_')).slice(0,30).map(x=>({symbol:x.symbol,symbolType:x.symbolType,reason:x.reason})),metaFresh:!metaState.stale,metaAt:metaState.at||null}};"
new_return="return {authority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION',at:now,cryptoOnly:true,coreSymbols:BYBIT_TRADE_UNIVERSE,tradeSymbols:trade.map(x=>x.symbol),ranked:rows,watchNew,watchOnly,promotionCandidates,blocked,summary:{authority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION',cryptoOnly:true,totalLinearUsdt:rows.length,tradeableNow:trade.length,promotedNow:trade.filter(x=>x.classification==='TRADE_PROMOTED').length,promotionCandidates:promotionCandidates.length,watchNew:watchNew.length,watchOnly:watchOnly.length,doNotTrade:blocked.length,counts,topTrade:trade.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,score:Number(x.score.toFixed(4)),promotion:x.promotion,spreadBps:Number(x.spreadBps.toFixed(3)),turnover24h:x.turnover,maxLeverage:x.maxLeverage,style:x.style,symbolType:x.symbolType})),promotionQueue:promotionCandidates.slice(0,30).map(x=>({symbol:x.symbol,class:x.classification,potential:x.promotion?.potential??null,observations:x.promotion?.observations??0,goodRatio:x.promotion?.goodRatio??0,freshRatio:x.promotion?.freshRatio??0,turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),reason:x.reason})),newListings:watchNew.slice(0,20).map(x=>({symbol:x.symbol,ageDays:x.ageDays===null?null:Number(x.ageDays.toFixed(2)),turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),reason:x.reason,symbolType:x.symbolType})),watch:watchOnly.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,reason:x.reason,potential:x.promotion?.potential??null,turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),symbolType:x.symbolType})),blockedNonCrypto:blocked.filter(x=>String(x.reason||'').startsWith('NON_CRYPTO_LINEAR_PRODUCT_')).slice(0,30).map(x=>({symbol:x.symbol,symbolType:x.symbolType,reason:x.reason})),metaFresh:!metaState.stale,metaAt:metaState.at||null}};"
d=rep(d,old_return,new_return,'universe_return')
d=rep(d,"export const BYBIT_DYNAMIC_UNIVERSE_VERSION='BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2';","export const BYBIT_DYNAMIC_UNIVERSE_VERSION='BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION';",'universe_version')
DYN.write_text(d)

# Controller: scan confirmed tradeables AND rotate through watch candidates, but never open risk from watch scans.
c=CTRL.read_text()
c=rep(c,"import {buildBybitDynamicUniverse} from './bybit-dynamic-universe.js';","import {buildBybitDynamicUniverse,updateBybitPromotionEvidence} from './bybit-dynamic-universe.js';",'controller_import')
c=rep(c,"const baseMax=maxConcurrentForEquity(capacityCapital)","const baseMax=maxConcurrentForEquity(equity)",'undefined_capacity_fix')
insert=r'''
function rotatingPromotionSymbols(rows=[],count=4,cursor=0){const n=Math.max(0,Math.min(rows.length,Math.floor(num(count)||0)));if(!n)return {symbols:[],nextCursor:0};if(rows.length<=n)return {symbols:rows.map(x=>x.symbol),nextCursor:0};const headCount=Math.min(2,n),head=rows.slice(0,headCount),tail=rows.slice(headCount),rotateCount=n-head.length,out=[...head];for(let i=0;i<rotateCount&&tail.length;i++)out.push(tail[(Math.floor(num(cursor))+i)%tail.length]);return {symbols:[...new Set(out.map(x=>x.symbol))],nextCursor:tail.length?(Math.floor(num(cursor))+rotateCount)%tail.length:0};}
'''
c=rep(c,"function setupRank(r={})",insert+"function setupRank(r={})",'promotion_rotation_helper')
old_targets="const openSymbols=[...new Set(positions.filter(x=>isSupportedTradeSymbol(sym(x))).map(sym))],rotation=rotatingDeepSymbols(ranked,Math.max(1,num(BYBIT_PORTFOLIO_POLICY.deepScanCount)||6),num(previous.deepScanCursor)),targets=[...new Set([...openSymbols,eventSymbol,...rotation.symbols])],results=[],scanRows=[],candidateDecisions=[];let newEntryDone=false;"
new_targets="const openSymbols=[...new Set(positions.filter(x=>isSupportedTradeSymbol(sym(x))).map(sym))],rotation=rotatingDeepSymbols(ranked,Math.max(1,num(BYBIT_PORTFOLIO_POLICY.deepScanCount)||6),num(previous.deepScanCursor)),promotionRotation=rotatingPromotionSymbols(universeState.promotionCandidates||[],Math.max(0,num(BYBIT_PORTFOLIO_POLICY.promotionScanCount)||4),num(previous.promotionScanCursor)),promotionSet=new Set(promotionRotation.symbols),targets=[...new Set([...openSymbols,eventSymbol,...rotation.symbols,...promotionRotation.symbols])],results=[],scanRows=[],promotionObservations=[],candidateDecisions=[];let newEntryDone=false;"
c=rep(c,old_targets,new_targets,'controller_dual_targets')
old_loop="for(const symbol of targets){const hardBlock=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked}),ctx=portfolioContext(positions,symbol,balance),r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:hardBlock||'EVENT_CANDIDATE_RANK_ONLY',portfolioContext:ctx});results.push(r);await sendLifecycle(env,r);const rank=setupRank(r);if(rank)scanRows.push({...rank,scanBlock:hardBlock||null});if(r?.reason==='SMART_CUT'||(r?.lifecycles||[]).some(x=>x?.cutExecuted))positions=openPos(await api.positions());}"
new_loop="for(const symbol of targets){const hardBlock=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked}),ctx=portfolioContext(positions,symbol,balance),r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:hardBlock||'EVENT_CANDIDATE_RANK_ONLY',portfolioContext:ctx});results.push(r);await sendLifecycle(env,r);const rank=setupRank(r),row=ranked.find(x=>x.symbol===symbol);if(promotionSet.has(symbol))promotionObservations.push({symbol,fresh:r?.market?.microstructureSource==='VPS_BYBIT_WS',setupOk:!!rank,quality:rank?.quality,edgeScore:rank?.edgeScore,netRR:rank?.netRR,localCounterTrend:rank?.localCounterTrend,reversalValidated:rank?.reversalValidated});if(rank&&row?.eligible)scanRows.push({...rank,scanBlock:hardBlock||null});if(r?.reason==='SMART_CUT'||(r?.lifecycles||[]).some(x=>x?.cutExecuted))positions=openPos(await api.positions());}await updateBybitPromotionEvidence(env,promotionObservations);"
c=rep(c,old_loop,new_loop,'controller_promotion_observations')
# Telemetry / cursor fields near final controller object.
c=rep(c,"deepScanCursor:rotation.nextCursor,","deepScanCursor:rotation.nextCursor,promotionScanCursor:promotionRotation.nextCursor,promotionDiscovery:{scanned:promotionRotation.symbols,candidateCount:(universeState.promotionCandidates||[]).length,observations:promotionObservations.length,authority:'WATCH_ONLY_DEEP_ANALYSIS_PERSISTENT_PROMOTION'},",'controller_promotion_telemetry')
CTRL.write_text(c)

# Runtime version/flags.
r=RUNTIME.read_text()
r=rep(r,"BYBIT_MULTI_ASSET_RUNTIME_V21_DIRECTION_COHERENCE_LONG_RUN_FREEZE","BYBIT_MULTI_ASSET_RUNTIME_V22_DUAL_LANE_DISCOVERY_PROMOTION",'runtime_version')
r=rep(r,"BYBIT-MULTI-STATEFLOW-4.4.1","BYBIT-MULTI-STATEFLOW-4.4.2",'auto_version')
r=rep(r,"universeAuthority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2'","universeAuthority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION'",'universe_authority')
r=rep(r,"longRunCoreFreeze:true,dynamicBybitScalpUniverse:true","longRunCoreFreeze:true,dualLaneMarketDiscovery:true,confirmedTradeLane:true,promotionWatchLane:true,persistentPromotionEvidence:true,promotionRequiresRepeatedFreshEvidence:true,dynamicBybitScalpUniverse:true",'runtime_dual_lane_flags')
RUNTIME.write_text(r)

# Fail closed checks.
for path,markers in {
    DYN:['TRADE_PROMOTED','promotionCandidates','updateBybitPromotionEvidence','BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION'],
    CTRL:['promotionScanCursor','WATCH_ONLY_DEEP_ANALYSIS_PERSISTENT_PROMOTION','updateBybitPromotionEvidence','const baseMax=maxConcurrentForEquity(equity)'],
    PROFILES:['promotionScanCount:4'],
    RUNTIME:['BYBIT-MULTI-STATEFLOW-4.4.2','dualLaneMarketDiscovery:true','persistentPromotionEvidence:true']
}.items():
    body=path.read_text()
    for marker in markers:
        if marker not in body: raise SystemExit(f'ASSERT_FAIL:{path.name}:{marker}')
print('BYBIT_V442_DUAL_LANE_PROMOTION_APPLIED')
