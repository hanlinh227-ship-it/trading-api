from pathlib import Path
import re

WORKER=Path('signalhub-worker/gateway-v3.js')
ACT=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
MON=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/MonitorService.java')
GRADLE=Path('signalhub-android/app/build.gradle')


def sub1(text, pattern, repl, flags=0, label='pattern'):
    out,n=re.subn(pattern,repl,text,count=1,flags=flags)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out

w=WORKER.read_text()
w=w.replace("const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.5.0';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.6.0';")
w=w.replace("versionCode: 11,\n  versionName: '3.5.0',\n  title: 'SignalHub 3.5.0',","versionCode: 12,\n  versionName: '3.6.0',\n  title: 'SignalHub 3.6.0',")
w=w.replace("artifactName: 'SignalHub-Android-v3.5.0',","artifactName: 'SignalHub-Android-v3.6.0',")
w=w.replace("    'V3.5 strict admission gate: fewer but higher-quality signals; historical win rate remains resolved TP/SL only.',","    'V3.6 Market Judgment Engine: no score gate, no minimum score, no RR admission threshold and no signal cooldown.',\n    'Bot classifies regime and actively chooses MARKET / LIMIT / STOP / NO TRADE from current market structure.',")
w=w.replace("    'No score is presented as a guaranteed win probability.'","    'No setup score is generated or displayed; historical win rate remains resolved TP/SL only.'")

judgment_helpers=r'''const MARKET_JUDGMENT_POLICY = Object.freeze({
  name:'BOT_MARKET_JUDGMENT',
  scoreGate:false,
  timeGate:false,
  rrGate:false,
  orderRouting:'DYNAMIC_MARKET_LIMIT_STOP',
  historicalWinRateMode:'RESOLVED_TP_SL_ONLY'
});
function validSignalStructure(signal){
  if(!signal)return false;
  const entry=Number(signal.entry||0),sl=Number(signal.sl||0),tp=Number(signal.tp3||signal.tp||0);
  if(!(entry>0&&sl>0&&tp>0&&Math.abs(entry-sl)>0))return false;
  const side=String(signal.side||'').toUpperCase();
  const dir=(side==='LONG'||side==='BUY')?1:(side==='SHORT'||side==='SELL')?-1:0;
  if(!dir)return false;
  if(dir>0&&!(sl<entry&&tp>entry))return false;
  if(dir<0&&!(sl>entry&&tp<entry))return false;
  return ['MARKET','LIMIT','STOP'].includes(String(signal.orderType||'MARKET').toUpperCase());
}
function stampMarketJudgment(signal,market,style){
  signal.decisionMode='BOT_MARKET_JUDGMENT';
  signal.admissionMode='NO_SCORE_NO_TIME_GATE';
  signal.entryState=String(signal.orderType||'MARKET').toUpperCase()==='MARKET'?'LIVE':'PENDING_ENTRY';
  signal.market=String(market||signal.market||'FOREX').toUpperCase();
  signal.style=String(style||signal.style||'SCALP').toUpperCase();
  delete signal.score;delete signal.qualityGrade;delete signal.scoreMeaning;
  delete signal.admissionGate;delete signal.admissionMinScore;delete signal.admissionMinRR;
  return signal;
}
'''
w=sub1(w,r"const V35_QUALITY_POLICY = Object\.freeze\(\{.*?function stampV35Quality\(signal,market,style\)\{.*?\n\}\n",judgment_helpers,flags=re.S,label='replace V35 policy')

