from pathlib import Path

ROOT=Path('.')
W=ROOT/'signalhub-worker/gateway-v3.js'
A=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java'
G=ROOT/'signalhub-android/app/build.gradle'
API=ROOT/'signalhub-android/app/src/main/java/com/hanlinh/signalhub/ApiClient.java'
ICON=ROOT/'signalhub-android/app/src/main/res/drawable/ic_watchlist.xml'

w=W.read_text()
a=A.read_text()
g=G.read_text()
api=API.read_text()

def rep(text,old,new,label,count=1):
    if old not in text:
        raise SystemExit(f'{label}: marker missing')
    return text.replace(old,new,count)

# ---------------- Worker V3.16 ----------------
w=rep(w,"const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.15.2';","const V3_VERSION = 'SIGNALHUB-V3-GATEWAY-3.16.0';",'worker version')
w=rep(w,"  versionCode: 20,\n  versionName: '3.14.0',\n  title: 'SignalHub 3.14.0 Crypto Stability',","  versionCode: 21,\n  versionName: '3.16.0',\n  title: 'SignalHub 3.16.0 Fixed 2x2 + Watchlist',",'release metadata')
w=rep(w,"  artifactName: 'SignalHub-Android-v3.14.0-Simple-Stable-Crypto',","  artifactName: 'SignalHub-Android-v3.16.0-Fixed-2x2-Watchlist',",'artifact name')
w=rep(w,"  notes: [\n", "  notes: [\n    'V3.16 adds a read-only Watchlist analyzer for user-selected crypto symbols; Watchlist analysis never consumes the fixed 2 SCALP + 2 SWING active book.',\n    'Watchlist reports active signal / strict tradeable setup / conditional wait / no-trade separately for SCALP and SWING, with current provider price and Entry/SL/TP when available.',\n", 'release notes')

