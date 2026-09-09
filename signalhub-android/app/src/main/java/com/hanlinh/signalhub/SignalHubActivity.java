package com.hanlinh.signalhub;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class SignalHubActivity extends Activity {
    private static final int REQ_NOTIFICATIONS=42;
    private static final String APP_VERSION="3.1.0";
    private static final long REFRESH_MS=3000L;
    private static final long SCAN_MS=15000L;
    private static final int BG=Color.rgb(4,7,11),PANEL=Color.rgb(12,18,26),PANEL2=Color.rgb(18,26,36),BORDER=Color.rgb(38,51,65);
    private static final int TEXT=Color.rgb(235,241,247),MUTED=Color.rgb(133,151,169),GREEN=Color.rgb(76,222,153),RED=Color.rgb(255,93,112),YELLOW=Color.rgb(246,196,91),BLUE=Color.rgb(93,158,255),CYAN=Color.rgb(73,219,219);
    private static final String CI_MARKERS="/v3/scan /v3/signals /v3/performance /v3/app-version FOREX CRYPTO SCALP SWING MARKET LIMIT STOP EXNESS";

    private final ExecutorService io=Executors.newFixedThreadPool(4);
    private final Handler main=new Handler(Looper.getMainLooper());
    private final AtomicBoolean busy=new AtomicBoolean(false);
    private final Map<String,Double> fxPrices=new HashMap<>();
    private final Map<String,JSONObject> cryptoPrices=new HashMap<>();
    private LinearLayout content,bottom;
    private TextView fxLive,cryptoLive;
    private Button fxBtn,cryptoBtn,scalpBtn,swingBtn;
    private boolean resumed,detail,monitorStarted;
    private String screen="SIGNALS",market="FOREX",style="SCALP";
    private long lastScan=0,lastCrypto=0;

    private final Runnable loop=new Runnable(){@Override public void run(){if(!resumed)return;if(!detail)refresh(false);main.postDelayed(this,REFRESH_MS);}};

    @Override public void onCreate(Bundle b){super.onCreate(b);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);buildUi();ensureMonitor(true);selectScreen("SIGNALS");}
    @Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);main.removeCallbacks(loop);main.post(loop);}
    @Override protected void onPause(){resumed=false;main.removeCallbacks(loop);super.onPause();}
    @Override protected void onDestroy(){main.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}

    private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
    private GradientDrawable shape(int fill,int radius,int stroke){GradientDrawable d=new GradientDrawable();d.setColor(fill);d.setCornerRadius(dp(radius));if(stroke!=Color.TRANSPARENT)d.setStroke(dp(1),stroke);return d;}
    private TextView tv(String s,int sp,int color,boolean bold){TextView v=new TextView(this);v.setText(s);v.setTextSize(sp);v.setTextColor(color);v.setTypeface(Typeface.create(Typeface.MONOSPACE,bold?Typeface.BOLD:Typeface.NORMAL));v.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout row(){LinearLayout r=new LinearLayout(this);r.setOrientation(LinearLayout.HORIZONTAL);r.setGravity(Gravity.CENTER_VERTICAL);return r;}
    private LinearLayout card(){LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);c.setPadding(dp(14),dp(12),dp(14),dp(12));c.setBackground(shape(PANEL,14,BORDER));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(5),0,dp(5));c.setLayoutParams(p);return c;}
    private TextView chip(String s,int color){TextView v=tv(s,9,color,true);v.setPadding(dp(8),dp(5),dp(8),dp(5));v.setGravity(Gravity.CENTER);v.setBackground(shape(Color.argb(24,Color.red(color),Color.green(color),Color.blue(color)),9,color));return v;}
    private Button button(String s,boolean selected,View.OnClickListener l){Button b=new Button(this);b.setText(s);b.setAllCaps(false);b.setTextSize(10);b.setTypeface(Typeface.MONOSPACE,Typeface.BOLD);b.setTextColor(selected?BG:TEXT);b.setBackground(shape(selected?GREEN:PANEL2,11,selected?GREEN:BORDER));b.setOnClickListener(l);return b;}
    private TextView line(String k,String v,int c){TextView t=tv(k+"  "+v,11,c,true);t.setPadding(0,dp(3),0,dp(3));return t;}

    private void buildUi(){
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(BG);
        LinearLayout head=new LinearLayout(this);head.setOrientation(LinearLayout.VERTICAL);head.setPadding(dp(14),dp(14),dp(14),dp(8));
        LinearLayout top=row();LinearLayout titles=new LinearLayout(this);titles.setOrientation(LinearLayout.VERTICAL);titles.addView(tv("SIGNALHUB",24,TEXT,true));titles.addView(tv("FOREX + CRYPTO • SCALP + SWING",9,MUTED,true));top.addView(titles,new LinearLayout.LayoutParams(0,-2,1f));top.addView(chip("V"+APP_VERSION,BLUE));head.addView(top);
        LinearLayout live=row();fxLive=chip("EXNESS • CHỜ",YELLOW);cryptoLive=chip("BYBIT • CHỜ",YELLOW);LinearLayout.LayoutParams a=new LinearLayout.LayoutParams(0,-2,1f);a.setMargins(0,dp(8),dp(4),0);LinearLayout.LayoutParams b=new LinearLayout.LayoutParams(0,-2,1f);b.setMargins(dp(4),dp(8),0,0);live.addView(fxLive,a);live.addView(cryptoLive,b);head.addView(live);
        LinearLayout mr=row();fxBtn=button("FOREX",true,v->setMarket("FOREX"));cryptoBtn=button("CRYPTO",false,v->setMarket("CRYPTO"));LinearLayout.LayoutParams m1=new LinearLayout.LayoutParams(0,dp(44),1f);m1.setMargins(0,dp(8),dp(4),0);LinearLayout.LayoutParams m2=new LinearLayout.LayoutParams(0,dp(44),1f);m2.setMargins(dp(4),dp(8),0,0);mr.addView(fxBtn,m1);mr.addView(cryptoBtn,m2);head.addView(mr);
        LinearLayout sr=row();scalpBtn=button("SCALP",true,v->setStyle("SCALP"));swingBtn=button("SWING",false,v->setStyle("SWING"));LinearLayout.LayoutParams s1=new LinearLayout.LayoutParams(0,dp(40),1f);s1.setMargins(0,dp(6),dp(4),0);LinearLayout.LayoutParams s2=new LinearLayout.LayoutParams(0,dp(40),1f);s2.setMargins(dp(4),dp(6),0,0);sr.addView(scalpBtn,s1);sr.addView(swingBtn,s2);head.addView(sr);root.addView(head);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(dp(14),dp(4),dp(14),dp(12));scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1f));
        bottom=row();bottom.setPadding(dp(8),dp(7),dp(8),dp(9));bottom.setBackgroundColor(PANEL);root.addView(bottom);setContentView(root);drawBottom();
    }

    private void setMarket(String m){market=m;detail=false;paintToggles();refresh(true);}
    private void setStyle(String s){style=s;detail=false;paintToggles();refresh(true);}
    private void paintToggles(){boolean fx=market.equals("FOREX"),sc=style.equals("SCALP");setBtn(fxBtn,fx);setBtn(cryptoBtn,!fx);setBtn(scalpBtn,sc);setBtn(swingBtn,!sc);}
    private void setBtn(Button b,boolean on){b.setTextColor(on?BG:TEXT);b.setBackground(shape(on?GREEN:PANEL2,11,on?GREEN:BORDER));}
    private void selectScreen(String s){screen=s;detail=false;drawBottom();refresh(true);}
    private void drawBottom(){bottom.removeAllViews();String[] k={"SIGNALS","WATCHLIST","HISTORY","NEWS"},n={"TÍN HIỆU","THEO DÕI","LỊCH SỬ","TIN TỨC"};for(int i=0;i<k.length;i++){final String x=k[i];Button b=button(n[i],screen.equals(x),v->selectScreen(x));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(48),1f);p.setMargins(dp(3),0,dp(3),0);bottom.addView(b,p);}}
    private void loading(){content.removeAllViews();content.addView(tv(title(),15,TEXT,true));LinearLayout c=card();c.addView(tv("Đang cập nhật dữ liệu live…",11,MUTED,false));content.addView(c);}
    private String title(){if(screen.equals("SIGNALS"))return"TÍN HIỆU • "+market+" • "+style;if(screen.equals("WATCHLIST"))return"THEO DÕI • "+market;if(screen.equals("HISTORY"))return"LỊCH SỬ • "+market+" • "+style;return"TIN TỨC • "+market;}

    private void refresh(boolean force){if(!resumed&&!force)return;if(!busy.compareAndSet(false,true))return;if(force)loading();final String scr=screen,m=market,st=style;io.execute(()->{try{refreshPrices();if(scr.equals("SIGNALS"))loadSignals(m,st);else if(scr.equals("WATCHLIST"))loadWatchlist(m);else if(scr.equals("HISTORY"))loadHistory(m,st);else loadNews(m);}finally{busy.set(false);}});}
    private void refreshPrices(){
        try{JSONObject p=new JSONObject(ApiClient.get("/v3/forex/live"));JSONArray a=p.optJSONArray("quotes");synchronized(fxPrices){fxPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null)fxPrices.put(q.optString("symbol"),q.optDouble("mid",0));}}String state=p.optString("state","OFFLINE");long age=p.optLong("quoteAgeMs",999999);main.post(()->{int c=state.equals("LIVE")?GREEN:state.equals("DELAYED")?YELLOW:RED;fxLive.setText("EXNESS • "+(state.equals("LIVE")?"LIVE":state.equals("DELAYED")?"TRỄ":"MẤT LIVE")+" • "+String.format(Locale.US,"%.1fs",age/1000.0));fxLive.setTextColor(c);});}catch(Throwable e){main.post(()->{fxLive.setText("EXNESS • MẤT LIVE");fxLive.setTextColor(RED);});}
        try{long now=System.currentTimeMillis();if(now-lastCrypto>2500){JSONObject p=new JSONObject(ApiClient.get("/v3/crypto/tickers?limit=1000"));JSONArray a=p.optJSONArray("tickers");synchronized(cryptoPrices){cryptoPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null)cryptoPrices.put(q.optString("symbol"),q);}}lastCrypto=now;String provider=p.optString("provider","CRYPTO");int n=p.optInt("count",0);main.post(()->{cryptoLive.setText(provider+" • LIVE • "+n+" MÃ");cryptoLive.setTextColor(GREEN);});}}catch(Throwable e){main.post(()->{cryptoLive.setText("CRYPTO • ĐANG NỐI LẠI");cryptoLive.setTextColor(YELLOW);});}
    }

    private void loadSignals(String m,String st){
        try{long now=System.currentTimeMillis();if(now-lastScan>SCAN_MS){try{ApiClient.get("/v3/scan?market="+m+"&style="+st);}catch(Throwable ignored){}lastScan=now;}JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market="+m+"&style="+st+"&status=active&limit=100"));JSONObject perf=new JSONObject(ApiClient.get("/v3/performance?market="+m+"&style="+st)).optJSONObject("performance");JSONArray a=root.optJSONArray("signals");main.post(()->renderSignals(m,st,a,perf));}catch(Throwable e){main.post(()->error("Không tải được tín hiệu",e));}
    }
    private void renderSignals(String m,String st,JSONArray a,JSONObject p){if(!screen.equals("SIGNALS")||!market.equals(m)||!style.equals(st))return;content.removeAllViews();LinearLayout h=row();h.addView(tv(m+" • "+st,15,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(m.equals("FOREX")?"EXNESS":"CRYPTO",GREEN));content.addView(h);LinearLayout sum=card();int active=a==null?0:a.length();sum.addView(tv(active+" tín hiệu đang hoạt động",11,TEXT,true));if(p!=null){String wr=p.optString("winRateLabel","CHƯA CÓ MẪU");sum.addView(tv("WR "+wr+" • NET "+String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)),10,MUTED,true));if(!p.optBoolean("sampleAdequate",false))sum.addView(tv("WR chỉ là lịch sử TP/SL; chưa đủ 30 lệnh thì coi là mẫu sơ bộ.",9,YELLOW,false));}content.addView(sum);if(active==0){LinearLayout c=card();c.addView(tv("Chưa có điểm vào đạt điều kiện.",12,MUTED,true));c.addView(tv("Hệ thống không ép lệnh khi giá đã chạy xa hoặc cấu trúc chưa sạch.",10,MUTED,false));content.addView(c);return;}for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s!=null)content.addView(signalCard(s));}}
    private View signalCard(JSONObject s){LinearLayout c=card();String sym=s.optString("symbol","—"),side=s.optString("side","—"),order=s.optString("orderType","MARKET"),status=s.optString("status","OPEN");int dir=side.equals("LONG")?1:-1,col=dir>0?GREEN:RED;LinearLayout h=row();h.addView(tv(sym,17,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side+" • "+order,col));c.addView(h);double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp",0),px=priceFor(s,e);c.addView(line("GIÁ LIVE",fmt(px),CYAN));c.addView(line("TRẠNG THÁI",stateVi(s),status.equals("PENDING")?YELLOW:GREEN));c.addView(tv("ENTRY "+fmt(e)+"   TP "+fmt(tp)+"   SL "+fmt(sl),10,MUTED,true));c.addView(tv(progress(dir,px,e,sl,tp),10,dir*(px-e)>=0?GREEN:RED,true));c.addView(tv("Setup "+s.optInt("score",0)+"/100 • RR "+String.format(Locale.US,"%.2f",s.optDouble("targetRR",0)),9,MUTED,false));c.setOnClickListener(v->detail(s));return c;}
    private String stateVi(JSONObject s){String x=s.optString("status","OPEN");if(x.equals("PENDING"))return"CHỜ KHỚP";if(s.optBoolean("brokerConfirmed",false))return"ĐÃ KHỚP EXNESS";return x.equals("OPEN")?"ĐANG CHẠY":x;}
    private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol","");if(s.optString("market",market).equals("CRYPTO")){synchronized(cryptoPrices){JSONObject q=cryptoPrices.get(sym);return q==null?fallback:q.optDouble("lastPrice",fallback);}}synchronized(fxPrices){Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}}
    private String progress(int dir,double px,double e,double sl,double tp){if(!(px>0&&e>0&&sl>0&&tp>0))return"[SL] ─── [ENTRY] ─── [NOW] ─── [TP]";double risk=Math.abs(e-sl);if(risk<=0)return"[SL] ─── [ENTRY] ─── [NOW] ─── [TP]";double r=dir*(px-e)/risk;return r>=0?String.format(Locale.US,"[SL] ─── [ENTRY] ── ●NOW ── [TP]   %+.2fR",r):String.format(Locale.US,"[SL] ── ●NOW ── [ENTRY] ─── [TP]   %+.2fR",r);}
    private void detail(JSONObject s){detail=true;content.removeAllViews();Button back=button("← QUAY LẠI",false,v->{detail=false;refresh(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(42)));LinearLayout c=card();String sym=s.optString("symbol","—"),side=s.optString("side","—"),order=s.optString("orderType","MARKET");int dir=side.equals("LONG")?1:-1;LinearLayout h=row();h.addView(tv(sym+" • "+side,20,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(order,dir>0?GREEN:RED));c.addView(h);double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp",0),px=priceFor(s,e);c.addView(line("NOW",fmt(px),CYAN));c.addView(line("ENTRY",fmt(e),TEXT));c.addView(line("TP",fmt(tp),GREEN));c.addView(line("SL",fmt(sl),RED));c.addView(tv(progress(dir,px,e,sl,tp),11,dir*(px-e)>=0?GREEN:RED,true));c.addView(line("TRẠNG THÁI",stateVi(s),YELLOW));c.addView(line("CHẤT LƯỢNG SETUP",s.optInt("score",0)+"/100",BLUE));c.addView(tv("Điểm setup không phải xác suất thắng.",9,YELLOW,false));JSONArray why=s.optJSONArray("rationale");if(why!=null){c.addView(tv("LÝ DO",11,TEXT,true));for(int i=0;i<why.length();i++)c.addView(tv("• "+why.optString(i),10,MUTED,false));}c.addView(tv("Phát: "+time(s.optString("issuedAt","")),9,MUTED,false));content.addView(c);}

    private void loadWatchlist(String m){main.post(()->{if(!screen.equals("WATCHLIST")||!market.equals(m))return;content.removeAllViews();content.addView(tv("THEO DÕI • "+m,15,TEXT,true));String[] syms=m.equals("FOREX")?new String[]{"EURUSD","GBPUSD","USDJPY","GBPJPY","XAUUSD","XAGUSD","USOIL","UKOIL"}:new String[]{"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","LTCUSDT","LINKUSDT"};for(String sym:syms){LinearLayout c=card();c.addView(tv(sym,15,TEXT,true));if(m.equals("FOREX")){double p; synchronized(fxPrices){p=fxPrices.getOrDefault(sym,0.0);}c.addView(line("GIÁ EXNESS",fmt(p),p>0?CYAN:YELLOW));}else{synchronized(cryptoPrices){JSONObject q=cryptoPrices.get(sym);if(q!=null){double ch=q.optDouble("change24hPct",0);c.addView(line("GIÁ "+q.optString("exchange",""),fmt(q.optDouble("lastPrice",0)),CYAN));c.addView(tv(String.format(Locale.US,"24h %+.2f%% • spread %.2f bps",ch,q.optDouble("spreadBps",0)),10,ch>=0?GREEN:RED,true));}else c.addView(tv("Chưa có quote",10,YELLOW,false));}}content.addView(c);}});}
    private void loadHistory(String m,String st){try{JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market="+m+"&style="+st+"&status=closed&limit=150"));JSONObject p=new JSONObject(ApiClient.get("/v3/performance?market="+m+"&style="+st)).optJSONObject("performance");JSONArray a=root.optJSONArray("signals");main.post(()->renderHistory(m,st,a,p));}catch(Throwable e){main.post(()->error("Không tải được lịch sử",e));}}
    private void renderHistory(String m,String st,JSONArray a,JSONObject p){if(!screen.equals("HISTORY")||!market.equals(m)||!style.equals(st))return;content.removeAllViews();content.addView(tv("LỊCH SỬ • "+m+" • "+st,15,TEXT,true));LinearLayout sum=card();if(p!=null){sum.addView(tv("WR "+p.optString("winRateLabel","—")+"   TP "+p.optInt("tp",0)+"   SL "+p.optInt("sl",0)+"   NET "+String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)),11,p.optDouble("netRResolved",0)>=0?GREEN:RED,true));sum.addView(tv(p.optBoolean("sampleAdequate",false)?"Mẫu ≥30 lệnh":"Mẫu <30 lệnh • chỉ tham khảo",9,p.optBoolean("sampleAdequate",false)?MUTED:YELLOW,false));}content.addView(sum);if(a==null||a.length()==0){LinearLayout c=card();c.addView(tv("Chưa có lệnh TP/SL đã đóng.",11,MUTED,false));content.addView(c);return;}for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s==null)continue;String out=s.optString("outcome","CLOSED");int col=out.equals("TP")?GREEN:out.equals("SL")?RED:MUTED;LinearLayout c=card(),h=row();h.addView(tv(s.optString("symbol","—")+" • "+s.optString("side","—"),13,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(out,col));c.addView(h);c.addView(tv("Entry "+fmt(s.optDouble("entry",0))+" → Exit "+fmt(s.optDouble("exitPrice",0))+"   "+String.format(Locale.US,"%+.2fR",s.optDouble("resultR",0)),10,col,true));content.addView(c);}}
    private void loadNews(String m){main.post(()->{if(!screen.equals("NEWS")||!market.equals(m))return;content.removeAllViews();content.addView(tv("TIN TỨC • "+m,15,TEXT,true));LinearLayout c=card();c.addView(chip("BỐI CẢNH",BLUE));c.addView(tv("Tin tức không tự tạo BUY/SELL. Engine chỉ dùng tin, biến động, spread và cấu trúc làm bối cảnh trước khi phát tín hiệu.",11,MUTED,false));c.addView(tv(m.equals("FOREX")?"Forex: ưu tiên trạng thái Exness live, spread và rủi ro tin mạnh.":"Crypto: ưu tiên Bybit, funding/OI/thanh khoản và trạng thái BTC/ETH.",10,YELLOW,false));content.addView(c);});}
    private void error(String t,Throwable e){content.removeAllViews();content.addView(tv(t,14,RED,true));LinearLayout c=card();c.addView(tv("Đang thử nối lại. Không gắn nhãn LIVE cho dữ liệu cũ.",11,YELLOW,true));c.addView(tv(String.valueOf(e.getMessage()),9,MUTED,false));content.addView(c);}

    private boolean notifyPermission(){return Build.VERSION.SDK_INT<33||checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;}
    private void ensureMonitor(boolean ask){if(monitorStarted)return;if(!notifyPermission()){if(ask&&Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},REQ_NOTIFICATIONS);return;}try{Intent i=new Intent(this,MonitorService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);monitorStarted=true;}catch(Throwable ignored){}}
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] grantResults){super.onRequestPermissionsResult(requestCode,permissions,grantResults);if(requestCode==REQ_NOTIFICATIONS&&grantResults.length>0&&grantResults[0]==PackageManager.PERMISSION_GRANTED)ensureMonitor(false);}
    private String fmt(double v){if(!Double.isFinite(v)||v<=0)return"—";if(v>=1000)return String.format(Locale.US,"%.2f",v);if(v>=100)return String.format(Locale.US,"%.3f",v);if(v>=10)return String.format(Locale.US,"%.4f",v);if(v>=1)return String.format(Locale.US,"%.5f",v);return String.format(Locale.US,"%.7f",v);}
    private String time(String iso){try{return DateTimeFormatter.ofPattern("dd/MM HH:mm",Locale.US).withZone(ZoneId.systemDefault()).format(Instant.parse(iso));}catch(Exception e){return iso.isEmpty()?"—":iso;}}
}