crypto_discovery=r'''async function cryptoDiscovery(url,env){
  const style=String(url.searchParams.get('style')||'scalp').toUpperCase()==='SWING'?'SWING':'SCALP';
  const limit=Math.min(100,Math.max(5,Number(url.searchParams.get('limit')||40))),snap=await loadCryptoSnapshot(env),all=snap.rows;
  const candidates=all.filter(t=>Number(t.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,limit).map(t=>({...t,marketRead:'DISCOVERY_FOR_BOT_JUDGMENT'}));
  return json({ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,candidates,classification:'DISCOVERY_ONLY_NOT_TRADE_SIGNAL',decisionMode:'BOT_MARKET_JUDGMENT',note:'No composite score is used. Candidates are handed to the market-judgment engine for regime classification and entry routing.',receivedAt:snap.receivedAt});
}
'''
w=sub1(w,r"function discoveryScore\(t,style\)\{.*?\n\}\nasync function cryptoDiscovery\(url,env\)\{.*?\n\}\n",crypto_discovery,flags=re.S,label='replace crypto discovery score')

crypto_setup=r'''function buildCryptoSetup(t,style,stats){
  const [a,b,c]=stats,px=Number(t.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c))return null;
  const sameAB=a.trend!==0&&a.trend===b.trend,sameBC=b.trend!==0&&b.trend===c.trend;
  const nearHigh=(a.priorHigh-px)/a.atr,nearLow=(px-a.priorLow)/a.atr;
  const breakoutUp=nearHigh>=-.18&&nearHigh<=.45&&(a.momentum>=0||a.slope>0);
  const breakoutDown=nearLow>=-.18&&nearLow<=.45&&(a.momentum<=0||a.slope<0);
  let dir=0,regime='TRANSITION';
  if(sameAB&&(c.trend===0||c.trend===a.trend)){dir=a.trend;regime=a.extensionAtr>.55?'TREND_PULLBACK':'TREND_CONTINUATION';}
  else if(sameBC&&(a.trend===0||a.trend===b.trend)){dir=b.trend;regime='HTF_TREND_REJOIN';}
  else if(breakoutUp&&!breakoutDown){dir=1;regime='BREAKOUT_BUILDUP';}
  else if(breakoutDown&&!breakoutUp){dir=-1;regime='BREAKOUT_BUILDUP';}
  else if(a.trend!==0&&a.momentum===a.trend&&Math.sign(a.slope||0)===a.trend){dir=a.trend;regime='MOMENTUM_CONTINUATION';}
  else return null;

  const spread=Number(t.spreadBps??0),atr1=a.atr;
  let orderType='MARKET',entry=px;
  if(regime==='BREAKOUT_BUILDUP'){
    orderType='STOP';entry=dir>0?a.priorHigh+.08*atr1:a.priorLow-.08*atr1;
  }else if(a.extensionAtr>.48||((dir>0&&px<a.ema20)||(dir<0&&px>a.ema20))){
    orderType='LIMIT';entry=a.ema20;
  }
  const structure=dir>0?Math.min(a.priorLow,entry-(style==='SCALP'?1.05:1.45)*atr1):Math.max(a.priorHigh,entry+(style==='SCALP'?1.05:1.45)*atr1);
  const sl=dir>0?Math.min(entry-.82*atr1,structure-.06*atr1):Math.max(entry+.82*atr1,structure+.06*atr1),risk=Math.abs(entry-sl);if(!(risk>0))return null;
  const rr=regime==='BREAKOUT_BUILDUP'?(style==='SCALP'?2.25:2.6):regime==='TREND_PULLBACK'?(style==='SCALP'?2.15:2.45):(style==='SCALP'?1.95:2.25),tp=entry+dir*risk*rr;
  const spreadState=spread>(style==='SCALP'?12:30)?'WIDE':'NORMAL';
  const judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} CONTEXT`;
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp:Number(tp.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,marketRegime:regime,judgment,executionCaution:spreadState,technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),extensionAtr:Number(a.extensionAtr.toFixed(2)),tfTrend:[a.trend,b.trend,c.trend],spreadBps:spread},rationale:[`${intervalMap[style].join('/')} market context read`,dir>0?'bot reads bullish pressure':'bot reads bearish pressure',`regime ${regime}`,`RSI ${a.rsi.toFixed(1)}`,`extension ${a.extensionAtr.toFixed(2)} ATR`,`spread ${spread.toFixed(2)} bps • ${spreadState}`,orderType==='LIMIT'?'bot waits for pullback to entry':orderType==='STOP'?'bot requires price trigger through breakout level':'bot accepts current market price']},'CRYPTO',style);
}
async function analyzeCryptoCandidate(t,style){try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildCryptoSetup(t,style,stats)}catch{return null;}}
'''
w=sub1(w,r"function buildCryptoSetup\(t,style,stats\)\{.*?\n\}\nasync function analyzeCryptoCandidate\(t,style\)\{.*?\n",crypto_setup,flags=re.S,label='replace crypto setup')

