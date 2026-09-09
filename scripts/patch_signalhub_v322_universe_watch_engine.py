from pathlib import Path

W=Path('signalhub-worker/gateway-v3.js')
A=Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
G=Path('signalhub-android/app/build.gradle')
w=W.read_text();a=A.read_text();g=G.read_text()

def rep(text,old,new,label,count=1):
    if old not in text: raise SystemExit('missing '+label)
    return text.replace(old,new,count)

# Release identity
w=rep(w,'SIGNALHUB-V3-GATEWAY-3.21.0','SIGNALHUB-V3-GATEWAY-3.22.0','worker version')
a=rep(a,'private static final String APP_VERSION="3.21.0";','private static final String APP_VERSION="3.22.0";','app version')
g=rep(g,'versionCode 28','versionCode 29','version code')
g=rep(g,"versionName '3.21.0'","versionName '3.22.0'",'version name')
w=w.replace("versionCode: 28,\n  versionName: '3.21.0',","versionCode: 29,\n  versionName: '3.22.0',",1)
w=w.replace("title: 'SignalHub 3.21 Standardized Data + Ideal Watchlist'","title: 'SignalHub 3.22 Universe Watch + Refined Market Read'",1)
w=w.replace("artifactName: 'SignalHub-Android-v3.21.0-Standardized-Watch-Ideal'","artifactName: 'SignalHub-Android-v3.22.0-Universe-Watch-Refined-Read'",1)
w=w.replace("const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_07';","const CHECKPOINT = 'SIGNALHUB_V3_CHECKPOINT_14';",1)

# V3.22 style-specific market read. This is categorical evidence, not a predicted score.
needle='async function analyzeCryptoCandidate(t,style){'
if needle not in w: raise SystemExit('analyzeCryptoCandidate missing')
helper=r'''function v322MarketRead(t,style,stats,setup){
  const [a,b,c]=stats,side=String(setup?.side||'').toUpperCase(),dir=side==='LONG'||side==='BUY'?1:-1;
  const spread=Math.max(0,Number(t?.spreadBps||0)),turnover=Math.max(0,Number(t?.turnover24h||t?.turnover24hQuote||0)),move=Math.abs(Number(t?.change24hPct||0)),fund=t?.fundingRate==null?null:Math.abs(Number(t.fundingRate)),oi=t?.openInterestValue==null?null:Number(t.openInterestValue);
  const execEvent=dir>0?(a.sweepLow||a.bullDisplacement||a.emaReclaimUp||a.bosUp):(a.sweepHigh||a.bearDisplacement||a.emaReclaimDown||a.bosDown);
  const execMomentum=a.momentum!==-dir,midMomentum=b.momentum!==-dir,execSlope=dir>0?a.slope>=-.08:a.slope<=.08;
  const extension=Math.abs(Number(a.extensionAtr||0));
  let contextAligned=false,contextStrong=false,marketEntryReady=false,hardConflict=false,contextLabel='MIXED';
  if(style==='SWING'){
    contextAligned=b.trend===dir&&c.trend===dir;
    contextStrong=contextAligned&&(b.momentum===dir||c.momentum===dir)&&(dir>0?b.slope>=-.05:b.slope<=.05);
    hardConflict=b.trend===-dir||c.trend===-dir||!contextAligned;
    marketEntryReady=contextStrong&&execMomentum&&midMomentum&&execSlope&&execEvent&&extension<=.18&&spread<=12&&turnover>=35_000_000&&move<=35;
    contextLabel=contextStrong?'H4_D1_ALIGNED':contextAligned?'H4_D1_ALIGNED_SOFT':'H4_D1_CONFLICT';
  }else{
    const noOpposition=b.trend!==-dir&&c.trend!==-dir,oneAligned=b.trend===dir||c.trend===dir;
    contextAligned=noOpposition&&oneAligned;contextStrong=contextAligned&&b.trend===dir&&(c.trend===dir||c.trend===0);
    hardConflict=b.trend===-dir||c.trend===-dir;
    marketEntryReady=contextAligned&&execMomentum&&midMomentum&&execSlope&&execEvent&&extension<=.22&&spread<=7&&turnover>=50_000_000&&move<=25;
    contextLabel=contextStrong?'M15_H1_ALIGNED':contextAligned?'M15_H1_SUPPORTIVE':'M15_H1_CONFLICT';
  }
  const liquidityOk=style==='SCALP'?(turnover>=20_000_000&&spread<=10):(turnover>=15_000_000&&spread<=18),fundingOk=fund==null||!Number.isFinite(fund)||fund<.02,oiOk=oi==null||!Number.isFinite(oi)||oi<=0||oi>=250_000;
  if(!liquidityOk||!fundingOk||!oiOk)hardConflict=true;
  const state=marketEntryReady?'CONFIRMED':hardConflict?'CONFLICT':'PENDING_PREFERRED';
  const reasons=[`context ${contextLabel}`,`execution ${execEvent?'STRUCTURE_EVENT':'NO_FRESH_STRUCTURE_EVENT'}`,`momentum ${execMomentum&&midMomentum?'CLEAN':'MIXED'}`,`extension ${extension.toFixed(2)} ATR`,`spread ${spread.toFixed(2)} bps`,`turnover ${Math.round(turnover)}`];
  return {version:'V322_STYLE_READ',state,contextLabel,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:execMomentum&&midMomentum,extensionAtr:Number(extension.toFixed(3)),liquidityOk,fundingOk,openInterestOk:oiOk,marketEntryReady,hardConflict,reasons};
}
'''
w=w.replace(needle,helper+needle,1)

