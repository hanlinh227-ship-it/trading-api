from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
STRAT=ROOT/'cloudflare-worker/bybit-symbol-strategy.js'
CTRL=ROOT/'cloudflare-worker/bybit-multi-asset-controller.js'
RUNTIME=ROOT/'cloudflare-worker/bybit-runtime-contract.js'


def must_replace(text, old, new, label):
    if old not in text:
        raise SystemExit(f'MISSING_MARKER:{label}')
    return text.replace(old,new,1)

# 1) Per-symbol local direction coherence + strict counter-trend exception.
s=STRAT.read_text()
helper=r'''function regimeSide(regime=''){const r=String(regime||'').toUpperCase();if(/(BREAKOUT_DOWN|TREND_DOWN|BEAR|SELL)/.test(r))return 'Sell';if(/(BREAKOUT_UP|TREND_UP|BULL|BUY)/.test(r))return 'Buy';return null;}
function directionCoherence(side,s={},p={}){const sgn=side==='Buy'?1:-1,q=qualityScore(s,p),fp=momentumFootprint(s),signed=signedMarketScore(s,p),alignedScore=sgn*signed,absAligned=Math.max(0,alignedScore),flowMult=Math.max(.8,num(p.flowThresholdMult)||1),threshold=(p.style==='MOMENTUM'?.060:p.style==='BURST'?.058:p.style==='TREND'?.064:p.style==='RANGE'?.052:.060)*flowMult,t=s.trades||{},u=s.ultraFast||{},b=s.book||{},pulse=s.marketPulse||{},flow3=sgn*num(t.window3s?.imbalance),flow5=sgn*num(t.window5s?.imbalance),flow15=sgn*num(t.window15s?.imbalance??t.aggressorImbalance),flow60=sgn*num(t.window60s?.imbalance),pressure=sgn*num(u.pressureScore),impulse=sgn*num(u.impulseScore),book=sgn*num(b.imbalance2),micro=sgn*num(b.micropriceEdgeBps),pulseScore=sgn*num(pulse.score),footprint=sgn*fp.score,d5=sgn*num(s.direction5),d15=sgn*num(s.direction15),d60=sgn*num(s.direction60),bias=sgn*num(s.structure15?.bias),regimeDirection=regimeSide(s.regime),againstRegime=!!regimeDirection&&regimeDirection!==side,slowConflict=(d15<-.05&&d60<-.05)||(bias<0&&d15<-.08),localCounterTrend=againstRegime||slowConflict,votes=[flow3>.045*flowMult,flow5>.055*flowMult,flow15>.045*flowMult,pressure>.035*flowMult,impulse>.04*flowMult,book>-.035,micro>-.10,pulseScore>.025,footprint>.04&&fp.confidence>.30].filter(Boolean).length,reversalValidated=!localCounterTrend||(q>=.34&&absAligned>=threshold*2.05&&votes>=6&&footprint>=.08&&fp.confidence>=.46&&flow3>=.10&&flow5>=.11&&flow15>=.075&&flow60>-.18&&(pressure>=.06||impulse>=.07)&&book>-.02&&micro>-.06&&d5>.015&&(d15>-.02||bias>=0)),marketContrarianQualified=q>=.38&&absAligned>=threshold*2.30&&votes>=7&&footprint>=.10&&fp.confidence>=.52&&flow5>=.13&&flow15>=.09&&flow60>-.12&&(pressure>=.07||impulse>=.08)&&book>=-.01&&micro>-.04&&d5>.02;return {side,regimeDirection,againstRegime,slowConflict,localCounterTrend,reversalValidated,marketContrarianQualified,q,alignedScore,threshold,votes,footprint,footprintConfidence:fp.confidence,flow3,flow5,flow15,flow60,pressure,impulse,book,micro,pulseScore,d5,d15,d60,bias};}
'''
s=must_replace(s,'function specializedSetup',helper+'function specializedSetup','strategy_helper_insert')
s=must_replace(s,"if(flow15<-.05*flowMult||flow60<-.58||book<-.20*bookTol)return {ok:false,reason:'PROFILE_MULTI_HORIZON_CONFLICT'};","if(flow15<-.05*flowMult||flow60<-.58||book<-.20*bookTol)return {ok:false,reason:'PROFILE_MULTI_HORIZON_CONFLICT'};const direction=directionCoherence(side,s,p);if(direction.localCounterTrend&&!direction.reversalValidated)return {ok:false,reason:'PROFILE_COUNTERTREND_UNCONFIRMED',diagnostic:direction};",'strategy_countertrend_guard')
s=must_replace(s,"if(p.style==='TREND'){const bias=num(s.structure15?.bias),d15=num(s.direction15);if(side==='Buy'&&bias<0&&d15<-.08)return {ok:false,reason:'PROFILE_TREND_CONFLICT'};if(side==='Sell'&&bias>0&&d15>.08)return {ok:false,reason:'PROFILE_TREND_CONFLICT'};}","if(p.style==='TREND'){const bias=num(s.structure15?.bias),d15=num(s.direction15);if(side==='Buy'&&bias<0&&d15<-.08&&!direction.reversalValidated)return {ok:false,reason:'PROFILE_TREND_CONFLICT'};if(side==='Sell'&&bias>0&&d15>.08&&!direction.reversalValidated)return {ok:false,reason:'PROFILE_TREND_CONFLICT'};}",'strategy_trend_exception')
s=must_replace(s,"const strength=abs>.18&&q>.42?'A_PLUS':abs>.11?'STRONG':'NORMAL',setupName=`${p.style}_${String(s.regime||'TRANSITION')}_PROFILE_EDGE`;","const strength=abs>.18&&q>.42?'A_PLUS':abs>.11?'STRONG':'NORMAL',setupName=direction.localCounterTrend?`${p.style}_COUNTERTREND_REVERSAL_PROFILE_EDGE`:`${p.style}_${String(s.regime||'TRANSITION')}_PROFILE_EDGE`;",'strategy_setup_name')
s=must_replace(s,"footprintReversalPenalty:fp.reversalPenalty,source:s.microstructureSource}","footprintReversalPenalty:fp.reversalPenalty,localCounterTrend:direction.localCounterTrend,reversalValidated:direction.reversalValidated,marketContrarianQualified:direction.marketContrarianQualified,regimeDirection:direction.regimeDirection,direction15:direction.d15,direction60:direction.d60,structureBias:direction.bias,source:s.microstructureSource}",'strategy_evidence')
pattern=r"function adaptBase\(base=\{\},s=\{\},p=\{\}\)\{.*?\}\n\nexport function selectBybitSymbolSetup"
m=re.search(pattern,s,re.S)
if not m: raise SystemExit('MISSING_MARKER:adaptBase')
new_adapt="""function adaptBase(base={},s={},p={}){const x={...(base.setup||{})},side=String(x.side||'Buy'),direction=directionCoherence(side,s,p);if(direction.localCounterTrend&&!direction.reversalValidated)return {ok:false,reason:'PROFILE_COUNTERTREND_UNCONFIRMED_BASE',diagnostic:direction};const entry=num(x.entry),sl=num(x.sl),d=Math.abs(entry-sl),rr=clamp(num(x.rr||1.8)*num(p.targetMult||1),1.35,num(p.runnerMaxR)||3.2),tp=side==='Buy'?entry+d*rr:entry-d*rr,cost=costGate(side,{entry,sl,tp},s,p);if(!cost.ok)return {ok:false,reason:'PROFILE_EDGE_INSUFFICIENT_AFTER_FEES',cost};return {ok:true,setup:{...x,symbol:normalizeBybitSymbol(s.symbol),setup:direction.localCounterTrend?`${String(x.setup||p.style||'BASE')}_COUNTERTREND_REVERSAL`:x.setup,tp,rr,cost,riskScale:clamp(num(x.riskScale||1)*num(p.riskMult||.7),.20,1),coinProfile:p,evidence:{...(x.evidence||{}),coinProfile:p.symbol,coinStyle:p.style,profileSignalGain:p.signalGain,profileTargetMult:p.targetMult,profileRiskMult:p.riskMult,localCounterTrend:direction.localCounterTrend,reversalValidated:direction.reversalValidated,marketContrarianQualified:direction.marketContrarianQualified,regimeDirection:direction.regimeDirection,direction15:direction.d15,direction60:direction.d60,structureBias:direction.bias}}};}

export function selectBybitSymbolSetup"""
s=s[:m.start()]+new_adapt+s[m.end():]
s=s.replace("BYBIT_SYMBOL_COGNITION_V4_MOMENTUM_FOOTPRINT_DYNAMIC_SCALP","BYBIT_SYMBOL_COGNITION_V5_DIRECTION_COHERENCE_LONG_RUN_FREEZE")
STRAT.write_text(s)