maybe_create=r'''async function maybeCreateV31(env,market,style,setups){
  if(!env?.SIGNALS_KV)return[];
  const current=await getV31Signals(env,market,style),active=current.filter(x=>x.status==='PENDING'||x.status==='OPEN'),made=[];
  for(const rawSetup of setups){
    const setup=stampMarketJudgment({...rawSetup},market,style);
    if(!validSignalStructure(setup))continue;
    if(active.some(x=>x.symbol===setup.symbol))continue;
    const ptr=await env.SIGNALS_KV.get(activePointer(market,style,setup.symbol));if(ptr)continue;
    const issuedAt=nowIso(),id=`V36-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`;
    const s=normalizeDisplaySignal({...setup,id,issuedAt,lastCheckedAt:issuedAt,outcome:null,resultR:null,engineVersion:V3_VERSION,checkpoint:CHECKPOINT},market,style);
    await writeV31Signal(env,s);made.push(s);active.push(s);
  }
  return made;
}
'''
w=sub1(w,r"async function maybeCreateV31\(env,market,style,setups,maxNew=1\)\{.*?\n\}\nasync function scanCrypto",maybe_create+"async function scanCrypto",flags=re.S,label='replace creation cooldown/gate')

scan_crypto=r'''async function scanCrypto(env,style){
  const snap=await loadCryptoSnapshot(env),all=snap.rows;
  const ranked=all.filter(x=>Number(x.lastPrice)>0).sort((a,b)=>Number(b.turnover24h||0)-Number(a.turnover24h||0)).slice(0,style==='SCALP'?12:10);
  const priceMap=new Map(all.map(x=>[x.symbol,x.lastPrice])),trackerEvents=await trackV31Signals(env,'CRYPTO',style,priceMap);
  const analyses=(await Promise.all(ranked.map(t=>analyzeCryptoCandidate(t,style)))).filter(Boolean);
  const created=await maybeCreateV31(env,'CRYPTO',style,analyses);
  return {ok:true,version:V3_VERSION,market:'CRYPTO',style,provider:snap.provider,live:snap.live!==false,scanned:all.length,deepAnalyzed:ranked.length,actionable:analyses.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:analyses.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score gate and no signal cooldown. The bot classifies regime and routes each actionable idea as MARKET, LIMIT or STOP.'};
}
'''
w=sub1(w,r"async function scanCrypto\(env,style\)\{.*?\n\}\n\nasync function exnessQuoteMap",scan_crypto+"\nasync function exnessQuoteMap",flags=re.S,label='replace scan crypto')