watch_code=r'''
function normalizeWatchSymbol(raw){
  let s=canonical(raw);if(!s)return'';if(!s.endsWith('USDT'))s+='USDT';return s.length<=24?s:'';
}
function watchFlatSignal(src,state,assessment){
  const s=src||{},a=assessment||s.entryAssessment||{};
  return {
    state,
    activeSignal:state==='ACTIVE_SIGNAL',
    symbol:s.symbol||null,side:s.side||null,orderType:s.orderType||null,status:s.status||null,
    entry:num(s.actualEntry??s.entry),sl:num(s.sl),tp1:num(s.tp1),tp2:num(s.tp2),tp3:num(s.tp3??s.tp),targetRR:num(s.targetRR),
    marketRegime:s.marketRegime||null,marketStory:s.marketStory||null,judgment:s.judgment||null,entryModel:s.entryModel||null,
    coverageTier:s.coverageTier||null,coverageFallback:Boolean(s.coverageFallback),
    assessmentMethod:a.method||null,failedChecks:Array.isArray(a.failed)?a.failed:[],
    rationale:Array.isArray(s.rationale)?s.rationale.slice(0,6):[],
    provider:s.executionPriceAuthority||s.provider||s.exchange||null,
    issuedAt:s.issuedAt||null,lastCheckedAt:s.lastCheckedAt||null
  };
}
async function watchAnalyze(url,env){
  const symbol=normalizeWatchSymbol(url.searchParams.get('symbol')||'');
  if(!symbol)return json({ok:false,version:V3_VERSION,error:'BAD_WATCH_SYMBOL'},400);
  const snap=await loadCryptoSnapshot(env);
  if(snap.live===false)return json({ok:false,version:V3_VERSION,symbol,error:'NO_FRESH_CRYPTO_SNAPSHOT',provider:snap.provider||null},503);
  const ticker=(snap.rows||[]).find(x=>canonical(x.symbol)===symbol);
  if(!ticker)return json({ok:false,version:V3_VERSION,symbol,error:'SYMBOL_NOT_FOUND_IN_LIVE_UNIVERSE',provider:snap.provider||null},404);
  const activeBook=await getActiveBook(env),styles={};
  await Promise.all(['SCALP','SWING'].map(async style=>{
    const active=activeBook.find(x=>String(x.style||'').toUpperCase()===style&&canonical(x.symbol)===symbol);
    if(active){styles[style]=watchFlatSignal(active,'ACTIVE_SIGNAL',active.entryAssessment);return;}
    const setup=await analyzeCryptoCandidate(ticker,style);
    if(!setup){styles[style]={state:'NO_TRADE',activeSignal:false,symbol,side:null,orderType:null,status:null,entry:null,sl:null,tp1:null,tp2:null,tp3:null,targetRR:null,marketRegime:'NO_TRADE',marketStory:'Chưa có cấu trúc đủ rõ cho style này ở thời điểm phân tích.',judgment:'NO_TRADE',entryModel:null,coverageTier:null,coverageFallback:false,assessmentMethod:null,failedChecks:['NO_COHERENT_SETUP'],rationale:[],provider:ticker.exchange||snap.provider||null};return;}
    const strict=assessEntrySetup(setup),conditional=setup.coverageFallback?assessCoverageSetup(setup):strict;
    const state=strict.verdict==='PASS'?'TRADEABLE_NOW':conditional.verdict==='PASS'?'CONDITIONAL_WAIT':'NO_TRADE';
    styles[style]=watchFlatSignal(setup,state,state==='TRADEABLE_NOW'?strict:conditional);
  }));
  return json({ok:true,version:V3_VERSION,mode:'CRYPTO_ONLY_STABILITY',analysisOnly:true,portfolioImpact:'NONE_READ_ONLY',symbol,ticker:{lastPrice:num(ticker.lastPrice),bid:num(ticker.bid),ask:num(ticker.ask),spreadBps:num(ticker.spreadBps),turnover24h:num(ticker.turnover24h),provider:ticker.exchange||snap.provider||null,source:ticker.source||null},styles,activeBook:{targetScalp:2,targetSwing:2,note:'Watchlist does not consume or replace active slots.'},analyzedAt:nowIso()});
}

'''
anchor="async function unifiedSignals(url,env,ctx){"
if anchor not in w: raise SystemExit('watch endpoint anchor missing')
w=w.replace(anchor,watch_code+anchor,1)
w=rep(w,"    if(url.pathname==='/v3/crypto/discovery'&&req.method==='GET')return cryptoDiscovery(url,env);","    if(url.pathname==='/v3/crypto/discovery'&&req.method==='GET')return cryptoDiscovery(url,env);\n    if(url.pathname==='/v3/watch/analyze'&&req.method==='GET')return watchAnalyze(url,env);",'watch route')
w=rep(w,"service:'SignalHub Crypto Fixed 2x2 SCALP/SWING gateway'","service:'SignalHub Crypto Fixed 2x2 + Watchlist gateway'",'status service')
W.write_text(w)

