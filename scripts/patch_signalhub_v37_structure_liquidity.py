from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
GRADLE=Path('signalhub-android/app/build.gradle')


def sub1(text, pattern, repl, label):
    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

w=WORKER.read_text()
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.6.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.7.0';")
w=w.replace("versionCode: 12,\n  versionName: '3.6.0',\n  title: 'SignalHub 3.6.0',","versionCode: 13,\n  versionName: '3.7.0',\n  title: 'SignalHub 3.7.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.6.0',","artifactName: 'SignalHub-Android-v3.7.0',")
w=w.replace("    'V3.6 Market Judgment Engine: no score gate, no minimum score, no RR admission threshold and no signal cooldown.',","    'V3.7 Structure-Liquidity Engine: entries, stops and targets are derived from live structure, liquidity/rejection and volatility context.',\n    'Stops sit beyond the bot-selected invalidation structure with ATR buffer; targets prefer structure/liquidity objectives before expansion.',\n    'V3.6 Market Judgment retained: no score gate, no minimum score, no RR admission threshold and no signal cooldown.',")
w=w.replace("  historicalWinRateMode:'RESOLVED_TP_SL_ONLY'","  historicalWinRateMode:'RESOLVED_TP_SL_ONLY',\n  entryModel:'STRUCTURE_LIQUIDITY_CONTEXT',\n  stopModel:'INVALIDATION_STRUCTURE_PLUS_VOLATILITY_BUFFER',\n  targetModel:'LIQUIDITY_STRUCTURE_THEN_EXPANSION'")

new_tf=r'''function tfStats(rows){
  if(!rows||rows.length<55)return null;
  const closes=rows.map(x=>x.c),e20s=emaSeries(closes,20),e50=ema(closes,50),e20=e20s.at(-1),e20Prev=e20s[Math.max(19,e20s.length-6)],rr=rsi(closes,14),aa=atr(rows,14),last=rows.at(-1),prev=rows.at(-2);
  const prior=rows.slice(-34,-2),recent=rows.slice(-9,-1);
  const priorHigh=Math.max(...prior.map(x=>x.h)),priorLow=Math.min(...prior.map(x=>x.l)),recentHigh=Math.max(...recent.map(x=>x.h)),recentLow=Math.min(...recent.map(x=>x.l));
  if(![e20,e50,rr,aa,last?.c,priorHigh,priorLow,recentHigh,recentLow].every(Number.isFinite)||aa<=0)return null;
  const trend=last.c>e20&&e20>e50?1:last.c<e20&&e20<e50?-1:0,slope=e20Prev?((e20-e20Prev)/aa):0,momentum=rr>=52?1:rr<=48?-1:0;
  const body=Math.max(Math.abs(last.c-last.o),aa*.04),upperWick=Math.max(0,last.h-Math.max(last.o,last.c)),lowerWick=Math.max(0,Math.min(last.o,last.c)-last.l);
  const sweepHigh=last.h>priorHigh&&last.c<priorHigh&&upperWick>body*.65,sweepLow=last.l<priorLow&&last.c>priorLow&&lowerWick>body*.65;
  const bosUp=last.c>priorHigh,bosDown=last.c<priorLow,range=Math.max(priorHigh-priorLow,aa*.25),rangePosition=Math.max(0,Math.min(1,(last.c-priorLow)/range));
  const impulse=Math.abs(last.c-last.o)/aa,extensionAtr=Math.abs(last.c-e20)/aa;
  return {close:last.c,open:last.o,high:last.h,low:last.l,prevClose:prev?.c,ema20:e20,ema50:e50,rsi:rr,atr:aa,trend,slope,priorHigh,priorLow,recentHigh,recentLow,extensionAtr,momentum,sweepHigh,sweepLow,bosUp,bosDown,rangePosition,impulse,upperWickAtr:upperWick/aa,lowerWickAtr:lowerWick/aa};
}'''
w=sub1(w,r"function tfStats\(rows\)\{.*?\n\}\nconst intervalMap",new_tf+"\nconst intervalMap",'tfStats')