forex_block=r'''async function tvForexFrames(style){
  const f=style==='SCALP'?['5','15','60']:['60','240','1D'];
  const cols=['name','close','change'];for(const x of f)cols.push(`Recommend.All|${x}`);for(const x of f.slice(0,2))cols.push(`RSI|${x}`);for(const x of f.slice(0,2)){cols.push(`EMA20|${x}`);cols.push(`EMA50|${x}`);cols.push(`ATR|${x}`);}
  const body={symbols:{tickers:FOREX.map(s=>`OANDA:${s}`),query:{types:[]}},columns:cols};
  const raw=await fetchJson('https://scanner.tradingview.com/forex/scan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)},9000);if(!Array.isArray(raw?.data))throw new Error('TV_FOREX_BAD_JSON');
  return raw.data.map(r=>{const d=r.d||[];return {symbol:canonical(d[0]||String(r.s||'').split(':').pop()),close:num(d[1]),change:num(d[2]),recA:num(d[3]),recB:num(d[4]),recC:num(d[5]),rsiA:num(d[6]),rsiB:num(d[7]),ema20A:num(d[8]),ema50A:num(d[9]),atrA:num(d[10]),ema20B:num(d[11]),ema50B:num(d[12]),atrB:num(d[13]),frames:f};});
}
function forexJudgmentSetup(r,px,style){
  if(!(px>0&&r.atrA>0&&r.atrB>0&&r.ema20A>0&&r.ema50A>0&&r.ema20B>0&&r.ema50B>0))return null;
  const emaA=r.ema20A>r.ema50A?1:r.ema20A<r.ema50A?-1:0,emaB=r.ema20B>r.ema50B?1:r.ema20B<r.ema50B?-1:0;
  const recA=r.recA>0?1:r.recA<0?-1:0,recB=r.recB>0?1:r.recB<0?-1:0,recC=r.recC>0?1:r.recC<0?-1:0;
  const atr=Math.max(r.atrA,r.atrB*(style==='SCALP'?.38:.45)),ext=(px-r.ema20A)/atr;
  let dir=0,regime='TRANSITION';
  if(emaA!==0&&emaA===emaB&&(recC===0||recC===emaA)){dir=emaA;regime=Math.abs(ext)>.55?'TREND_PULLBACK':'TREND_CONTINUATION';}
  else if(recA!==0&&recA===recB&&(recC===0||recC===recA)){dir=recA;regime='MOMENTUM_CONTINUATION';}
  else if(recA!==0&&((recA>0&&r.rsiA>=50)||(recA<0&&r.rsiA<=50))){dir=recA;regime='TRANSITION_MOMENTUM';}
  else return null;

  let orderType='MARKET',entry=px;
  const strongImpulse=Math.abs(Number(r.recA||0))>.45&&Math.abs(Number(r.recB||0))>.25;
  if(strongImpulse&&Math.abs(ext)<.45){orderType='STOP';entry=px+dir*atr*(style==='SCALP'?.08:.12);regime='BREAKOUT_CONFIRMATION';}
  else if(Math.abs(ext)>.46||((dir>0&&px<r.ema20A)||(dir<0&&px>r.ema20A))){orderType='LIMIT';entry=r.ema20A;}
  const risk=atr*(style==='SCALP'?1.05:1.48),sl=entry-dir*risk;
  const rr=regime==='BREAKOUT_CONFIRMATION'?(style==='SCALP'?2.2:2.55):regime==='TREND_PULLBACK'?(style==='SCALP'?2.1:2.4):(style==='SCALP'?1.9:2.25),tp=entry+dir*risk*rr;
  const judgment=`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} CONTEXT`;
  return stampMarketJudgment({market:'FOREX',style,symbol:r.symbol,side:dir>0?'LONG':'SHORT',orderType,status:orderType==='MARKET'?'OPEN':'PENDING',entry,sl,tp,targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:'EXNESS_MT5+TRADINGVIEW_FOREX',executionPriceAuthority:'EXNESS_MT5',marketRegime:regime,judgment,technicalAtIssue:{frames:r.frames,recommend:[r.recA,r.recB,r.recC],rsi:[r.rsiA,r.rsiB],atr:[r.atrA,r.atrB],ema20:[r.ema20A,r.ema20B],ema50:[r.ema50A,r.ema50B],extensionAtr:Number(ext.toFixed(2))},rationale:[`${r.frames.join('/')} market context read`,dir>0?'bot reads bullish pressure':'bot reads bearish pressure',`regime ${regime}`,`RSI ${Number(r.rsiA).toFixed(1)} / ${Number(r.rsiB).toFixed(1)}`,orderType==='LIMIT'?'bot waits for pullback to entry':orderType==='STOP'?'bot waits for continuation trigger':'bot accepts current Exness price']},'FOREX',style);
}
async function scanForexJudgment(env,style){
  const ex=await exnessQuoteMap(env);if(ex.state==='OFFLINE'||ex.state==='STALE')return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'NO_CURRENT_EXNESS_QUOTE',created:0,state:ex.state,ageMs:ex.ageMs,decisionPolicy:MARKET_JUDGMENT_POLICY,note:'No score/time gate is applied, but stale data is never treated as a current market price.'};
  const rows=await tvForexFrames(style),priceMap=ex.map,trackerEvents=await trackV31Signals(env,'FOREX',style,priceMap),setups=rows.map(r=>forexJudgmentSetup(r,priceMap.get(r.symbol),style)).filter(Boolean),created=await maybeCreateV31(env,'FOREX',style,setups);
  return {ok:true,version:V3_VERSION,market:'FOREX',style,status:'OK',state:ex.state,scanned:rows.length,actionable:setups.length,created:created.length,newSignals:created,trackerEvents,topAnalyses:setups.slice(0,8),decisionPolicy:MARKET_JUDGMENT_POLICY};
}
async function scanForexScalp(env){return scanForexJudgment(env,'SCALP');}
async function scanForexSwing(env){return scanForexJudgment(env,'SWING');}
function normalizeDisplaySignal'''
w=sub1(w,r"async function tvForexSwing\(\)\{.*?\n\}\nfunction forexSwingSetup\(r,px\)\{.*?\nasync function scanForexSwing\(env\)\{.*?\n\}\nfunction normalizeDisplaySignal",forex_block,flags=re.S,label='replace forex judgment engines')