# 2) Cross-market breadth guard. It never forces all coins to same side; only blocks weak unexplained outliers.
c=CTRL.read_text()
rank_pattern=r"function setupRank\(r=\{\}\)\{.*?\}\nfunction entryBlockFor"
m=re.search(rank_pattern,c,re.S)
if not m: raise SystemExit('MISSING_MARKER:setupRank')
new_rank="""function setupRank(r={}){const s=r?.scan?.best;if(!s)return null;const strength=String(s.strength||'NORMAL')==='A_PLUS'?3:String(s.strength||'NORMAL')==='STRONG'?2:1,tier=String(s.entryTier||'CONFIRM')==='FULL'?3:String(s.entryTier||'CONFIRM')==='CONFIRM'?2:1,e=s.evidence||{},profile=coinProfileForSymbol(s.symbol||r?.market?.symbol||''),edge=Math.abs(num(e.score)),quality=num(e.quality),netRR=num(s.cost?.netRewardRisk),priority=num(profile?.priority),rankScore=strength*100+tier*30+clamp(edge,0,1)*20+clamp(quality,0,1)*15+clamp(netRR,0,6)*2+priority/100;return {symbol:normalizeBybitSymbol(s.symbol||r?.market?.symbol||''),side:String(s.side||''),regime:String(s.regime||''),rankScore,strength:String(s.strength||'NORMAL'),entryTier:String(s.entryTier||'CONFIRM'),edgeScore:edge,quality,netRR,priority,setup:String(s.setup||'PROFILE_EDGE'),localCounterTrend:!!e.localCounterTrend,reversalValidated:!!e.reversalValidated,marketContrarianQualified:!!e.marketContrarianQualified};}
function marketBreadth(rows=[]){const usable=rows.filter(x=>x&&['Buy','Sell'].includes(String(x.side)));if(usable.length<4)return {strong:false,side:null,agreement:0,sample:usable.length,buyWeight:0,sellWeight:0};let buy=0,sell=0;for(const x of usable){const w=1+clamp(num(x.edgeScore)*2,0,1)+clamp(num(x.quality),0,.75)+(String(x.strength)==='A_PLUS'?.45:String(x.strength)==='STRONG'?.22:0);if(x.side==='Buy')buy+=w;else sell+=w;}const total=Math.max(.0001,buy+sell),side=buy>=sell?'Buy':'Sell',agreement=Math.max(buy,sell)/total,imbalance=Math.abs(buy-sell)/total,strong=usable.length>=4&&agreement>=.72&&imbalance>=.44;return {strong,side,agreement:Number(agreement.toFixed(4)),imbalance:Number(imbalance.toFixed(4)),sample:usable.length,buyWeight:Number(buy.toFixed(3)),sellWeight:Number(sell.toFixed(3))};}
function marketDirectionBlock(candidate={},breadth={}){if(!breadth?.strong||!breadth.side||candidate.side===breadth.side)return null;const exceptional=candidate.marketContrarianQualified===true&&candidate.strength==='A_PLUS'&&candidate.entryTier==='FULL'&&num(candidate.quality)>=.38;return exceptional?null:'CROSS_MARKET_DIRECTION_CONFLICT';}
function entryBlockFor"""
c=c[:m.start()]+new_rank+c[m.end():]
old="positions=openPos(await api.positions());const queue=scanRows.sort((a,b)=>b.rankScore-a.rankScore||b.priority-a.priority);for(const candidate of queue){if(newEntryDone)break;const symbol=candidate.symbol,block=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked}),decision={...candidate,finalBlock:block||null,action:block?'BLOCKED':'FRESH_RECHECK'};"
if old not in c:
    old="positions=openPos(await api.positions());const queue=scanRows.sort((a,b)=>b.rankScore-a.rankScore||b.priority-a.priority);for(const candidate of queue){if(newEntryDone)break;const symbol=candidate.symbol,block=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked});const decision={...candidate,finalBlock:block||null,action:block?'BLOCKED':'FRESH_RECHECK'};"
