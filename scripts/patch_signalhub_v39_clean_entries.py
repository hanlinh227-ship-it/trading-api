from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
API=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java')
GRADLE=Path('signalhub-android/app/build.gradle')


def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

w=WORKER.read_text()
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.8.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.9.0';")
w=w.replace("versionCode: 14,\n  versionName: '3.8.0',\n  title: 'SignalHub 3.8.0',","versionCode: 15,\n  versionName: '3.9.0',\n  title: 'SignalHub 3.9.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.8.0',","artifactName: 'SignalHub-Android-v3.9.0',")
w=w.replace("    'V3.8 separates SCALP microstructure execution from SWING higher-timeframe execution and tracks pending triggers continuously.',","    'V3.9 Clean Market Story removes permissive transition entries and requires a coherent structure/liquidity narrative before the bot emits an order.',\n    'V3.9 uses one realtime lifecycle source of truth; scanner cycles no longer trigger or close orders from mid price.',\n    'Pending LIMIT/STOP ideas invalidate immediately by price if the setup fails before entry, and LIMIT ideas retire if the move reaches TP1 without the pullback entry.',\n    'V3.8 separation retained: SCALP microstructure execution is distinct from SWING higher-timeframe execution.',")
w=w.replace("  pendingActivation:'PRICE_TOUCH_EVENT_DRIVEN_NO_COOLDOWN'","  pendingActivation:'PRICE_TOUCH_EVENT_DRIVEN_NO_COOLDOWN',\n  qualityMode:'CLEAN_MARKET_STORY_NO_SCORE',\n  lifecycleSource:'DURABLE_OBJECT_REALTIME_SINGLE_SOURCE'")

style_policy=r'''const STYLE_EXECUTION_POLICY = Object.freeze({
  SCALP:Object.freeze({name:'SCALP_MICROSTRUCTURE',frames:['5m','15m','1h'],execution:'5m',context:'15m/1h',entryFocus:'micro liquidity sweep/reclaim, aligned continuation or confirmed breakout only',stopFocus:'validated micro swing/liquidity invalidation + volatility/spread buffer',targetFocus:'nearest clean liquidity then 15m/1h structure',holdModel:'short-horizon structure hold; no transition chase'}),
  SWING:Object.freeze({name:'SWING_HTF_STRUCTURE',frames:['1h','4h','1d'],execution:'1h',context:'4h/1d',entryFocus:'H4/D1 directional story with H1 pullback/reclaim or H1 breakout confirmation',stopFocus:'H1/H4 invalidation outside liquidity + wider volatility buffer',targetFocus:'H4/D1 liquidity objectives then structural expansion',holdModel:'multi-session HTF structure hold; H1 alone cannot define the trade'})
});'''
w=sub1(w,r"const STYLE_EXECUTION_POLICY = Object\.freeze\(\{.*?\n\}\);",style_policy,'style policy')