w=w.replace("  const score=Number(s.score||0);\n  s.qualityGrade=score>=95?'A+':score>=90?'A':score>=85?'A-':score>=80?'B+':'B';\n  s.scoreMeaning='SETUP_QUALITY_NOT_WIN_PROBABILITY';\n", "  s.decisionMode=String(s.decisionMode||'BOT_MARKET_JUDGMENT');\n  s.admissionMode=String(s.admissionMode||'NO_SCORE_NO_TIME_GATE');\n  delete s.score;delete s.qualityGrade;delete s.scoreMeaning;\n")

unified=r'''async function unifiedSignals(url,env){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX';
  const style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  const status=String(url.searchParams.get('status')||'active').toLowerCase();
  const limit=Math.min(300,Math.max(1,Number(url.searchParams.get('limit')||120)));
  let rows=await getV31Signals(env,market,style);rows=rows.map(x=>normalizeDisplaySignal(x,market,style));
  rows=rows.filter(s=>status==='all'||(status==='active'&&(s.status==='PENDING'||s.status==='OPEN'))||(status==='closed'&&s.status==='CLOSED')||String(s.status||'').toLowerCase()===status).slice(0,limit);
  let dataHealth=null;if(market==='FOREX'){const ex=await exnessQuoteMap(env);dataHealth={provider:'EXNESS_MT5',state:ex.state,quoteAgeMs:ex.ageMs};}
  return json({ok:true,version:V3_VERSION,market,style,partitionKey:`${market}:${style}`,status,count:rows.length,dataHealth,decisionPolicy:MARKET_JUDGMENT_POLICY,signals:rows});
}

async function unifiedPerformance(url,env){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP',rows=await getV31Signals(env,market,style),active=rows.filter(s=>s.status==='PENDING'||s.status==='OPEN'),resolved=rows.filter(s=>s.status==='CLOSED'&&(s.outcome==='TP'||s.outcome==='SL')),tp=resolved.filter(s=>s.outcome==='TP').length,sl=resolved.filter(s=>s.outcome==='SL').length,netR=resolved.reduce((a,s)=>a+Number(s.resultR||0),0),wr=resolved.length?tp/resolved.length*100:null;
  return json({ok:true,version:V3_VERSION,market,style,performance:{total:rows.length,active:active.length,pending:active.filter(s=>s.status==='PENDING').length,open:active.filter(s=>s.status==='OPEN').length,resolved:resolved.length,tp,sl,winRateResolved:wr,netRResolved:Number(netR.toFixed(2)),sampleAdequate:resolved.length>=30,winRateLabel:resolved.length?`${wr.toFixed(1)}% (${tp}/${resolved.length})`:'CHƯA CÓ MẪU'}});
}
async function scanRoute(url,env,ctx){
  const market=String(url.searchParams.get('market')||'FOREX').toUpperCase()==='CRYPTO'?'CRYPTO':'FOREX',style=String(url.searchParams.get('style')||'SCALP').toUpperCase()==='SWING'?'SWING':'SCALP';
  if(market==='CRYPTO')return json(await scanCrypto(env,style));
  return json(await scanForexJudgment(env,style));
}
'''
w=sub1(w,r"async function unifiedSignals\(url,env\)\{.*?\n\}\n\nasync function unifiedPerformance\(url,env\)\{.*?\n\}\nasync function scanRoute\(url,env,ctx\)\{.*?\n\}\n",unified,flags=re.S,label='replace unified signals/perf/scan')