# Replace candidate analyzer with two-secondary-venue consensus + V3.22 evidence enrichment.
start=w.index('async function analyzeCryptoCandidate(t,style){')
end=w.index('function v31Prefix',start)
new_analyze=r'''async function analyzeCryptoCandidate(t,style){
  try{
    const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;
    const setup=buildCryptoSetup(t,style,stats);if(!setup)return null;
    const read=v322MarketRead(t,style,stats,setup),dir=String(setup.side||'').toUpperCase()==='LONG'?1:-1,contextInterval=intervalMap[style][1],primary=String(t.exchange||'').toUpperCase();
    setup.marketReadV322=read;setup.executionRead=read.state;setup.qualityEvidence={...(setup.qualityEvidence||{}),v322ContextAligned:read.contextAligned,v322ExecutionEvent:read.executionEvent,v322ExecutionMomentum:read.executionMomentum,v322LiquidityOk:read.liquidityOk,v322MarketEntryReady:read.marketEntryReady};
    setup.technicalAtIssue={...(setup.technicalAtIssue||{}),v322Context:read.contextLabel,v322Read:read.state};setup.rationale=[...(setup.rationale||[]),...read.reasons.map(x=>'V3.22 '+x)];
    const probes=[['BYBIT',bybitCandles],['OKX',okxCandles],['BINANCE',binanceCandles]].filter(x=>x[0]!==primary);let checked=0,confirmed=0,opposed=0,details=[];
    for(const [provider,fn] of probes){
      try{const sec=tfStats(await fn(t.symbol,contextInterval));if(!sec)continue;checked++;const opposing=sec.trend===-dir||sec.momentum===-dir,supporting=sec.trend===dir||sec.momentum===dir;if(opposing)opposed++;else if(supporting)confirmed++;details.push({provider,trend:sec.trend,momentum:sec.momentum,confirmed:!opposing&&supporting});}catch{}
    }
    const crossState=opposed>0?'OPPOSED':confirmed>0?'CONFIRMED':checked>0?'NEUTRAL':'UNAVAILABLE';
    setup.crossProviderConfirmation=crossState==='CONFIRMED';setup.crossProviderConsensus={state:crossState,checked,confirmed,opposed,details};setup.qualityEvidence.secondaryProviderConfirmed=crossState==='CONFIRMED';setup.technicalAtIssue.crossProviderConsensus=crossState;setup.rationale.push(`secondary venue consensus ${crossState} (${confirmed} confirm / ${opposed} oppose / ${checked} checked)`);
    if(opposed>0&&String(setup.orderType||'').toUpperCase()==='MARKET')return null;
    if(read.hardConflict&&String(setup.orderType||'').toUpperCase()==='MARKET')return null;
    return setup;
  }catch{return null;}
}

'''
w=w[:start]+new_analyze+w[end:]