new_evaluate=r'''  async evaluate(market,rows,receivedAt){
    const reg=await this.registry(),by=new Map();
    for(const q of rows||[]){const sym=canonical(q?.symbol);if(!sym)continue;by.set(sym,q);}
    const changed=[],at=receivedAt||nowIso();let dirty=false;
    for(const [id,s] of Object.entries(reg)){
      if(String(s.market||'').toUpperCase()!==String(market||'').toUpperCase())continue;
      if(s.status!=='PENDING'&&s.status!=='OPEN'){delete reg[id];dirty=true;continue;}
      const q=by.get(canonical(s.symbol));if(!q)continue;
      const dir=String(s.side||'').toUpperCase()==='LONG'||String(s.side||'').toUpperCase()==='BUY'?1:-1;
      let entryPx,exitPx;
      if(String(market).toUpperCase()==='FOREX'){
        const bid=Number(q.bid||q.mid||0),ask=Number(q.ask||q.mid||0);entryPx=dir>0?ask:bid;exitPx=dir>0?bid:ask;
      }else{const last=Number(q.lastPrice||q.last||q.mid||0);entryPx=last;exitPx=last;}
      if(!(entryPx>0&&exitPx>0))continue;
      const entry=Number(s.entry),sl=Number(s.sl),tp1=Number(s.tp1||s.tp3||s.tp),tp=Number(s.tp3||s.tp);let mutated=false,eventType='';
      if(s.status==='PENDING'){
        const type=String(s.orderType||'').toUpperCase();
        const trigger=type==='LIMIT'?(dir>0?entryPx<=entry:entryPx>=entry):type==='STOP'?(dir>0?entryPx>=entry:entryPx<=entry):false;
        const invalidated=dir>0?exitPx<=sl:exitPx>=sl;
        const missedMove=type==='LIMIT'&&tp1>0&&(dir>0?exitPx>=tp1:exitPx<=tp1);
        if(invalidated||missedMove){
          s.status='CANCELLED';s.lifecycle=invalidated?'INVALIDATED_BEFORE_ENTRY':'MISSED_MOVE_BEFORE_ENTRY';s.entryState='CANCELLED';s.cancelledAt=at;s.outcome=s.lifecycle;s.resolution='REALTIME_PENDING_INVALIDATION';eventType='CANCELLED';mutated=true;delete reg[id];dirty=true;
        }else if(trigger){
          s.status='OPEN';s.lifecycle='ACTIVE';s.entryState='LIVE';s.triggeredAt=at;s.triggerPrice=entryPx;s.actualEntry=s.actualEntry||entry;s.executionStatus='PRICE_TRIGGERED_AWAITING_BROKER_CONFIRM';eventType='TRIGGERED';mutated=true;
        }
      }
      if(s.status==='OPEN'){
        const hitTp=dir>0?exitPx>=tp:exitPx<=tp,hitSl=dir>0?exitPx<=sl:exitPx>=sl;
        if(hitTp||hitSl){s.status='CLOSED';s.outcome=hitTp?'TP':'SL';s.lifecycle=hitTp?'TP3_HIT':'STOP_LOSS_HIT';s.closedAt=at;s.exitPrice=hitTp?tp:sl;s.resultR=hitTp?Number(s.targetRR||0):-1;s.resolution='REALTIME_EVENT_TRACKER';eventType=s.outcome;mutated=true;delete reg[id];dirty=true;}
      }
      if(mutated){
        s.lastPrice=exitPx;s.lastCheckedAt=at;
        const kvKey=String(s.kvKey||`v31:signal:${s.market}:${s.style}:${id}`),clean={...s};delete clean.kvKey;
        const active=clean.status==='PENDING'||clean.status==='OPEN';
        if(this.env?.SIGNALS_KV){await this.env.SIGNALS_KV.put(kvKey,JSON.stringify(clean),{expirationTtl:SIGNAL_TTL});if(!active)await this.env.SIGNALS_KV.delete(`v31:active:${clean.market}:${clean.style}:${clean.symbol}`);}
        if(active)reg[id]={...clean,kvKey};else delete reg[id];dirty=true;
        changed.push({type:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,at});this.broadcast({type:'signal_event',event:eventType,signal:clean,price:eventType==='TRIGGERED'?entryPx:exitPx,receivedAt:at});
      }
    }
    if(dirty)await this.persistRegistry();return changed;
  }'''
w=sub1(w,r"  async evaluate\(market,rows,receivedAt\)\{.*?\n  \}\n  async fetch\(req\)",new_evaluate+"\n  async fetch(req)",'realtime evaluate')

# Scanner must never be a second fill/SL/TP engine. Durable Object live events are the sole lifecycle authority.
w=sub1(w,r"async function trackV31Signals\(env,market,style,priceMap\)\{.*?\n\}\nasync function maybeCreateV31",r'''async function trackV31Signals(env,market,style,priceMap){
  return [];
}
async function retireLegacyPendingSignals(env,market,style){
  if(!env?.SIGNALS_KV)return[];
  const all=await getV31Signals(env,market,style),events=[],at=nowIso();
  for(const s of all){
    if(s.status!=='PENDING'||String(s.engineVersion||'')===V3_VERSION)continue;
    s.status='CANCELLED';s.entryState='CANCELLED';s.lifecycle='REPLACED_BY_V39_CLEAN_STORY';s.outcome='CONTEXT_REFRESH';s.cancelledAt=at;s.resolution='V39_PENDING_MIGRATION';s.lastCheckedAt=at;
    await writeV31Signal(env,s);events.push({type:'CANCELLED',id:s.id,symbol:s.symbol,reason:s.lifecycle});
  }
  return events;
}
async function maybeCreateV31''','single lifecycle')
w=w.replace("const issuedAt=nowIso(),id=`V36-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;","const issuedAt=nowIso(),id=`V39-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;")