w=w.replace("forex:{executionPriceAuthority:'EXNESS_MT5',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME_WEBSOCKET':'KV_FALLBACK',scalp:'LEGACY_2.1_QUALITY_ENGINE',swing:'V31_SEPARATE_1H_4H_1D_ENGINE'},crypto:{priceAuthority:'BYBIT_PREFERRED_WITH_LABELED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'V31_MULTI_TF_ENGINE',swing:'V31_MULTI_TF_ENGINE',antiFomo:true}","forex:{executionPriceAuthority:'EXNESS_MT5',transport:mt5LiveStub(env)?'DURABLE_OBJECT_REALTIME_WEBSOCKET':'KV_FALLBACK',scalp:'V36_MARKET_JUDGMENT_5M_15M_1H',swing:'V36_MARKET_JUDGMENT_1H_4H_1D'},crypto:{priceAuthority:'BYBIT_PREFERRED_WITH_LABELED_OKX_BINANCE_FALLBACK',universe:'USDT_PERPETUAL',scalp:'V36_MARKET_JUDGMENT_MULTI_TF',swing:'V36_MARKET_JUDGMENT_MULTI_TF',antiFomo:false}")
w=w.replace("winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'","decisionPolicy:MARKET_JUDGMENT_POLICY,winRatePolicy:'HISTORICAL_RESOLVED_TP_SL_ONLY_NOT_PREDICTED_PROBABILITY'")
w=w.replace("ctx.waitUntil((async()=>{await scanForexSwing(env).catch(()=>{});await sleep(150);await scanCrypto(env,'SCALP').catch(()=>{});await sleep(150);await scanCrypto(env,'SWING').catch(()=>{});})());","ctx.waitUntil((async()=>{await scanForexScalp(env).catch(()=>{});await sleep(100);await scanForexSwing(env).catch(()=>{});await sleep(100);await scanCrypto(env,'SCALP').catch(()=>{});await sleep(100);await scanCrypto(env,'SWING').catch(()=>{});})());")

# Hard checks: no admission score/cooldown logic remains in active V3.6 engine.
for bad in ['V35_QUALITY_POLICY','passesV35QualityGate','stampV35Quality','admissionMinScore','admissionMinRR','minGap=','score<threshold','if(score<']:
    if bad in w:
        raise SystemExit(f'worker still contains forbidden gate: {bad}')
WORKER.write_text(w)