# Prioritize confirmed structure/venue agreement before spread and turnover, without a numeric admission score.
sp=w.index('function setupPriority(s){')
cp=w.index('function compareSetupPriority',sp)
priority=r'''function setupPriority(s){
  const r=String(s.marketRegime||''),family=r.includes('LIQUIDITY')?0:r.includes('RECLAIM')?1:r.includes('BREAKOUT')?2:r.includes('CONTINUATION')?3:4,read=String(s.executionRead||s.marketReadV322?.state||''),readRank=read==='CONFIRMED'?0:read==='PENDING_PREFERRED'?1:2,cross=String(s.crossProviderConsensus?.state||''),crossRank=cross==='CONFIRMED'?0:cross==='NEUTRAL'?1:cross==='UNAVAILABLE'?2:3,spread=Number(s?.technicalAtIssue?.spreadBps||999),ext=Math.abs(Number(s?.technicalAtIssue?.extensionAtr||0)),turnover=Number(s?.technicalAtIssue?.turnover24h||0);
  return [readRank,crossRank,family,spread,ext,-turnover];
}
'''
w=w[:sp]+priority+w[cp:]

# Replace ideal Watch reference with style-specific directional context and explicit market-read metadata.
bi=w.index('function buildWatchIdealReference(t,style,stats){')
fi=w.index('async function findWatchTickerMulti',bi)
ideal=r'''function buildWatchIdealReference(t,style,stats){
  const [a,b,c]=stats,px=Number(t?.lastPrice||0);if(!(px>0&&a?.atr>0&&b?.atr>0&&c?.atr>0))return null;
  const profile=STYLE_EXECUTION_POLICY[style]||STYLE_EXECUTION_POLICY.SCALP,atr=Number(a.atr),spread=Math.max(0,Number(t.spreadBps||0)),spreadPx=px*spread/10000;
  let dir=0,contextState='MIXED',aligned=false;
  if(style==='SWING'){
    if(b.trend!==0&&b.trend===c.trend){dir=b.trend;aligned=true;contextState='H4_D1_ALIGNED';}
    else{const vote=3*Number(c.trend||0)+2*Number(b.trend||0)+Number(c.momentum||0)+Number(b.momentum||0);dir=vote>0?1:vote<0?-1:(px>=Number(b.ema50||px)?1:-1);contextState='H4_D1_MIXED_CONFIRMATION_REQUIRED';}
  }else{
    const vote=2*Number(c.trend||0)+2*Number(b.trend||0)+Number(a.trend||0)+Number(b.momentum||0)+Number(a.momentum||0);dir=vote>0?1:vote<0?-1:(px>=Number(b.ema50||px)?1:-1);aligned=(b.trend===dir&&c.trend!==-dir)||(c.trend===dir&&b.trend!==-dir);contextState=aligned?'M15_H1_SUPPORTIVE':'M15_H1_MIXED_CONFIRMATION_REQUIRED';
  }
  const entryBuffer=Math.max(atr*(style==='SCALP'?.07:.12),spreadPx*3.2),structurePullback=dir>0?Math.max(Number(a.ema20||px),Number(a.recentLow||a.low)+.30*atr):Math.min(Number(a.ema20||px),Number(a.recentHigh||a.high)-.30*atr),pb=dir>0?Math.min(px-entryBuffer,structurePullback):Math.max(px+entryBuffer,structurePullback),pbDistance=Math.abs(px-pb);
  const execEvent=dir>0?(a.sweepLow||a.emaReclaimUp||a.bullDisplacement):(a.sweepHigh||a.emaReclaimDown||a.bearDisplacement),preferLimit=aligned&&pbDistance<=atr*(style==='SCALP'?1.35:1.85)&&Math.abs(Number(a.extensionAtr||0))<=1.25;
  const orderType=preferLimit?'LIMIT':'STOP',entry=preferLimit?pb:(dir>0?Math.max(px+entryBuffer,Number(a.recentHigh||a.high)+entryBuffer):Math.min(px-entryBuffer,Number(a.recentLow||a.low)-entryBuffer)),entryModel=preferLimit?'WATCH_IDEAL_STRUCTURE_PULLBACK_LIMIT':'WATCH_IDEAL_CONFIRMATION_STOP';
  const stopBuffer=Math.max(atr*(style==='SCALP'?.28:.44),spreadPx*(style==='SCALP'?3.6:4.4)),anchor=dir>0?Math.min(Number(a.recentLow||a.low),Number(a.low),Number(a.ema50||a.low)-.08*atr):Math.max(Number(a.recentHigh||a.high),Number(a.high),Number(a.ema50||a.high)+.08*atr);
  let sl=dir>0?anchor-stopBuffer:anchor+stopBuffer,risk=Math.abs(entry-sl),minRisk=atr*(style==='SCALP'?.82:1.18);if(risk<minRisk){risk=minRisk;sl=entry-dir*risk;}if(!(risk>0))return null;
  const hi=(vals,f)=>Math.max(...vals.filter(Number.isFinite),f),lo=(vals,f)=>Math.min(...vals.filter(Number.isFinite),f);let tp1,tp2,tp3;
  if(dir>0){tp1=hi([a.priorHigh,a.recentHigh],entry+risk*1.0);tp2=hi([b.priorHigh,b.recentHigh],Math.max(tp1+risk*.30,entry+risk*1.65));tp3=hi([c.priorHigh,c.recentHigh],Math.max(tp2+risk*.35,entry+risk*(style==='SCALP'?2.25:2.90)));}
  else{tp1=lo([a.priorLow,a.recentLow],entry-risk*1.0);tp2=lo([b.priorLow,b.recentLow],Math.min(tp1-risk*.30,entry-risk*1.65));tp3=lo([c.priorLow,c.recentLow],Math.min(tp2-risk*.35,entry-risk*(style==='SCALP'?2.25:2.90)));}
  const distance=Math.abs(entry-px),distancePct=distance/px*100,rr=Math.abs(tp3-entry)/risk,regime=style==='SCALP'?'WATCH_V322_MICROSTRUCTURE':'WATCH_V322_HTF_STRUCTURE',story=style==='SCALP'?'SCALP: 5m execution, 15m structure, 1h direction; ưu tiên sweep/reclaim, displacement và vị trí không đuổi giá.':'SWING: H4/D1 định hướng, H1 thực thi; ưu tiên pullback/reclaim hoặc STOP xác nhận khi bối cảnh còn trộn.';
  return stampMarketJudgment({market:'CRYPTO',style,symbol:t.symbol,side:dir>0?'LONG':'SHORT',orderType,status:'REFERENCE',lifecycle:'REFERENCE_ONLY',entryState:'REFERENCE_ONLY',entry:Number(entry.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),targetRR:Number(rr.toFixed(2)),sourcePrice:px,lastPrice:px,source:t.source,exchange:t.exchange,provider:t.exchange,executionPriceAuthority:t.exchange,riskCluster:cryptoRiskCluster(t.symbol),marketRegime:regime,marketStory:story,judgment:`${regime} • ${orderType} • ${dir>0?'BULLISH':'BEARISH'} • STUDY ONLY`,entryModel,slModel:'WATCH_STRUCTURE_INVALIDATION_PLUS_ATR_SPREAD_BUFFER_V322',tpModel:'WATCH_STRUCTURE_LIQUIDITY_LADDER_THEN_EXPANSION_V322',invalidationLevel:Number(anchor.toPrecision(10)),styleExecutionModel:profile.name,executionFrames:profile.frames,executionCaution:'REFERENCE_ONLY',watchReference:true,studyOnly:true,occupiesActiveSlot:false,performanceEligible:false,referenceReason:'V322_STYLE_SPECIFIC_IDEAL_PLAN_NOT_ACTIVE_SIGNAL',distanceToEntryAbs:Number(distance.toPrecision(8)),distanceToEntryPct:Number(distancePct.toFixed(4)),watchMarketRead:{contextState,contextAligned:aligned,executionEvent:execEvent,extensionAtr:Number(Math.abs(Number(a.extensionAtr||0)).toFixed(3)),spreadBps:spread,turnover24h:Number(t.turnover24h||0),planType:preferLimit?'PULLBACK_LIMIT':'CONFIRMATION_STOP'},technicalAtIssue:{primary:intervalMap[style][0],rsi:Number(a.rsi.toFixed(1)),atr:Number(a.atr.toPrecision(8)),ema20:Number(a.ema20.toPrecision(10)),ema50:Number(a.ema50.toPrecision(10)),tfTrend:[a.trend,b.trend,c.trend],tfMomentum:[a.momentum,b.momentum,c.momentum],spreadBps:spread,turnover24h:Number(t.turnover24h||0),recentHigh:a.recentHigh,recentLow:a.recentLow},rationale:[story,`context ${contextState}`,`execution event ${execEvent?'present':'wait confirmation'}`,`entry ${entryModel}`,'SL ngoài invalidation structure + ATR/spread buffer','TP1/TP2/TP3 theo liquidity/structure rồi mới expansion','Watchlist reference only — không chiếm active slot, không tính performance']},'CRYPTO',style);
}
async function analyzeWatchIdealReference(t,style){
  try{const rows=await Promise.all(intervalMap[style].map(i=>providerCandles(t.symbol,i,t.exchange))),stats=rows.map(tfStats);if(stats.some(x=>!x))return null;return buildWatchIdealReference(t,style,stats);}catch{return null;}
}
'''
w=w[:bi]+ideal+w[fi:]