new_crypto=r'''function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const sameAB=a.trend!==0&&a.trend===b.trend,sameBC=b.trend!==0&&b.trend===c.trend;
  const nearHigh=(a.priorHigh-px)/a.atr,nearLow=(px-a.priorLow)/a.atr;
  const breakoutUp=(a.bosUp||(nearHigh>=-.12&&nearHigh<=.30))&&(a.momentum>=0||a.slope>0||a.impulse>.45);
  const breakoutDown=(a.bosDown||(nearLow>=-.12&&nearLow<=.30))&&(a.momentum<=0||a.slope<0||a.impulse>.45);
  let dir=0,regime='TRANSITION';
  if(a.sweepLow&&(b.trend>=0||c.trend>=0||b.momentum>=0)){dir=1;regime='LIQUIDITY_SWEEP_RECLAIM';}
  else if(a.sweepHigh&&(b.trend<=0||c.trend<=0||b.momentum<=0)){dir=-1;regime='LIQUIDITY_SWEEP_RECLAIM';}
  else if(sameAB&&(c.trend===0||c.trend===a.trend)){dir=a.trend;regime=a.extensionAtr>.48?'TREND_PULLBACK':'TREND_CONTINUATION';}
  else if(sameBC&&(a.trend===0||a.trend===b.trend)){dir=b.trend;regime='HTF_TREND_REJOIN';}
  else if(breakoutUp&&!breakoutDown){dir=1;regime='BREAKOUT_BUILDUP';}
  else if(breakoutDown&&!breakoutUp){dir=-1;regime='BREAKOUT_BUILDUP';}
  else if(a.trend!==0&&a.momentum===a.trend&&Math.sign(a.slope||0)===a.trend){dir=a.trend;regime='MOMENTUM_CONTINUATION';}
  else return null;

  const spread=Number(t.spreadBps??0),atr1=a.atr,spreadPx=Math.max(0,px*spread/10000),entryBuffer=Math.max(atr1*(style==='SCALP'?.055:.075),spreadPx*1.8);
  let orderType='MARKET',entry=px,entryModel='MARKET_AT_ACCEPTABLE_STRUCTURE_LOCATION';
  if(regime==='BREAKOUT_BUILDUP'){
    orderType='STOP';entry=dir>0?a.priorHigh+entryBuffer:a.priorLow-entryBuffer;entryModel='BREAKOUT_TRIGGER_BEYOND_LIQUIDITY';
  }else if(regime==='TREND_PULLBACK'||a.extensionAtr>.42||((dir>0&&px<a.ema20)||(dir<0&&px>a.ema20))){
    const raw=dir>0?Math.max(a.ema20,a.recentLow+.30*atr1):Math.min(a.ema20,a.recentHigh-.30*atr1);
    if((dir>0&&raw<px-entryBuffer*.35)||(dir<0&&raw>px+entryBuffer*.35)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_DYNAMIC_STRUCTURE';}
  }else if(regime==='MOMENTUM_CONTINUATION'&&a.impulse>.72){
    orderType='STOP';entry=px+dir*entryBuffer;entryModel='MOMENTUM_CONTINUATION_TRIGGER';
  }else if(regime==='LIQUIDITY_SWEEP_RECLAIM')entryModel='SWEEP_RECLAIM_MARKET_ENTRY';

  const stopBuffer=Math.max(atr1*(style==='SCALP'?.12:.17),spreadPx*2.6);
  let anchor;
  if(dir>0){
    if(regime==='LIQUIDITY_SWEEP_RECLAIM')anchor=Math.min(a.low,a.priorLow);
    else if(regime==='BREAKOUT_BUILDUP')anchor=Math.min(a.recentLow,a.priorHigh-.38*atr1);
    else anchor=Math.min(a.recentLow,a.ema50-.08*atr1);
  }else{
    if(regime==='LIQUIDITY_SWEEP_RECLAIM')anchor=Math.max(a.high,a.priorHigh);
    else if(regime==='BREAKOUT_BUILDUP')anchor=Math.max(a.recentHigh,a.priorLow+.38*atr1);
    else anchor=Math.max(a.recentHigh,a.ema50+.08*atr1);
  }
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer;
  let risk=Math.abs(entry-sl);if(!(risk>atr1*.18)) {risk=atr1*(style==='SCALP'?.82:1.12);sl=entry-dir*risk;}

  const target=(candidate,fallback,dirSign)=>dirSign>0?(Number(candidate)>fallback?Number(candidate):fallback):(Number(candidate)<fallback?Number(candidate):fallback);
  let tp1,tp2,tp3;
  if(dir>0){
    tp1=target(a.priorHigh,entry+risk*.95,1);
    tp2=target(b.priorHigh,Math.max(tp1+risk*.25,entry+risk*1.65),1);
    tp3=target(c.priorHigh,Math.max(tp2+risk*.30,entry+risk*(style==='SCALP'?2.25:2.65)),1);
  }else{
    tp1=target(a.priorLow,entry-risk*.95,-1);
    tp2=target(b.priorLow,Math.min(tp1-risk*.25,entry-risk*1.65),-1);
    tp3=target(c.priorLow,Math.min(tp2-risk*.30,entry-risk*(style==='SCALP'?2.25:2.65)),-1);
  }
  const rr=Math.abs(tp3-entry)/risk,spreadState=spread>(style==='SCALP'?12:30)?'WIDE':'NORMAL';
  const judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STRUCTURE SL/TP`;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,marketRegime:regime,judgment,entryModel,slModel:'INVALIDATION_SWING_LIQUIDITY_PLUS_ATR_SPREAD_BUFFER',tpModel:'STRUCTURE_LIQUIDITY_TARGETS_THEN_EXPANSION',invalidationLevel:Number(anchor.toPrecision(10)),executionCaution:spreadState,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread,sweepHigh:a.sweepHigh,sweepLow:a.sweepLow,bosUp:a.bosUp,bosDown:a.bosDown,recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[`${intervalMap[style].join('/')} structure/liquidity context`,dir>0?'bot reads bullish pressure':'bot reads bearish pressure',`regime ${regime}`,`entry ${entryModel}`,`SL beyond invalidation ${Number(anchor.toPrecision(8))} + volatility/spread buffer`,`TPs seek nearby and higher-timeframe liquidity before expansion`,`RSI ${a.rsi.toFixed(1)} • extension ${a.extensionAtr.toFixed(2)} ATR • spread ${spread.toFixed(2)} bps`]},'CRYPTO',style);
}'''
w=sub1(w,r"function buildCryptoSetup\(t,style,stats\)\{.*?\n\}\nasync function analyzeCryptoCandidate",new_crypto+"\nasync function analyzeCryptoCandidate",'crypto setup')