new="positions=openPos(await api.positions());const queue=scanRows.sort((a,b)=>b.rankScore-a.rankScore||b.priority-a.priority),breadth=marketBreadth(queue);for(const candidate of queue){if(newEntryDone)break;const symbol=candidate.symbol,portfolioBlock=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked}),directionBlock=marketDirectionBlock(candidate,breadth),block=portfolioBlock||directionBlock;const decision={...candidate,marketBreadthSide:breadth.side,marketBreadthAgreement:breadth.agreement,finalBlock:block||null,action:block?'BLOCKED':'FRESH_RECHECK'};"
c=must_replace(c,old,new,'controller_queue_breadth')
c=must_replace(c,"entrySelectionAuthority:'OBJECTIVE_SCAN_THEN_RANK_FRESH_RECHECK',deepScanAuthority:","entrySelectionAuthority:'OBJECTIVE_SCAN_THEN_RANK_FRESH_RECHECK',directionCoherenceAuthority:'PER_SYMBOL_REGIME_PLUS_CROSS_MARKET_BREADTH',strictContrarianException:true,deepScanAuthority:",'controller_authority')
c=must_replace(c,"objectiveCandidateRanking:queue.slice(0,8),candidateDecisions:","objectiveCandidateRanking:queue.slice(0,8),marketDirectionBreadth:breadth,candidateDecisions:",'controller_telemetry')
CTRL.write_text(c)