# Production status wording.
w=w.replace("service:'SignalHub Crypto Fixed 2x2 + Watchlist gateway'","service:'SignalHub Crypto 10 SCALP + 5 SWING + Universe Watch gateway'",1)
w=w.replace("crossProviderContextCheck:true","crossProviderContextCheck:true,marketReadVersion:'V322_STYLE_SPECIFIC_CONTEXT_STRUCTURE_LIQUIDITY',watchMode:'STABLE100_TAP_FOR_IDEAL_PLAN'",1)

# Android fields for 100-coin universe list and tap-to-analyze detail.
field='private final Map<String,JSONObject> watchCache=new ConcurrentHashMap<>();'
if field not in a: raise SystemExit('watchCache field missing')
a=a.replace(field,field+'\n    private final Map<String,TextView> watchUniversePriceViews=new ConcurrentHashMap<>();\n    private volatile JSONArray watchUniverseRows=new JSONArray();\n    private volatile boolean watchUniverseLoading=false;\n    private volatile long watchUniverseAt=0;\n    private String watchDetailSymbol=null;',1)

# Back from Watch detail returns to full universe.
a=a.replace('@Override public void onBackPressed(){if(detail){detail=false;selectedSignal=null;renderSignals(false);}else super.onBackPressed();}', '@Override public void onBackPressed(){if(screen.equals("WATCH")&&watchDetailSymbol!=null){watchDetailSymbol=null;renderWatchlist(false);return;}if(detail){detail=false;selectedSignal=null;renderSignals(false);}else super.onBackPressed();}',1)