new_forex=r'''async function tvForexFrames(style){
  const f=style==='SCALP'?['5','15','60']:['60','240','1D'];
  const cols=['name','close','change'];for(const x of f)cols.push(`Recommend.All|${x}`);for(const x of f.slice(0,2))cols.push(`RSI|${x}`);for(const x of f.slice(0,2)){cols.push(`EMA20|${x}`);cols.push(`EMA50|${x}`);cols.push(`ATR|${x}`);cols.push(`open|${x}`);cols.push(`high|${x}`);cols.push(`low|${x}`);}
  const body={symbols:{tickers:FOREX.map(s=>`OANDA:${s}`),query:{types:[]}},columns:cols};
  const raw=await fetchJson('https://scanner.tradingview.com/forex/scan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)},9000);if(!Array.isArray(raw?.data))throw new Error('TV_FOREX_BAD_JSON');
  return raw.data.map(r=>{const d=r.d||[];let i=0;const symbol=canonical(d[i++]||String(r.s||'').split(':').pop()),close=num(d[i++]),change=num(d[i++]),recA=num(d[i++]),recB=num(d[i++]),recC=num(d[i++]),rsiA=num(d[i++]),rsiB=num(d[i++]);const a={ema20:num(d[i++]),ema50:num(d[i++]),atr:num(d[i++]),open:num(d[i++]),high:num(d[i++]),low:num(d[i++])},b={ema20:num(d[i++]),ema50:num(d[i++]),atr:num(d[i++]),open:num(d[i++]),high:num(d[i++]),low:num(d[i++])};return {symbol,close,change,recA,recB,recC,rsiA,rsiB,ema20A:a.ema20,ema50A:a.ema50,atrA:a.atr,openA:a.open,highA:a.high,lowA:a.low,ema20B:b.ema20,ema50B:b.ema50,atrB:b.atr,openB:b.open,highB:b.high,lowB:b.low,frames:f};});
}
function forexJudgmentSetup(r,px,style){
  if(!(px>0&&r.atrA>0&&r.atrB>0&&r.ema20A>0&&r.ema50A>0&&r.ema20B>0&&r.ema50B>0))return null;
  const emaA=r.ema20A>r.ema50A?1:r.ema20A<r.ema50A?-1:0,emaB=r.ema20B>r.ema50B?1:r.ema20B<r.ema50B?-1:0;
  const recA=r.recA>0?1:r.recA<0?-1:0,recB=r.recB>0?1:r.recB<0?-1:0,recC=r.recC>0?1:r.recC<0?-1:0;
  const atr=Math.max(r.atrA,r.atrB*(style==='SCALP'?.38:.45)),ext=(px-r.ema20A)/atr;
  const highA=r.highA>0?r.highA:px+.55*atr,lowA=r.lowA>0?r.lowA:px-.55*atr,openA=r.openA>0?r.openA:px;
  const highB=r.highB>0?r.highB:r.ema20B+r.atrB*.8,lowB=r.lowB>0?r.lowB:r.ema20B-r.atrB*.8;
  const body=Math.max(Math.abs(px-openA),atr*.05),lowerWick=Math.max(0,Math.min(px,openA)-lowA),upperWick=Math.max(0,highA-Math.max(px,openA));
  const bullReject=px>=openA&&lowerWick>Math.max(body*.9,atr*.16),bearReject=px<=openA&&upperWick>Math.max(body*.9,atr*.16);
  let dir=0,regime='TRANSITION';
  if(bullReject&&(emaB>=0||recB>=0)){dir=1;regime='LIQUIDITY_REJECTION';}
  else if(bearReject&&(emaB<=0||recB<=0)){dir=-1;regime='LIQUIDITY_REJECTION';}
  else if(emaA!==0&&emaA===emaB&&(recC===0||recC===emaA)){dir=emaA;regime=Math.abs(ext)>.48?'TREND_PULLBACK':'TREND_CONTINUATION';}
  else if(recA!==0&&recA===recB&&(recC===0||recC===recA)){dir=recA;regime='MOMENTUM_CONTINUATION';}
  else if(recA!==0&&((recA>0&&r.rsiA>=50)||(recA<0&&r.rsiA<=50))){dir=recA;regime='TRANSITION_MOMENTUM';}
  else return null;

  const entryBuffer=atr*(style==='SCALP'?.055:.075),strongImpulse=Math.abs(Number(r.recA||0))>.45&&Math.abs(Number(r.recB||0))>.25;
  let orderType='MARKET',entry=px,entryModel='MARKET_AT_ACCEPTABLE_STRUCTURE_LOCATION';
  if(strongImpulse&&Math.abs(ext)<.38&&regime!=='LIQUIDITY_REJECTION'){orderType='STOP';entry=dir>0?highA+entryBuffer:lowA-entryBuffer;regime='BREAKOUT_CONFIRMATION';entryModel='BREAKOUT_TRIGGER_OUTSIDE_CURRENT_STRUCTURE';}
  else if(regime==='TREND_PULLBACK'||Math.abs(ext)>.42||((dir>0&&px<r.ema20A)||(dir<0&&px>r.ema20A))){const raw=dir>0?Math.max(r.ema20A,lowA+.30*atr):Math.min(r.ema20A,highA-.30*atr);if((dir>0&&raw<px-entryBuffer*.3)||(dir<0&&raw>px+entryBuffer*.3)){orderType='LIMIT';entry=raw;entryModel='PULLBACK_TO_EMA_STRUCTURE';}}
  else if(regime==='LIQUIDITY_REJECTION')entryModel='REJECTION_RECLAIM_MARKET_ENTRY';

  const stopBuffer=atr*(style==='SCALP'?.13:.18);let anchor;
  if(dir>0){anchor=regime==='LIQUIDITY_REJECTION'?lowA:regime==='BREAKOUT_CONFIRMATION'?Math.min(lowA,r.ema20A-.35*atr):Math.min(lowA,r.ema50A-.08*atr);if(style==='SWING'&&lowB<entry&&entry-lowB<2.8*atr)anchor=Math.min(anchor,lowB);}
  else{anchor=regime==='LIQUIDITY_REJECTION'?highA:regime==='BREAKOUT_CONFIRMATION'?Math.max(highA,r.ema20A+.35*atr):Math.max(highA,r.ema50A+.08*atr);if(style==='SWING'&&highB>entry&&highB-entry<2.8*atr)anchor=Math.max(anchor,highB);}
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl);if(!(risk>atr*.18)){risk=atr*(style==='SCALP'?.88:1.18);sl=entry-dir*risk;}
  const pick=(candidate,fallback,sign)=>sign>0?(Number(candidate)>fallback?Number(candidate):fallback):(Number(candidate)<fallback?Number(candidate):fallback);
  let tp1,tp2,tp3;if(dir>0){tp1=pick(highA,entry+risk*.95,1);tp2=pick(highB,Math.max(tp1+risk*.25,entry+risk*1.65),1);tp3=Math.max(tp2+risk*.30,entry+risk*(style==='SCALP'?2.20:2.60));}else{tp1=pick(lowA,entry-risk*.95,-1);tp2=pick(lowB,Math.min(tp1-risk*.25,entry-risk*1.65),-1);tp3=Math.min(tp2-risk*.30,entry-risk*(style==='SCALP'?2.20:2.60));}
  const rr=Math.abs(tp3-entry)/risk,judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STRUCTURE SL/TP`;
  return stampMarketJudgment({market:'FOREX',style,symbol:r.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry,sl,tp1,tp2,tp3,tp:tp3,targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:'EXNESS_MT5+TRADINGVIEW_FOREX',executionPriceAuthority:'EXNESS_MT5',marketRegime:regime,judgment,entryModel,slModel:'INVALIDATION_STRUCTURE_PLUS_ATR_BUFFER',tpModel:'LOCAL_HTF_STRUCTURE_THEN_EXPANSION',invalidationLevel:anchor,technicalAtIssue:{frames:r.frames,recommend:[r.recA,r.recB,r.recC],rsi:[r.rsiA,r.rsiB],atr:[r.atrA,r.atrB],ema20:[r.ema20A,r.ema20B],ema50:[r.ema50A,r.ema50B],extensionAtr:Number(ext.toFixed(2)),localStructure:[lowA,highA],htfStructure:[lowB,highB],bullReject,bearReject},rationale:[`${r.frames.join('/')} context with local/HTF structure`,dir>0?'bot reads bullish pressure':'bot reads bearish pressure',`regime ${regime}`,`entry ${entryModel}`,`SL beyond invalidation ${Number(anchor.toPrecision(8))} + volatility buffer`,`TP1/TP2 use local and HTF structure when available; TP3 extends only after those objectives`,`RSI ${Number(r.rsiA).toFixed(1)} / ${Number(r.rsiB).toFixed(1)}`]},'FOREX',style);
}'''
w=sub1(w,r"async function tvForexFrames\(style\)\{.*?\n\}\nfunction forexJudgmentSetup\(r,px,style\)\{.*?\n\}\nasync function scanForexJudgment",new_forex+"\nasync function scanForexJudgment",'forex block')