# 3) Runtime contract: long-run freeze version and explicit safeguards.
r=RUNTIME.read_text()
r=must_replace(r,"BYBIT_MULTI_ASSET_RUNTIME_V20_DYNAMIC_SCALP_ANTI_SWEEP","BYBIT_MULTI_ASSET_RUNTIME_V21_DIRECTION_COHERENCE_LONG_RUN_FREEZE",'runtime_version')
r=must_replace(r,"BYBIT-MULTI-STATEFLOW-4.4.0","BYBIT-MULTI-STATEFLOW-4.4.1",'auto_version')
r=must_replace(r,"momentumFootprint:true,dynamicBybitScalpUniverse:true","momentumFootprint:true,perSymbolRegimeSideCoherence:true,crossMarketDirectionBreadthGuard:true,strictContrarianException:true,longRunCoreFreeze:true,dynamicBybitScalpUniverse:true",'runtime_flags')
RUNTIME.write_text(r)

# Assertions: fail closed if anything essential is absent.
checks={
 'strategy':['PROFILE_COUNTERTREND_UNCONFIRMED','marketContrarianQualified','BYBIT_SYMBOL_COGNITION_V5_DIRECTION_COHERENCE_LONG_RUN_FREEZE'],
 'controller':['CROSS_MARKET_DIRECTION_CONFLICT','marketDirectionBreadth','PER_SYMBOL_REGIME_PLUS_CROSS_MARKET_BREADTH'],
 'runtime':['BYBIT-MULTI-STATEFLOW-4.4.1','crossMarketDirectionBreadthGuard:true','longRunCoreFreeze:true']
}
for name,path in [('strategy',STRAT),('controller',CTRL),('runtime',RUNTIME)]:
    body=path.read_text()
    for marker in checks[name]:
        if marker not in body: raise SystemExit(f'ASSERT_FAIL:{name}:{marker}')
print('BYBIT_V441_DIRECTION_COHERENCE_FREEZE_APPLIED')