# Replace old personal-search Watchlist implementation with full Stable100 universe browser.
wb=a.index('private boolean watchSearchHasFocus()')
we=a.index('private void loadAllPerformance()',wb)
watch_block=r'''private boolean watchSearchHasFocus(){return false;}
    private void refreshWatchUniverse(boolean force){
        long now=System.currentTimeMillis();if(watchUniverseLoading||(!force&&watchUniverseRows.length()>0&&now-watchUniverseAt<60000))return;watchUniverseLoading=true;
        io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.get("/v3/crypto/stable100?v322="+System.currentTimeMillis()));JSONArray rows=p.optJSONArray("rows");if(rows!=null&&rows.length()>0){watchUniverseRows=rows;watchUniverseAt=System.currentTimeMillis();lastApiOkMs=watchUniverseAt;}}catch(Throwable ignored){}finally{watchUniverseLoading=false;main.post(()->{if(screen.equals("WATCH")&&watchDetailSymbol==null)renderWatchlist(false);});}});
    }
    private JSONObject watchUniverseRow(String symbol){for(int i=0;i<watchUniverseRows.length();i++){JSONObject x=watchUniverseRows.optJSONObject(i);if(x!=null&&symbol.equalsIgnoreCase(x.optString("symbol","")))return x;}return null;}
    private void refreshWatchlistAnalyses(boolean force){refreshWatchUniverse(force);if(watchDetailSymbol!=null)refreshWatchSymbol(watchDetailSymbol,force);}
    private void refreshWatchSymbol(String symbol,boolean force){if(Boolean.TRUE.equals(watchLoading.putIfAbsent(symbol,true)))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.get("/v3/watch/analyze?symbol="+symbol+"&v322="+System.currentTimeMillis()));watchCache.put(symbol,p);lastApiOkMs=System.currentTimeMillis();}catch(Throwable e){try{JSONObject err=new JSONObject();err.put("ok",false);err.put("symbol",symbol);err.put("error",String.valueOf(e.getMessage()));watchCache.put(symbol,err);}catch(Throwable ignored){}}finally{watchLoading.remove(symbol);main.post(()->{if(screen.equals("WATCH")&&symbol.equals(watchDetailSymbol))renderWatchlist(false);});}});}
    private int watchStateColor(String state){String x=state==null?"":state.toUpperCase(Locale.US);if(x.equals("ACTIVE_SIGNAL"))return GREEN;if(x.equals("TRADEABLE_NOW"))return CYAN;if(x.equals("CONDITIONAL_WAIT")||x.equals("IDEAL_REFERENCE")||x.equals("DATA_UNAVAILABLE"))return YELLOW;return RED;}
    private String watchStateVi(String state){String x=state==null?"":state.toUpperCase(Locale.US);return switch(x){case "ACTIVE_SIGNAL"->"CÓ LỆNH ACTIVE";case "TRADEABLE_NOW"->"SETUP ĐANG ĐẸP";case "CONDITIONAL_WAIT"->"CHỜ ĐIỀU KIỆN";case "IDEAL_REFERENCE"->"LỆNH LÝ TƯỞNG";case "DATA_UNAVAILABLE"->"DỮ LIỆU TẠM THIẾU";case "NO_TRADE"->"NO TRADE";default->"ĐANG PHÂN TÍCH";};}
    private View watchStyleBlock(String styleName,JSONObject x){
        LinearLayout c=card();String state=x==null?"LOADING":x.optString("state","NO_TRADE"),side=sideVi(x==null?"":x.optString("side","")),order=x==null?"":x.optString("orderType","");LinearLayout h=row();LinearLayout title=column();title.addView(tv(styleName,15,TEXT,true));title.addView(tv(styleName.startsWith("SCALP")?"5m execution • 15m structure • 1h direction":"1h execution • 4h structure • 1D direction",8,MUTED,false));h.addView(title,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(watchStateVi(state),watchStateColor(state)));c.addView(h);
        if(x==null){c.addView(tv("Đang đọc nến và cấu trúc đa khung…",9,MUTED,false));return c;}
        String regime=x.optString("marketRegime",""),story=x.optString("marketStory","");if(!side.isEmpty()&&!order.isEmpty()){TextView d=tv(side+" • "+order+(regime.isEmpty()?"":" • "+regime),11,side.equals("BUY")?GREEN:RED,true);d.setPadding(0,dp(8),0,0);c.addView(d);}
        double e=x.optDouble("entry",0),sl=x.optDouble("sl",0),t1=x.optDouble("tp1",0),t2=x.optDouble("tp2",0),t3=x.optDouble("tp3",0);if(e>0&&sl>0&&t3>0){LinearLayout levels=row();View ve=levelBox("ENTRY",fmt(e),CYAN),vs=levelBox("SL",fmt(sl),RED),vt=levelBox("TP3",fmt(t3),GREEN);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1f);lp.setMargins(dp(2),dp(8),dp(2),0);levels.addView(ve,lp);levels.addView(vs,lp);levels.addView(vt,lp);c.addView(levels);c.addView(tv("TP1 "+fmt(t1)+"  •  TP2 "+fmt(t2)+"  •  RR "+String.format(Locale.US,"%.2fR",x.optDouble("targetRR",0)),9,TEXT,true));}
        JSONObject read=x.optJSONObject("watchMarketRead");if(read!=null){String ctx=read.optString("contextState","—"),plan=read.optString("planType","—");c.addView(tv("READ  "+ctx+"  •  "+plan+"  •  spread "+String.format(Locale.US,"%.1f",read.optDouble("spreadBps",0))+" bps",8,YELLOW,true));}
        if(!story.isEmpty())c.addView(tv(story,9,MUTED,false));JSONArray rat=x.optJSONArray("rationale");if(rat!=null&&rat.length()>0)c.addView(tv("• "+rat.optString(0),8,MUTED,false));return c;
    }
    private void openWatchCoin(String symbol){watchDetailSymbol=symbol;renderWatchlist(true);refreshWatchSymbol(symbol,true);}
    private View watchUniverseCard(JSONObject r){
        String sym=r.optString("symbol","—"),tier=r.optString("qualityTier","—");JSONObject live=cryptoPrices.get(sym);double px=live!=null?live.optDouble("lastPrice",r.optDouble("lastPrice",0)):r.optDouble("lastPrice",0),move=live!=null?live.optDouble("change24hPct",r.optDouble("change24hPct",0)):r.optDouble("change24hPct",0),spread=live!=null?live.optDouble("spreadBps",r.optDouble("spreadBps",0)):r.optDouble("spreadBps",0),turn=r.optDouble("turnover24hQuote",r.optDouble("turnover24h",0));
        LinearLayout c=card();c.setPadding(dp(13),dp(11),dp(13),dp(11));LinearLayout h=row();TextView rank=chip("#"+r.optInt("rank",0),MUTED);h.addView(rank);LinearLayout n=column();n.setPadding(dp(9),0,0,0);n.addView(tv(sym.replace("USDT"," / USDT"),14,TEXT,true));n.addView(tv("Tier "+tier+" • "+r.optString("venue","—")+" • Vol $"+compactMoney(turn),8,MUTED,false));h.addView(n,new LinearLayout.LayoutParams(0,-2,1f));LinearLayout q=column();q.setGravity(Gravity.END);TextView pv=tv(fmt(px),13,CYAN,true);pv.setGravity(Gravity.END);q.addView(pv);watchUniversePriceViews.put(sym,pv);TextView mv=tv(String.format(Locale.US,"%+.2f%% • %.1fbps",move,spread),8,move>=0?GREEN:RED,true);mv.setGravity(Gravity.END);q.addView(mv);h.addView(q);c.addView(h);TextView tap=tv("Chạm để xem SCALP + SWING và Entry / SL / TP lý tưởng",8,YELLOW,false);tap.setPadding(0,dp(6),0,0);c.addView(tap);c.setClickable(true);c.setOnClickListener(v->openWatchCoin(sym));pressFeedback(c);return c;
    }
    private String compactMoney(double v){if(v>=1_000_000_000)return String.format(Locale.US,"%.1fB",v/1_000_000_000.0);if(v>=1_000_000)return String.format(Locale.US,"%.1fM",v/1_000_000.0);if(v>=1_000)return String.format(Locale.US,"%.0fK",v/1_000.0);return String.format(Locale.US,"%.0f",v);}
    private void updateWatchUniversePrices(){for(Map.Entry<String,TextView> e:watchUniversePriceViews.entrySet()){JSONObject q=cryptoPrices.get(e.getKey());if(q!=null){double px=q.optDouble("lastPrice",0);if(px>0)e.getValue().setText(fmt(px));}}}
    private void renderWatchDetail(boolean animate){Runnable body=()->{
        content.removeAllViews();watchUniversePriceViews.clear();String sym=watchDetailSymbol;if(sym==null){renderWatchlist(false);return;}subtitle.setText("WATCH • "+sym+" • LỆNH LÝ TƯỞNG");Button back=button("‹  Tất cả 100 coin",false,v->{watchDetailSymbol=null;renderWatchlist(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(44)));JSONObject u=watchUniverseRow(sym),live=cryptoPrices.get(sym),root=watchCache.get(sym),ticker=root==null?null:root.optJSONObject("ticker");double px=live!=null?live.optDouble("lastPrice",0):(ticker!=null?ticker.optDouble("lastPrice",0):(u==null?0:u.optDouble("lastPrice",0)));LinearLayout hero=card();hero.addView(tv(sym.replace("USDT"," / USDT"),22,TEXT,true));hero.addView(tv(fmt(px),25,CYAN,true));hero.addView(tv("Lệnh dưới đây là kế hoạch tham khảo; Watch không chiếm 10 SCALP + 5 SWING active.",9,MUTED,false));content.addView(hero);
        JSONObject styles=root==null?null:root.optJSONObject("styles");content.addView(watchStyleBlock("SCALP",styles==null?null:styles.optJSONObject("SCALP")));content.addView(watchStyleBlock("SWING",styles==null?null:styles.optJSONObject("SWING")));Button refresh=button(Boolean.TRUE.equals(watchLoading.get(sym))?"Đang phân tích…":"Làm mới phân tích",true,v->refreshWatchSymbol(sym,true));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(-1,dp(46));rp.setMargins(0,dp(5),0,0);content.addView(refresh,rp);
    };if(animate)swap(body);else body.run();}
    private void renderWatchlist(boolean animate){
        if(watchDetailSymbol!=null){renderWatchDetail(animate);return;}Runnable body=()->{content.removeAllViews();watchUniversePriceViews.clear();subtitle.setText("WATCH • 100 COIN • CHẠM ĐỂ PHÂN TÍCH");content.addView(tv("100 coin có thể theo dõi",20,TEXT,true));content.addView(tv("Không cần tìm kiếm. Danh sách Stable100 tự làm mới; chạm coin để xem lệnh SCALP + SWING lý tưởng.",9,MUTED,false));
            LinearLayout summary=card();summary.addView(line("UNIVERSE",watchUniverseRows.length()+" / 100",watchUniverseRows.length()==100?GREEN:YELLOW));summary.addView(line("DỮ LIỆU",cryptoProvider+" • "+cryptoState,stateColor(cryptoState)));summary.addView(line("CẬP NHẬT",watchUniverseLoading?"Đang làm mới":"Tự động mỗi 60 giây",CYAN));content.addView(summary);
            if(watchUniverseRows.length()==0){LinearLayout z=card();z.addView(tv("Đang tải Stable100 từ server…",11,MUTED,true));content.addView(z);refreshWatchUniverse(true);return;}
            content.addView(sectionHeader("STABLE100","Xếp hạng theo quality tier → turnover → OI → spread → biến động",CYAN));for(int i=0;i<watchUniverseRows.length();i++){JSONObject r=watchUniverseRows.optJSONObject(i);if(r!=null)content.addView(watchUniverseCard(r));}
        };if(animate)swap(body);else body.run();refreshWatchUniverse(false);updateWatchUniversePrices();
    }

    '''