crypto_setup=r'''function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP;
  const breakoutUp=(a.bosUp||(a.priorHigh-px)/a.atr>=-.08&&(a.priorHigh-px)/a.atr<=.18)&&(a.momentum>=0&&a.slope>0||a.impulse>.55);
  const breakoutDown=(a.bosDown||(px-a.priorLow)/a.atr>=-.08&&(px-a.priorLow)/a.atr<=.18)&&(a.momentum<=0&&a.slope<0||a.impulse>.55);
  let dir=0,regime='NO_TRADE',story='';
  if(style==='SWING'){
    const htf=b.trend!==0&&b.trend===c.trend?b.trend:0;
    if(a.sweepLow&&htf===1&&a.close>a.priorLow){dir=1;regime='HTF_LIQUIDITY_SWEEP_RECLAIM';story='H4/D1 bullish structure + H1 downside sweep and reclaim';}
    else if(a.sweepHigh&&htf===-1&&a.close<a.priorHigh){dir=-1;regime='HTF_LIQUIDITY_SWEEP_RECLAIM';story='H4/D1 bearish structure + H1 upside sweep and reclaim';}
    else if(htf!==0&&a.trend===htf&&a.momentum===htf){dir=htf;regime=a.extensionAtr>.38?'HTF_TREND_PULLBACK':'HTF_TREND_CONTINUATION';story='H4/D1 trend aligned with H1 structure and momentum';}
    else if(htf===1&&breakoutUp){dir=1;regime='HTF_BREAKOUT_BUILDUP';story='H4/D1 bullish structure + H1 breakout pressure';}
    else if(htf===-1&&breakoutDown){dir=-1;regime='HTF_BREAKOUT_BUILDUP';story='H4/D1 bearish structure + H1 breakout pressure';}
    else if(htf!==0&&a.trend!==-htf&&a.momentum===htf){dir=htf;regime='HTF_TREND_REJOIN';story='H4/D1 trend with H1 momentum rejoining after pullback';}
    else return null;
  }else{
    const contextNotBear=b.trend>=0&&c.trend>=0,contextNotBull=b.trend<=0&&c.trend<=0;
    if(a.sweepLow&&contextNotBear&&a.close>a.priorLow){dir=1;regime='LIQUIDITY_SWEEP_RECLAIM';story='5m downside liquidity sweep + reclaim with 15m/1h not opposing';}
    else if(a.sweepHigh&&contextNotBull&&a.close<a.priorHigh){dir=-1;regime='LIQUIDITY_SWEEP_RECLAIM';story='5m upside liquidity sweep + reclaim with 15m/1h not opposing';}
    else if(a.trend!==0&&a.trend===b.trend&&c.trend!==-a.trend&&a.momentum===a.trend){dir=a.trend;regime=a.extensionAtr>.34?'TREND_PULLBACK':'TREND_CONTINUATION';story='5m/15m structure aligned, 1h not opposing, momentum confirms';}
    else if(b.trend!==0&&b.trend===c.trend&&a.trend!==-b.trend&&a.momentum===b.trend){dir=b.trend;regime='HTF_TREND_REJOIN';story='15m/1h aligned while 5m momentum rejoins';}
    else if(breakoutUp&&b.trend>=0&&c.trend>=0){dir=1;regime='BREAKOUT_BUILDUP';story='5m breakout pressure with 15m/1h not opposing';}
    else if(breakoutDown&&b.trend<=0&&c.trend<=0){dir=-1;regime='BREAKOUT_BUILDUP';story='5m breakdown pressure with 15m/1h not opposing';}
    else return null;
  }

  const spread=Number(t.spreadBps??0),atr1=a.atr,spreadPx=Math.max(0,px*spread/10000),entryBuffer=Math.max(atr1*(style==='SCALP'?.05:.09),spreadPx*(style==='SCALP'?2.0:2.5));
  const badLocation=dir>0?a.rangePosition>.72:a.rangePosition<.28,extended=Math.abs(a.extensionAtr)>(style==='SCALP'?.34:.28);
  let orderType='MARKET',entry=px,entryModel='MARKET_AFTER_STRUCTURE_CONFIRMATION';
  if(regime.includes('BREAKOUT')){orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='BREAKOUT_TRIGGER_BEYOND_LIQUIDITY';}
  else if(!regime.includes('SWEEP')&&(style==='SWING'||badLocation||extended||regime.includes('PULLBACK')||regime.includes('REJOIN'))){
    const raw=dir>0?Math.max(a.ema20,a.recentLow+.34*atr1):Math.min(a.ema20,a.recentHigh-.34*atr1);
    if((dir>0&&raw<px-entryBuffer*.25)||(dir<0&&raw>px+entryBuffer*.25)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_VALIDATED_DYNAMIC_STRUCTURE';}
    else if(style==='SWING'){return null;}
  }else if(regime.includes('SWEEP'))entryModel='LIQUIDITY_RECLAIM_MARKET_ENTRY';

  const stopBuffer=Math.max(atr1*(style==='SCALP'?.17:.30),spreadPx*(style==='SCALP'?2.2:3.0));
  let anchor;
  if(dir>0){anchor=Math.min(a.low,a.priorLow,a.recentLow,a.ema50-.05*atr1);if(style==='SWING')anchor=Math.min(anchor,b.low,b.priorLow,b.recentLow,b.ema50-.08*b.atr);}
  else{anchor=Math.max(a.high,a.priorHigh,a.recentHigh,a.ema50+.05*atr1);if(style==='SWING')anchor=Math.max(anchor,b.high,b.priorHigh,b.recentHigh,b.ema50+.08*b.atr);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl);
  const minRisk=atr1*(style==='SCALP'?.62:1.02);if(!(risk>=minRisk)){risk=minRisk;sl=entry-dir*risk;}
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;
  if(dir>0){tp1=above([a.priorHigh,a.recentHigh],entry+risk*.90);tp2=above([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=above([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.15:2.95)));}
  else{tp1=below([a.priorLow,a.recentLow],entry-risk*.90);tp2=below([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=below([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.15:2.95)));}
  const rr=Math.abs(tp3-entry)/risk,spreadState=spread>(style==='SCALP'?12:30)?'WIDE':'NORMAL',judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • CLEAN STORY`;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,marketRegime:regime,marketStory:story,judgment,entryModel,slModel:'VALIDATED_SWING_LIQUIDITY_INVALIDATION_PLUS_VOLATILITY_SPREAD_BUFFER',tpModel:'CLEAN_LIQUIDITY_LADDER_THEN_STRUCTURE_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:spreadState,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`entry ${entryModel}`,`SL outside invalidation ${Number(anchor.toPrecision(8))} plus volatility/spread buffer`,`TP ladder targets local, context and HTF liquidity before expansion`,`RSI ${a.rsi.toFixed(1)} • extension ${a.extensionAtr.toFixed(2)} ATR • spread ${spread.toFixed(2)} bps`]},'CRYPTO',style);
}'''
w=sub1(w,r"function buildCryptoSetup\(t,style,stats\)\{.*?\n\}\nasync function analyzeCryptoCandidate",crypto_setup+"\nasync function analyzeCryptoCandidate",'crypto clean setup')