# ---------------- Android V3.16 ----------------
a=rep(a,'import android.widget.ImageView;','import android.widget.ImageView;\nimport android.widget.EditText;\nimport android.widget.Toast;','watch imports')
a=rep(a,'private static final String APP_VERSION="3.14.0";','private static final String APP_VERSION="3.16.0";','app version')
a=rep(a,'    private final Map<String,Button> filterButtons=new ConcurrentHashMap<>();','    private final Map<String,Button> filterButtons=new ConcurrentHashMap<>();\n    private final Map<String,JSONObject> watchCache=new ConcurrentHashMap<>();\n    private final Map<String,Boolean> watchLoading=new ConcurrentHashMap<>();','watch maps')
a=rep(a,'    private volatile long fxStreamLastMs=0;','    private volatile long fxStreamLastMs=0,watchLastBulkMs=0,watchLastRenderMs=0;','watch clocks')
a=rep(a,'subtitle=tv("CRYPTO • SCALP / SWING • V3.14",9,MUTED,false);','subtitle=tv("CRYPTO • 2 SCALP + 2 SWING • V3.16",9,MUTED,false);','subtitle')
a=rep(a,'String[] keys={"HOME","SIGNALS","STATS","SETTINGS"},names={"TRANG CHỦ","TÍN HIỆU","THỐNG KÊ","CÀI ĐẶT"};int[] icons={R.drawable.ic_home,R.drawable.ic_signal,R.drawable.ic_stats,R.drawable.ic_settings};','String[] keys={"HOME","SIGNALS","WATCH","STATS","SETTINGS"},names={"TRANG CHỦ","TÍN HIỆU","THEO DÕI","THỐNG KÊ","CÀI ĐẶT"};int[] icons={R.drawable.ic_home,R.drawable.ic_signal,R.drawable.ic_watchlist,R.drawable.ic_stats,R.drawable.ic_settings};','bottom watch tab')
a=rep(a,'        else if(screen.equals("STATS"))renderStats(animate);\n        else renderSettings(animate);','        else if(screen.equals("WATCH"))renderWatchlist(animate);\n        else if(screen.equals("STATS"))renderStats(animate);\n        else renderSettings(animate);','render current watch')
a=rep(a,'    private void refreshPage(boolean force){\n        if(!resumed&&!force)return;\n        if(!pageBusy.compareAndSet(false,true))return;','    private void refreshPage(boolean force){\n        if(!resumed&&!force)return;\n        if(screen.equals("WATCH")){refreshWatchlistAnalyses(force);return;}\n        if(!pageBusy.compareAndSet(false,true))return;','watch refresh branch')
a=rep(a,'            else if(scr.equals("STATS"))loadAllPerformance();','            else if(scr.equals("STATS"))loadAllPerformance();','noop stats marker')