WORKER.write_text(w)

j=ACT.read_text()
j=j.replace('private static final String APP_VERSION="3.6.0";','private static final String APP_VERSION="3.7.0";')
j=j.replace('MARKET JUDGMENT • REALTIME EXECUTION • V3.6','STRUCTURE • LIQUIDITY • REALTIME • V3.7')
j=j.replace('c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("BOT DECISION",s.optString("judgment","BOT MARKET JUDGMENT"),CYAN));', 'c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("ENTRY MODEL",s.optString("entryModel","BOT MARKET JUDGMENT").replace(\'_\',\' \'),YELLOW));c.addView(line("SL MODEL",s.optString("slModel","STRUCTURE INVALIDATION").replace(\'_\',\' \'),RED));c.addView(line("TP MODEL",s.optString("tpModel","STRUCTURE TARGETS").replace(\'_\',\' \'),GREEN));c.addView(line("BOT DECISION",s.optString("judgment","BOT MARKET JUDGMENT"),CYAN));')
ACT.write_text(j)

m=MON.read_text().replace('SignalHub V3.6 • LIVE MONITOR','SignalHub V3.7 • LIVE MONITOR')
MON.write_text(m)

g=GRADLE.read_text().replace('versionCode 12','versionCode 13').replace("versionName '3.6.0'","versionName '3.7.0'")
GRADLE.write_text(g)
print('patched SignalHub V3.7 structure/liquidity entries and adaptive SL/TP')