forex_setup=r'''function forexJudgmentSetup(r,px,style){
  if(!(px>0&&r.atrA>0&&r.atrB>0&&r.ema20A>0&&r.ema50A>0&&r.ema20B>0&&r.ema50B>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP;
  const emaA=r.ema20A>r.ema50A?1:r.ema20A<r.ema50A?-1:0,emaB=r.ema20B>r.ema50B?1:r.ema20B<r.ema50B?-1:0;
  const recA=r.recA>0?1:r.recA<0?-1:0,recB=r.recB>0?1:r.recB<0?-1:0,recC=r.recC>0?1:r.recC<0?-1:0;
  const atr=Math.max(r.atrA,r.atrB*(style==='SCALP'?.34:.50)),ext=(px-r.ema20A)/atr;
  const highA=r.highA>0?r.highA:px+.55*atr,lowA=r.lowA>0?r.lowA:px-.55*atr,openA=r.openA>0?r.openA:px;
  const highB=r.highB>0?r.highB:r.ema20B+r.atrB*.8,lowB=r.lowB>0?r.lowB:r.ema20B-r.atrB*.8;
  const body=Math.max(Math.abs(px-openA),atr*.04),lowerWick=Math.max(0,Math.min(px,openA)-lowA),upperWick=Math.max(0,highA-Math.max(px,openA));
  const bullReject=px>=openA&&lowerWick>Math.max(body*.95,atr*.18),bearReject=px<=openA&&upperWick>Math.max(body*.95,atr*.18);
  const range=Math.max(highA-lowA,atr*.55),pos=Math.max(0,Math.min(1,(px-lowA)/range));
  const contextDir=emaB!==0&&recB===emaB&&(recC===0||recC===emaB)?emaB:0;
  let dir=0,regime='NO_TRADE',story='';
  if(style==='SWING'){
    const htfDir=contextDir;
    if(bullReject&&htfDir===1&&emaA>=0){dir=1;regime='HTF_LIQUIDITY_REJECTION';story='H4/D1 bullish context + H1 downside rejection/reclaim';}
    else if(bearReject&&htfDir===-1&&emaA<=0){dir=-1;regime='HTF_LIQUIDITY_REJECTION';story='H4/D1 bearish context + H1 upside rejection/reclaim';}
    else if(htfDir!==0&&emaA===htfDir&&recA===htfDir){dir=htfDir;regime=Math.abs(ext)>.32?'HTF_TREND_PULLBACK':'HTF_TREND_REJOIN';story='H4/D1 directional context aligned with H1 EMA structure and recommendation';}
    else return null;
  }else{
    if(bullReject&&contextDir===1){dir=1;regime='LIQUIDITY_REJECTION';story='5m rejection/reclaim aligned with 15m/1h bullish context';}
    else if(bearReject&&contextDir===-1){dir=-1;regime='LIQUIDITY_REJECTION';story='5m rejection/reclaim aligned with 15m/1h bearish context';}
    else if(contextDir!==0&&emaA===contextDir&&recA===contextDir){dir=contextDir;regime=Math.abs(ext)>.34?'TREND_PULLBACK':'TREND_CONTINUATION';story='5m EMA and recommendation aligned with 15m/1h context';}
    else return null;
  }

  const strongImpulse=Math.abs(Number(r.recA||0))>.48&&Math.abs(Number(r.recB||0))>.28&&body>atr*.22;
  const atBreakEdge=dir>0?pos>.72:pos<.28,entryBuffer=atr*(style==='SCALP'?.05:.10);
  let orderType='MARKET',entry=px,entryModel='MARKET_AFTER_CLEAN_STRUCTURE_CONFIRMATION';
  if(strongImpulse&&atBreakEdge&&regime!=='LIQUIDITY_REJECTION'&&regime!=='HTF_LIQUIDITY_REJECTION'){
    orderType='STOP';entry=dir>0?highA+entryBuffer:lowA-entryBuffer;regime=style==='SCALP'?'BREAKOUT_CONFIRMATION':'HTF_BREAKOUT_CONFIRMATION';entryModel='BREAKOUT_TRIGGER_OUTSIDE_CURRENT_STRUCTURE';story+=' + execution waits for structure break';
  }else if(!regime.includes('LIQUIDITY')&&(style==='SWING'||Math.abs(ext)>.30||(dir>0?pos>.68:pos<.32)||regime.includes('PULLBACK'))){
    const raw=dir>0?Math.max(r.ema20A,lowA+.34*atr):Math.min(r.ema20A,highA-.34*atr);
    if((dir>0&&raw<px-entryBuffer*.25)||(dir<0&&raw>px+entryBuffer*.25)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_VALIDATED_EMA_STRUCTURE';}
    else if(style==='SWING'){return null;}
  }else if(regime.includes('LIQUIDITY'))entryModel='REJECTION_RECLAIM_MARKET_ENTRY';

  const stopBuffer=atr*(style==='SCALP'?.17:.30);let anchor;
  if(dir>0){anchor=Math.min(lowA,r.ema50A-.06*atr);if(style==='SWING')anchor=Math.min(anchor,lowB,r.ema50B-.10*r.atrB);}
  else{anchor=Math.max(highA,r.ema50A+.06*atr);if(style==='SWING')anchor=Math.max(anchor,highB,r.ema50B+.10*r.atrB);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr*(style==='SCALP'?.62:1.05);if(!(risk>=minRisk)){risk=minRisk;sl=entry-dir*risk;}
  const above=(vals,fallback)=>Math.max(...vals.filter(Number.isFinite),fallback),below=(vals,fallback)=>Math.min(...vals.filter(Number.isFinite),fallback);
  let tp1,tp2,tp3;
  if(dir>0){tp1=above([highA],entry+risk*.90);tp2=above([highB],Math.max(tp1+risk*.30,entry+risk*1.55));tp3=Math.max(tp2+risk*.38,entry+risk*(style==='SCALP'?2.15:3.00));}
  else{tp1=below([lowA],entry-risk*.90);tp2=below([lowB],Math.min(tp1-risk*.30,entry-risk*1.55));tp3=Math.min(tp2-risk*.38,entry-risk*(style==='SCALP'?2.15:3.00));}
  const rr=Math.abs(tp3-entry)/risk,judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • CLEAN STORY`;
  return stampMarketJudgment({market:'FOREX',style,symbol:r.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry,sl,tp1,tp2,tp3,tp:tp3,targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:'EXNESS_MT5+TRADINGVIEW_FOREX',executionPriceAuthority:'EXNESS_MT5',marketRegime:regime,marketStory:story,judgment,entryModel,slModel:'VALIDATED_LIQUIDITY_STRUCTURE_INVALIDATION_PLUS_VOLATILITY_BUFFER',tpModel:'LOCAL_HTF_LIQUIDITY_LADDER_THEN_EXPANSION',invalidationLevel:anchor,styleExecutionModel:profile.name,executionFrames:profile.frames,technicalAtIssue:{frames:r.frames,recommend:[r.recA,r.recB,r.recC],rsi:[r.rsiA,r.rsiB],atr:[r.atrA,r.atrB],ema20:[r.ema20A,r.ema20B],ema50:[r.ema50A,r.ema50B],extensionAtr:Number(ext.toFixed(2)),localStructure:[lowA,highA],htfStructure:[lowB,highB],bullReject,bearReject,rangePosition:Number(pos.toFixed(2))},rationale:[story,`entry ${entryModel}`,`SL outside invalidation ${Number(anchor.toPrecision(8))} plus volatility buffer`,`TP1/TP2 use local and HTF liquidity; TP3 expands only beyond those objectives`,`RSI ${Number(r.rsiA).toFixed(1)} / ${Number(r.rsiB).toFixed(1)}`]},'FOREX',style);
}'''
w=sub1(w,r"function forexJudgmentSetup\(r,px,style\)\{.*?\n\}\nasync function scanForexJudgment",forex_setup+"\nasync function scanForexJudgment",'forex clean setup')