watch_android=r'''
    private SharedPreferences watchPrefs(){return getSharedPreferences("signalhub_watch",MODE_PRIVATE);}
    private String normalizeWatch(String raw){String s=raw==null?"":raw.toUpperCase(Locale.US).replaceAll("[^A-Z0-9]","");if(s.isEmpty())return"";if(!s.endsWith("USDT"))s+="USDT";return s.length()<=24?s:"";}
    private List<String> watchSymbols(){
        String raw=watchPrefs().getString("symbols","BTCUSDT,ETHUSDT,SOLUSDT");List<String> out=new ArrayList<>();for(String x:raw.split(",")){String s=normalizeWatch(x);if(!s.isEmpty()&&!out.contains(s))out.add(s);}return out;
    }
    private void saveWatchSymbols(List<String> rows){watchPrefs().edit().putString("symbols",String.join(",",rows)).apply();}
    private void addWatch(String raw){String s=normalizeWatch(raw);if(s.isEmpty()){Toast.makeText(this,"Mã coin không hợp lệ",Toast.LENGTH_SHORT).show();return;}List<String> rows=watchSymbols();if(rows.contains(s)){refreshWatchSymbol(s,true);return;}if(rows.size()>=12){Toast.makeText(this,"Watchlist tối đa 12 coin",Toast.LENGTH_SHORT).show();return;}rows.add(s);saveWatchSymbols(rows);watchCache.remove(s);renderWatchlist(false);refreshWatchSymbol(s,true);}
    private void removeWatch(String symbol){List<String> rows=watchSymbols();rows.remove(symbol);saveWatchSymbols(rows);watchCache.remove(symbol);renderWatchlist(false);}
    private void refreshWatchlistAnalyses(boolean force){long now=System.currentTimeMillis();if(!force&&now-watchLastBulkMs<30000)return;watchLastBulkMs=now;for(String s:watchSymbols())refreshWatchSymbol(s,false);}
    private void refreshWatchSymbol(String symbol,boolean force){if(Boolean.TRUE.equals(watchLoading.putIfAbsent(symbol,true)))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.get("/v3/watch/analyze?symbol="+symbol));watchCache.put(symbol,p);lastApiOkMs=System.currentTimeMillis();}catch(Throwable e){try{JSONObject err=new JSONObject();err.put("ok",false);err.put("symbol",symbol);err.put("error",String.valueOf(e.getMessage()));watchCache.put(symbol,err);}catch(Throwable ignored){}}finally{watchLoading.remove(symbol);main.post(()->{if(screen.equals("WATCH"))renderWatchlist(false);});}});}
    private int watchStateColor(String state){String x=state==null?"":state.toUpperCase(Locale.US);if(x.equals("ACTIVE_SIGNAL"))return GREEN;if(x.equals("TRADEABLE_NOW"))return CYAN;if(x.equals("CONDITIONAL_WAIT"))return YELLOW;return RED;}
    private String watchStateVi(String state){String x=state==null?"":state.toUpperCase(Locale.US);return switch(x){case "ACTIVE_SIGNAL"->"CÓ LỆNH";case "TRADEABLE_NOW"->"SETUP ĐẸP";case "CONDITIONAL_WAIT"->"CHỜ ĐIỀU KIỆN";case "NO_TRADE"->"NO TRADE";default->"ĐANG PHÂN TÍCH";};}
    private View watchStyleBlock(String styleName,JSONObject x){LinearLayout c=column();c.setPadding(0,dp(8),0,dp(5));String state=x==null?"LOADING":x.optString("state","NO_TRADE"),side=sideVi(x==null?"":x.optString("side","")),order=x==null?"":x.optString("orderType","");LinearLayout h=row();h.addView(tv(styleName,11,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(watchStateVi(state),watchStateColor(state)));c.addView(h);if(x==null){c.addView(tv("Đang đọc cấu trúc thị trường…",9,MUTED,false));return c;}String story=x.optString("marketStory","");String regime=x.optString("marketRegime","");if(!side.isEmpty()&&!order.isEmpty())c.addView(tv(side+" • "+order+(regime.isEmpty()?"":" • "+regime),10,side.equals("BUY")?GREEN:RED,true));else if(!regime.isEmpty())c.addView(tv(regime,10,MUTED,true));if(!story.isEmpty())c.addView(tv(story,9,MUTED,false));double e=x.optDouble("entry",0),sl=x.optDouble("sl",0),tp=x.optDouble("tp3",0);if(e>0&&sl>0&&tp>0)c.addView(tv("ENTRY "+fmt(e)+"   •   SL "+fmt(sl)+"   •   TP3 "+fmt(tp)+"   •   "+String.format(Locale.US,"%.2fR",x.optDouble("targetRR",0)),9,TEXT,true));JSONArray failed=x.optJSONArray("failedChecks");if(state.equals("NO_TRADE")&&failed!=null&&failed.length()>0){StringBuilder b=new StringBuilder("Thiếu: ");for(int i=0;i<Math.min(3,failed.length());i++){if(i>0)b.append(" • ");b.append(failed.optString(i));}c.addView(tv(b.toString(),8,YELLOW,false));}return c;}
    private void renderWatchlist(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("WATCHLIST • PHÂN TÍCH RIÊNG • KHÔNG CHIẾM 2+2 SLOT");content.addView(tv("WATCHLIST",18,TEXT,true));LinearLayout note=card();note.addView(tv("2 SCALP + 2 SWING luôn là bảng tín hiệu tham khảo chính.",11,GREEN,true));note.addView(tv("Watchlist chỉ phân tích coin bạn chọn; không tạo thêm lệnh và không chiếm 4 slot active.",9,MUTED,false));content.addView(note);LinearLayout add=row();EditText input=new EditText(this);input.setHint("BTC, ETH, XRP, ZEC…");input.setHintTextColor(MUTED);input.setTextColor(TEXT);input.setTextSize(12);input.setSingleLine(true);input.setPadding(dp(12),0,dp(12),0);input.setBackground(shape(PANEL2,11,BORDER));Button addBtn=button("THÊM",false,v->{String s=input.getText().toString();input.setText("");addWatch(s);});LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(0,dp(44),1f);ip.setMargins(0,dp(6),dp(6),dp(8));add.addView(input,ip);LinearLayout.LayoutParams ab=new LinearLayout.LayoutParams(dp(82),dp(44));ab.setMargins(dp(2),dp(6),0,dp(8));add.addView(addBtn,ab);content.addView(add);List<String> symbols=watchSymbols();if(symbols.isEmpty()){LinearLayout z=card();z.addView(tv("Chưa có coin nào. Nhập mã phía trên để thêm vào Watchlist.",10,MUTED,true));content.addView(z);return;}for(String sym:symbols){JSONObject root=watchCache.get(sym),ticker=root==null?null:root.optJSONObject("ticker"),live=cryptoPrices.get(sym);double px=live!=null?live.optDouble("lastPrice",0):(ticker==null?0:ticker.optDouble("lastPrice",0));LinearLayout c=card();LinearLayout h=row();h.addView(tv(sym.replace("USDT"," / USDT"),14,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));TextView price=tv(fmt(px),13,CYAN,true);h.addView(price);Button rm=button("×",false,v->removeWatch(sym));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(dp(40),dp(34));rp.setMargins(dp(8),0,0,0);h.addView(rm,rp);c.addView(h);String provider=live!=null?cryptoProvider:(ticker==null?"—":ticker.optString("provider","—"));c.addView(tv(provider+" • "+cryptoState,8,stateColor(cryptoState),false));JSONObject styles=root==null?null:root.optJSONObject("styles");c.addView(watchStyleBlock("SCALP • 5m / 15m / 1h",styles==null?null:styles.optJSONObject("SCALP")));c.addView(watchStyleBlock("SWING • 1h / 4h / 1D",styles==null?null:styles.optJSONObject("SWING")));Button refresh=button(Boolean.TRUE.equals(watchLoading.get(sym))?"ĐANG PHÂN TÍCH…":"PHÂN TÍCH LẠI",false,v->refreshWatchSymbol(sym,true));LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(38));fp.setMargins(0,dp(5),0,0);c.addView(refresh,fp);content.addView(c);} };if(animate)swap(body);else body.run();}

'''
anchor='    private void loadAllPerformance(){'
if anchor not in a: raise SystemExit('android watch insertion anchor missing')
a=a.replace(anchor,watch_android+anchor,1)
# Re-render watchlist from live ticker stream at a modest rate (not every 500ms).
old='main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);});}});}'
new='main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);if(screen.equals("WATCH")&&System.currentTimeMillis()-watchLastRenderMs>2000){watchLastRenderMs=System.currentTimeMillis();renderWatchlist(false);}});}});}'
# only replace second occurrence corresponding to crypto refresh: use rsplit-like exact count by finding all
idxs=[];start=0
while True:
    i=a.find(old,start)
    if i<0: break
    idxs.append(i);start=i+1
if not idxs: raise SystemExit('crypto callback marker missing')
i=idxs[-1]
a=a[:i]+new+a[i+len(old):]
A.write_text(a)

g=rep(g,"versionCode 20","versionCode 21",'versionCode')
g=rep(g,"versionName '3.14.0'","versionName '3.16.0'",'versionName')
G.write_text(g)
api=rep(api,'SignalHub-Android/3.13.0-crypto-only-quality','SignalHub-Android/3.16.0-fixed-2x2-watchlist','user agent')
API.write_text(api)

ICON.write_text('''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M12,2.5l2.9,5.88 6.49,0.94 -4.69,4.57 1.11,6.46L12,17.3l-5.81,3.05 1.11,-6.46 -4.69,-4.57 6.49,-0.94z"/></vector>''')

print('patched SignalHub V3.16 fixed 2x2 + watchlist')