# Android UI: remove score language and present bot market read instead.
a=ACT.read_text()
a=a.replace('private static final String APP_VERSION="3.5.0";','private static final String APP_VERSION="3.6.0";')
a=a.replace('REALTIME EXECUTION INTELLIGENCE • V3.5','MARKET JUDGMENT • REALTIME EXECUTION • V3.6')
a=a.replace('.append(\'|\').append(s.optInt("score",0))','')
a=a.replace('TextView grade=chip(s.optString("qualityGrade",grade(s.optInt("score",0)))+" • "+s.optInt("score",0)+"/100",BLUE);LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-2,-2);gp.setMargins(dp(7),0,0,0);h.addView(grade,gp);','TextView regime=chip(s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE);LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-2,-2);gp.setMargins(dp(7),0,0,0);h.addView(regime,gp);')
a=a.replace('c.addView(tv("Setup quality "+s.optInt("score",0)+"/100 • "+historicalWr(market,signalStyle),9,MUTED,false));','c.addView(tv("BOT • "+s.optString("judgment",s.optString("marketRegime","MARKET JUDGMENT").replace(\'_\',\' \'))+" • "+historicalWr(market,signalStyle),9,MUTED,false));')
a=a.replace('c.addView(line("SETUP QUALITY",s.optInt("score",0)+"/100 • "+s.optString("qualityGrade",grade(s.optInt("score",0))),BLUE));c.addView(tv("Điểm setup không phải xác suất thắng. "+historicalWr(market,signalStyle)+".",9,YELLOW,false));','c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace(\'_\',\' \'),BLUE));c.addView(line("BOT DECISION",s.optString("judgment","BOT MARKET JUDGMENT"),CYAN));c.addView(tv("Không chấm điểm • không score gate • không cooldown tín hiệu. "+historicalWr(market,signalStyle)+".",9,YELLOW,false));')
a=a.replace('ui.addView(line("Quality Gate","V3.5 STRICT",YELLOW));ui.addView(line("Forex Scalp","score ≥90 • RR ≥2.0",TEXT));ui.addView(line("Forex Swing","score ≥90 • RR ≥2.3",TEXT));ui.addView(line("Crypto Scalp","score ≥92 • RR ≥2.0",TEXT));ui.addView(line("Crypto Swing","score ≥90 • RR ≥2.3",TEXT));','ui.addView(line("Decision Engine","BOT MARKET JUDGMENT",CYAN));ui.addView(line("Score Gate","OFF",GREEN));ui.addView(line("Signal Cooldown","OFF",GREEN));ui.addView(line("Entry Routing","MARKET / LIMIT / STOP tự động",TEXT));')
a=a.replace('note.addView(tv("WATCH/PENDING không được tính thắng thua. Setup score không phải win probability.",9,MUTED,false));','note.addView(tv("WATCH/PENDING không được tính thắng thua. Bot không dùng điểm số để quyết định entry.",9,MUTED,false));')
a=a.replace('rule.addView(tv("FRESHNESS GATE",12,CYAN,true));rule.addView(tv("LIVE → được phép đánh giá entry. DELAYED/STALE/OFFLINE → app giữ dữ liệu cũ để xem nhưng không được coi là quote live mới.",10,MUTED,false));','rule.addView(tv("DATA INTEGRITY",12,CYAN,true));rule.addView(tv("Không có score/time gate. Quote mất kết nối vẫn phải được gắn DELAYED/STALE/OFFLINE thay vì giả thành giá live.",10,MUTED,false));')
a=a.replace('private String grade(int score){return score>=95?"A+":score>=90?"A":score>=85?"A-":score>=80?"B+":"B";}\n','')
ACT.write_text(a)

m=MON.read_text()
m=m.replace('b.append(" • Setup ").append(s.optInt("score",0)).append("/100");','String regime=s.optString("marketRegime","").replace(\'_\',\' \');if(!regime.isEmpty())b.append(" • ").append(regime);')
m=m.replace('SignalHub V3.3 • LIVE MONITOR','SignalHub V3.6 • LIVE MONITOR')
MON.write_text(m)

g=GRADLE.read_text().replace('versionCode 11','versionCode 12').replace("versionName '3.5.0'","versionName '3.6.0'")
GRADLE.write_text(g)

print('patched SignalHub V3.6 market judgment / no score / no cooldown')