w=w.replace("  const priceMap=new Map(all.map(x=>[x.symbol,x.lastPrice])),trackerEvents=await trackV31Signals(env,'CRYPTO',style,priceMap);","  const trackerEvents=await retireLegacyPendingSignals(env,'CRYPTO',style);")
w=w.replace("return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,deepAnalyzed:ranked.length,actionable:analyses.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score gate and no signal cooldown. The bot classifies regime and routes each actionable idea as MARKET, LIMIT or STOP.'};","return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,deepAnalyzed:ranked.length,actionable:analyses.length,noTrade:Math.max(0,ranked.length-analyses.length),created:created.length,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time/RR admission gate. The bot emits an order only when it can form a coherent market story; otherwise NO TRADE.'};")
w=w.replace("const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await trackV31Signals(env,'FOREX',style,priceMap),setups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),created=await maybeCreateV31(env,'FOREX',style,setups);","const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await retireLegacyPendingSignals(env,'FOREX',style),setups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),created=await maybeCreateV31(env,'FOREX',style,setups);")
w=w.replace("return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,actionable:setups.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY};","return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,actionable:setups.length,noTrade:Math.max(0,rows.length-setups.length),created:created.length,newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY};")
WORKER.write_text(w)

# Android version and transparency: expose the bot's market story, not a score.
a=ACT.read_text().replace('APP_VERSION="3.8.0"','APP_VERSION="3.9.0"').replace('REALTIME • V3.8','CLEAN STORY • REALTIME • V3.9')
a=a.replace('c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("ENTRY MODEL",', 'c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("MARKET STORY",s.optString("marketStory","BOT READS CURRENT STRUCTURE"),CYAN));c.addView(line("ENTRY MODEL",')
ACT.write_text(a)

m=MON.read_text().replace('SignalHub V3.8 • LIVE MONITOR','SignalHub V3.9 • CLEAN STORY LIVE').replace('else if("CLOSED".equals(status)&&"CANCELLED".equals(outcome))notifySignal("ĐÃ HỦY",market,style,s,dataState,id+":cancel");','else if("CANCELLED".equals(status))notifySignal("ĐÃ HỦY / SETUP MẤT HIỆU LỰC",market,style,s,dataState,id+":cancel");')
MON.write_text(m)

api=API.read_text().replace('SignalHub-Android/3.3.0-cyber-ui','SignalHub-Android/3.9.0-clean-market-story')
API.write_text(api)

g=GRADLE.read_text().replace('versionCode 14','versionCode 15').replace("versionName '3.8.0'","versionName '3.9.0'")
GRADLE.write_text(g)

print('patched SignalHub V3.9 clean market story: selective entries + single realtime lifecycle')