a=a[:wb]+watch_block+a[we:]

# WATCH page should not rebuild all 100 cards on every 500ms quote refresh; update only price labels.
old='if(screen.equals("WATCH")&&!watchSearchHasFocus()&&System.currentTimeMillis()-watchLastRenderMs>2000){watchLastRenderMs=System.currentTimeMillis();renderWatchlist(false);}'
a=a.replace(old,'if(screen.equals("WATCH")){updateWatchUniversePrices();}',1)

# Product wording from previous fixed 2x2 UI to current 10+5 book.
a=a.replace('CRYPTO • 2 SCALP + 2 SWING','CRYPTO • 10 SCALP + 5 SWING')
a=a.replace('Bảng tham khảo luôn ưu tiên 2 SCALP + 2 SWING. Watchlist phân tích riêng coin bạn chọn.','Bảng chính duy trì 10 SCALP + 5 SWING. Watch hiển thị Stable100 và mở phân tích lý tưởng khi chạm coin.')
a=a.replace('mục tiêu 2 active','mục tiêu 10 active',1)
a=a.replace('mục tiêu 2 active','mục tiêu 5 active',1)
a=a.replace('4 tín hiệu tham khảo','15 tín hiệu tham khảo')
a=a.replace('Danh mục","2 SCALP + 2 SWING','Danh mục","10 SCALP + 5 SWING')

W.write_text(w);A.write_text(a);G.write_text(g)
print('patched SignalHub V3.22 universe Watch + refined market read')
