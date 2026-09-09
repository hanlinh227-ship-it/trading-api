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
import android.view.MotionEvent;
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
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class SignalHubActivity extends Activity {
    private static final int REQ_NOTIFICATIONS=42;
    private static final String APP_VERSION="3.2.0";
    private static final long LIVE_REFRESH_MS=1000L;
    private static final long PAGE_REFRESH_MS=3000L;
    private static final long SCAN_MS=30000L;
    private static final int BG=Color.rgb(3,7,11),PANEL=Color.rgb(9,16,23),PANEL2=Color.rgb(15,25,35),BORDER=Color.rgb(30,49,64);
    private static final int TEXT=Color.rgb(238,246,252),MUTED=Color.rgb(126,151,169),GREEN=Color.rgb(44,226,155),RED=Color.rgb(255,82,104),YELLOW=Color.rgb(246,194,76),BLUE=Color.rgb(68,170,255),CYAN=Color.rgb(60,220,235);

    private final ExecutorService io=Executors.newFixedThreadPool(6);
    private final Handler main=new Handler(Looper.getMainLooper());
    private final AtomicBoolean fxBusy=new AtomicBoolean(false),cryptoBusy=new AtomicBoolean(false),pageBusy=new AtomicBoolean(false),scanBusy=new AtomicBoolean(false);
    private final Map<String,Double> fxPrices=new ConcurrentHashMap<>();
    private final Map<String,JSONObject> cryptoPrices=new ConcurrentHashMap<>();
    private final Map<String,JSONArray> signalCache=new ConcurrentHashMap<>();
    private final Map<String,JSONObject> perfCache=new ConcurrentHashMap<>();
    private final Map<String,String> signalFingerprints=new ConcurrentHashMap<>();
    private final Map<String,TextView> priceViews=new ConcurrentHashMap<>();
    private final Map<String,TextView> sourceViews=new ConcurrentHashMap<>();
    private final Map<String,String> viewMarkets=new ConcurrentHashMap<>();
    private final Map<String,Long> lastScanAt=new ConcurrentHashMap<>();
    private final Map<String,Button> filterButtons=new ConcurrentHashMap<>();

    private LinearLayout content,bottom,signalControls;
    private TextView fxLive,cryptoLive,subtitle;
    private Button scalpBtn,swingBtn;
    private boolean resumed,detail,monitorStarted;
    private String screen="SIGNALS",style="SCALP",filter="ALL";
    private JSONObject selectedSignal,systemStatus;
    private volatile String fxState="OFFLINE",cryptoState="OFFLINE",cryptoProvider="CRYPTO",systemState="CONNECTING";
    private volatile long fxQuoteAgeMs=-1,fxLastOkMs=0,cryptoLastOkMs=0,lastApiOkMs=0,lastUiPageRefreshMs=0;
    private volatile int fxCount=0,cryptoCount=0;

    private final Runnable loop=new Runnable(){@Override public void run(){
        if(!resumed)return;
        refreshForexLive();refreshCryptoLive();
        long now=System.currentTimeMillis();
        if(now-lastUiPageRefreshMs>=PAGE_REFRESH_MS){lastUiPageRefreshMs=now;refreshPage(false);}
        main.postDelayed(this,LIVE_REFRESH_MS);
    }};

    @Override public void onCreate(Bundle b){
        super.onCreate(b);
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        buildUi();ensureMonitor(true);renderCurrent(true);
    }
    @Override protected void onResume(){super.onResume();resumed=true;ensureMonitor(false);main.removeCallbacks(loop);main.post(loop);}
    @Override protected void onPause(){resumed=false;main.removeCallbacks(loop);super.onPause();}
    @Override protected void onDestroy(){main.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}
    @Override public void onBackPressed(){if(detail){detail=false;selectedSignal=null;renderSignals(false);}else super.onBackPressed();}

    private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
    private GradientDrawable shape(int fill,int radius,int stroke){GradientDrawable d=new GradientDrawable();d.setColor(fill);d.setCornerRadius(dp(radius));if(stroke!=Color.TRANSPARENT)d.setStroke(dp(1),stroke);return d;}
    private TextView tv(String s,int sp,int color,boolean bold){TextView v=new TextView(this);v.setText(s);v.setTextSize(sp);v.setTextColor(color);v.setTypeface(Typeface.create(Typeface.MONOSPACE,bold?Typeface.BOLD:Typeface.NORMAL));v.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout row(){LinearLayout r=new LinearLayout(this);r.setOrientation(LinearLayout.HORIZONTAL);r.setGravity(Gravity.CENTER_VERTICAL);return r;}
    private LinearLayout column(){LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);return c;}
    private LinearLayout card(){LinearLayout c=column();c.setPadding(dp(15),dp(13),dp(15),dp(13));c.setBackground(shape(PANEL,15,BORDER));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(6),0,dp(6));c.setLayoutParams(p);return c;}
    private TextView chip(String s,int color){TextView v=tv(s,9,color,true);v.setPadding(dp(8),dp(5),dp(8),dp(5));v.setGravity(Gravity.CENTER);v.setBackground(shape(Color.argb(28,Color.red(color),Color.green(color),Color.blue(color)),9,color));return v;}
    private Button button(String s,boolean selected,View.OnClickListener l){Button b=new Button(this);b.setText(s);b.setAllCaps(false);b.setTextSize(10);b.setTypeface(Typeface.MONOSPACE,Typeface.BOLD);b.setTextColor(selected?BG:TEXT);b.setPadding(dp(8),0,dp(8),0);b.setMinHeight(0);b.setMinimumHeight(0);b.setStateListAnimator(null);b.setBackground(shape(selected?GREEN:PANEL2,11,selected?GREEN:BORDER));b.setOnClickListener(l);pressFeedback(b);return b;}
    private void pressFeedback(View v){v.setOnTouchListener((x,e)->{if(e.getAction()==MotionEvent.ACTION_DOWN)x.animate().scaleX(.985f).scaleY(.985f).alpha(.82f).setDuration(55).start();else if(e.getAction()==MotionEvent.ACTION_UP||e.getAction()==MotionEvent.ACTION_CANCEL)x.animate().scaleX(1f).scaleY(1f).alpha(1f).setDuration(90).start();return false;});}
    private TextView line(String k,String v,int c){TextView t=tv(k+"  "+v,11,c,true);t.setPadding(0,dp(3),0,dp(3));return t;}

    private void buildUi(){
        LinearLayout root=column();root.setBackgroundColor(BG);
        LinearLayout head=column();head.setPadding(dp(14),dp(12),dp(14),dp(7));
        LinearLayout top=row();LinearLayout titles=column();
        TextView logo=tv("SignalHub V3",22,TEXT,true);subtitle=tv("LIVE TRADING SIGNALS • FAST • CLEAR • ACTIONABLE",8,MUTED,true);
        titles.addView(logo);titles.addView(subtitle);top.addView(titles,new LinearLayout.LayoutParams(0,-2,1f));top.addView(chip("V"+APP_VERSION,BLUE));head.addView(top);

        LinearLayout live=row();fxLive=chip("EXNESS • OFFLINE",RED);cryptoLive=chip("CRYPTO • OFFLINE",RED);
        LinearLayout.LayoutParams lp1=new LinearLayout.LayoutParams(0,-2,1f);lp1.setMargins(0,dp(8),dp(4),0);LinearLayout.LayoutParams lp2=new LinearLayout.LayoutParams(0,-2,1f);lp2.setMargins(dp(4),dp(8),0,0);
        live.addView(fxLive,lp1);live.addView(cryptoLive,lp2);head.addView(live);

        signalControls=column();
        LinearLayout styles=row();scalpBtn=button("SCALP",true,v->setStyle("SCALP"));swingBtn=button("SWING",false,v->setStyle("SWING"));
        LinearLayout.LayoutParams sp1=new LinearLayout.LayoutParams(0,dp(43),1f);sp1.setMargins(0,dp(9),dp(4),0);LinearLayout.LayoutParams sp2=new LinearLayout.LayoutParams(0,dp(43),1f);sp2.setMargins(dp(4),dp(9),0,0);styles.addView(scalpBtn,sp1);styles.addView(swingBtn,sp2);signalControls.addView(styles);
        LinearLayout filters=row();String[] fs={"ALL","XAU","FX","OIL","CRYPTO"};for(String f:fs){Button b=button(f,f.equals(filter),v->setFilter(f));filterButtons.put(f,b);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(36),1f);p.setMargins(dp(2),dp(6),dp(2),0);filters.addView(b,p);}signalControls.addView(filters);head.addView(signalControls);root.addView(head);

        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);content=column();content.setPadding(dp(14),dp(3),dp(14),dp(12));scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1f));
        bottom=row();bottom.setPadding(dp(7),dp(6),dp(7),dp(8));bottom.setBackgroundColor(PANEL);root.addView(bottom);setContentView(root);drawBottom();
    }

    private void setStyle(String s){if(style.equals(s))return;style=s;detail=false;selectedSignal=null;paintControls();renderSignals(true);kickScanIfDue();refreshPage(true);}
    private void setFilter(String f){if(filter.equals(f))return;filter=f;detail=false;selectedSignal=null;paintControls();renderSignals(true);kickScanIfDue();refreshPage(false);}
    private void paintControls(){setBtn(scalpBtn,style.equals("SCALP"));setBtn(swingBtn,style.equals("SWING"));for(Map.Entry<String,Button> e:filterButtons.entrySet())setBtn(e.getValue(),e.getKey().equals(filter));}
    private void setBtn(Button b,boolean on){b.setTextColor(on?BG:TEXT);b.setBackground(shape(on?GREEN:PANEL2,11,on?GREEN:BORDER));}
    private void selectScreen(String s){if(screen.equals(s)&&!detail)return;screen=s;detail=false;selectedSignal=null;signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);drawBottom();renderCurrent(true);refreshPage(true);}
    private void drawBottom(){bottom.removeAllViews();String[] keys={"SIGNALS","STATS","SOURCES","SYSTEM"},names={"TÍN HIỆU","THỐNG KÊ","NGUỒN","HỆ THỐNG"};for(int i=0;i<keys.length;i++){final String x=keys[i];Button b=button(names[i],screen.equals(x),v->selectScreen(x));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(48),1f);p.setMargins(dp(2),0,dp(2),0);bottom.addView(b,p);}}
    private void swap(Runnable r){content.animate().cancel();content.setAlpha(.78f);r.run();content.animate().alpha(1f).setDuration(120).start();}

    private void renderCurrent(boolean animate){
        if(screen.equals("SIGNALS"))renderSignals(animate);
        else if(screen.equals("STATS"))renderStats(animate);
        else if(screen.equals("SOURCES"))renderSources(animate);
        else renderSystem(animate);
    }

    private void refreshPage(boolean force){
        if(!resumed&&!force)return;
        if(screen.equals("SOURCES")){main.post(this::updateConnectionViews);return;}
        if(!pageBusy.compareAndSet(false,true))return;
        final String scr=screen,st=style;
        io.execute(()->{try{
            if(scr.equals("SIGNALS"))loadSignalPartitions(st);
            else if(scr.equals("STATS"))loadAllPerformance();
            else if(scr.equals("SYSTEM"))loadSystemStatus();
        }finally{pageBusy.set(false);}});
        if(scr.equals("SIGNALS"))kickScanIfDue();
    }

    private void loadSignalPartitions(String st){
        boolean changed=false;
        for(String m:new String[]{"FOREX","CRYPTO"}){
            try{
                JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market="+m+"&style="+st+"&status=active&limit=100"));
                JSONArray a=root.optJSONArray("signals");if(a==null)a=new JSONArray();
                String key=m+":"+st,fp=fingerprint(a),old=signalFingerprints.put(key,fp);signalCache.put(key,a);lastApiOkMs=System.currentTimeMillis();
                if(old==null||!old.equals(fp))changed=true;
                try{JSONObject perf=new JSONObject(ApiClient.get("/v3/performance?market="+m+"&style="+st)).optJSONObject("performance");if(perf!=null)perfCache.put(key,perf);}catch(Throwable ignored){}
            }catch(Throwable ignored){}
        }
        if(changed&&style.equals(st)&&screen.equals("SIGNALS")&&!detail)main.post(()->renderSignals(false));
    }

    private String fingerprint(JSONArray a){StringBuilder b=new StringBuilder();for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s==null)continue;b.append(s.optString("signalId",s.optString("id",""))).append('|').append(s.optString("status","")).append('|').append(s.optString("outcome","")).append('|').append(s.optDouble("entry",0)).append('|').append(s.optDouble("sl",0)).append('|').append(s.optDouble("tp",0)).append('|').append(s.optInt("score",0)).append(';');}return b.toString();}

    private void kickScanIfDue(){
        if(!screen.equals("SIGNALS")||!scanBusy.compareAndSet(false,true))return;
        final String st=style,f=filter;io.execute(()->{try{
            List<String> markets=new ArrayList<>();if(f.equals("ALL")||f.equals("CRYPTO"))markets.add("CRYPTO");if(!f.equals("CRYPTO"))markets.add("FOREX");
            long now=System.currentTimeMillis();for(String m:markets){String key=m+":"+st;long last=lastScanAt.getOrDefault(key,0L);if(now-last<SCAN_MS)continue;try{ApiClient.get("/v3/scan?market="+m+"&style="+st);lastScanAt.put(key,System.currentTimeMillis());}catch(Throwable ignored){}}
        }finally{scanBusy.set(false);}});
    }

    private List<JSONObject> collectSignals(){
        List<JSONObject> out=new ArrayList<>();for(String m:new String[]{"FOREX","CRYPTO"}){JSONArray a=signalCache.get(m+":"+style);if(a==null)continue;for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s!=null&&acceptFilter(s,m))out.add(s);}}
        out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }
    private boolean acceptFilter(JSONObject s,String fallbackMarket){String m=s.optString("market",fallbackMarket).toUpperCase(Locale.US),sym=s.optString("symbol","").toUpperCase(Locale.US);if(filter.equals("ALL"))return true;if(filter.equals("CRYPTO"))return m.equals("CRYPTO");if(!m.equals("FOREX"))return false;if(filter.equals("XAU"))return sym.startsWith("XAU")||sym.startsWith("XAG");if(filter.equals("OIL"))return sym.contains("OIL")||sym.equals("WTI")||sym.equals("BRENT");if(filter.equals("FX"))return !(sym.startsWith("XAU")||sym.startsWith("XAG")||sym.contains("OIL")||sym.equals("WTI")||sym.equals("BRENT"));return true;}

    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}
        Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();subtitle.setText("LIVE SIGNALS • "+style+" • "+filter);
            LinearLayout title=row();title.addView(tv("TÍN HIỆU",16,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));title.addView(chip(style,CYAN));content.addView(title);
            List<JSONObject> rows=collectSignals();LinearLayout summary=card();summary.addView(tv(rows.size()+" tín hiệu đang hiển thị",12,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));summary.addView(tv("SCALP và SWING là hai partition độc lập • Setup score không phải xác suất thắng.",9,YELLOW,false));content.addView(summary);
            if(rows.isEmpty()){LinearLayout c=card();c.addView(tv(signalCache.containsKey("FOREX:"+style)||signalCache.containsKey("CRYPTO:"+style)?"Chưa có tín hiệu đạt chuẩn ở bộ lọc này.":"Đang đồng bộ tín hiệu live…",12,MUTED,true));c.addView(tv("Không ép lệnh khi dữ liệu stale hoặc entry đã chạy xa.",10,MUTED,false));content.addView(c);return;}
            for(JSONObject s:rows)content.addView(signalCard(s));
        };if(animate)swap(body);else body.run();updateAllPriceViews();
    }

    private String performanceSummary(){StringBuilder b=new StringBuilder();for(String m:new String[]{"FOREX","CRYPTO"}){if(filter.equals("CRYPTO")&&!m.equals("CRYPTO"))continue;if(!filter.equals("ALL")&&!filter.equals("CRYPTO")&&!m.equals("FOREX"))continue;JSONObject p=perfCache.get(m+":"+style);if(p==null)continue;if(b.length()>0)b.append("  •  ");b.append(m).append(" WR ").append(p.optString("winRateLabel","—"));int n=p.optInt("resolved",p.optInt("tp",0)+p.optInt("sl",0));if(n>0)b.append(" (").append(n).append(" lệnh)");}return b.length()==0?"WR chỉ tính từ lệnh đã TP/SL":""+b;}

    private View signalCard(JSONObject s){
        LinearLayout c=card();String sym=s.optString("symbol","—"),side=sideVi(s.optString("side","—")),order=s.optString("orderType","MARKET"),market=s.optString("market","FOREX");int col=side.equals("BUY")?GREEN:side.equals("SELL")?RED:MUTED;
        LinearLayout h=row();h.addView(tv(sym,18,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));TextView grade=chip(s.optString("qualityGrade",grade(s.optInt("score",0)))+" • "+s.optInt("score",0)+"/100",BLUE);LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-2,-2);gp.setMargins(dp(7),0,0,0);h.addView(grade,gp);c.addView(h);
        LinearLayout meta=row();meta.addView(tv(style+" • "+order,10,CYAN,true),new LinearLayout.LayoutParams(0,-2,1f));meta.addView(chip(lifecycleVi(s),lifecycleColor(s)));c.addView(meta);
        String id=s.optString("signalId",s.optString("id",sym+":"+style));double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp3=s.optDouble("tp3",s.optDouble("tp",0));double px=priceFor(s,e);
        TextView pv=tv(fmt(px),21,CYAN,true);pv.setPadding(0,dp(8),0,0);c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);
        TextView sv=tv(sourceText(market),9,stateColor(market.equals("FOREX")?fxState:cryptoState),true);c.addView(sv);sourceViews.put(id,sv);
        LinearLayout levels=row();LinearLayout left=column(),right=column();left.addView(metric("ENTRY",fmt(e),TEXT));left.addView(metric("SL",fmt(sl),RED));left.addView(metric("RR","1 : "+String.format(Locale.US,"%.2f",s.optDouble("targetRR",0)),CYAN));right.addView(metric("TP1",fmt(s.optDouble("tp1",0)),GREEN));right.addView(metric("TP2",fmt(s.optDouble("tp2",0)),GREEN));right.addView(metric("TP3",fmt(tp3),GREEN));levels.addView(left,new LinearLayout.LayoutParams(0,-2,1f));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(0,-2,1f);rp.setMargins(dp(16),0,0,0);levels.addView(right,rp);c.addView(levels);
        c.addView(tv("Setup quality "+s.optInt("score",0)+"/100 • "+historicalWr(market),9,MUTED,false));
        pressFeedback(c);c.setClickable(true);c.setOnClickListener(v->{selectedSignal=s;detail=true;renderDetail(s,true);});return c;
    }

    private TextView metric(String k,String v,int color){TextView t=tv(String.format(Locale.US,"%-6s %s",k,v),11,color,true);t.setPadding(0,dp(3),0,dp(3));return t;}
    private String historicalWr(String market){JSONObject p=perfCache.get(market+":"+style);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}

    private void renderDetail(JSONObject s,boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();subtitle.setText("CHI TIẾT TÍN HIỆU • "+style);
        Button back=button("← QUAY LẠI",false,v->{detail=false;selectedSignal=null;renderSignals(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(42)));
        LinearLayout c=card();String market=s.optString("market","FOREX"),side=sideVi(s.optString("side","—")),id=s.optString("signalId",s.optString("id","detail"));int col=side.equals("BUY")?GREEN:RED;
        LinearLayout h=row();h.addView(tv(s.optString("symbol","—"),22,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));c.addView(h);c.addView(tv(style+" • "+s.optString("orderType","MARKET")+" • "+lifecycleVi(s),10,CYAN,true));
        TextView pv=tv(fmt(priceFor(s,s.optDouble("entry",0))),26,CYAN,true);pv.setPadding(0,dp(10),0,dp(3));c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);TextView sv=tv(sourceText(market),10,stateColor(market.equals("FOREX")?fxState:cryptoState),true);c.addView(sv);sourceViews.put(id,sv);
        c.addView(line("ENTRY",fmt(s.optDouble("entry",0)),TEXT));c.addView(line("SL",fmt(s.optDouble("sl",0)),RED));c.addView(line("TP1",fmt(s.optDouble("tp1",0)),GREEN));c.addView(line("TP2",fmt(s.optDouble("tp2",0)),GREEN));c.addView(line("TP3",fmt(s.optDouble("tp3",s.optDouble("tp",0))),GREEN));c.addView(line("RR","1 : "+String.format(Locale.US,"%.2f",s.optDouble("targetRR",0)),CYAN));
        c.addView(line("SETUP QUALITY",s.optInt("score",0)+"/100 • "+s.optString("qualityGrade",grade(s.optInt("score",0))),BLUE));c.addView(tv("Điểm setup không phải xác suất thắng. "+historicalWr(market)+".",9,YELLOW,false));
        JSONArray why=s.optJSONArray("rationale");if(why!=null&&why.length()>0){TextView w=tv("LÝ DO",11,TEXT,true);w.setPadding(0,dp(10),0,dp(2));c.addView(w);for(int i=0;i<why.length();i++)c.addView(tv("• "+why.optString(i),10,MUTED,false));}
        c.addView(tv("Phát: "+time(s.optString("issuedAt",""))+" • ID: "+id,9,MUTED,false));content.addView(c);
    };if(animate)swap(body);else body.run();updateAllPriceViews();}

    private void loadAllPerformance(){boolean changed=false;for(String m:new String[]{"FOREX","CRYPTO"})for(String st:new String[]{"SCALP","SWING"}){try{JSONObject p=new JSONObject(ApiClient.get("/v3/performance?market="+m+"&style="+st)).optJSONObject("performance");if(p!=null){String k=m+":"+st,old=perfCache.containsKey(k)?perfCache.get(k).toString():"";perfCache.put(k,p);if(!old.equals(p.toString()))changed=true;lastApiOkMs=System.currentTimeMillis();}}catch(Throwable ignored){}}if(changed&&screen.equals("STATS"))main.post(()->renderStats(false));}
    private void renderStats(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("PERFORMANCE STATISTICS • RESOLVED TRADES ONLY");content.addView(tv("THỐNG KÊ HIỆU SUẤT",16,TEXT,true));LinearLayout note=card();note.addView(tv("Win Rate chỉ tính lệnh đã đóng bằng TP/SL.",11,YELLOW,true));note.addView(tv("WATCH/PENDING không được tính thắng thua. Setup score không phải win probability.",9,MUTED,false));content.addView(note);for(String m:new String[]{"FOREX","CRYPTO"})for(String st:new String[]{"SCALP","SWING"})content.addView(perfCard(m,st));};if(animate)swap(body);else body.run();}
    private View perfCard(String m,String st){LinearLayout c=card(),h=row();h.addView(tv(m+" • "+st,14,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(st,st.equals("SCALP")?CYAN:BLUE));c.addView(h);JSONObject p=perfCache.get(m+":"+st);if(p==null){c.addView(tv("Đang đồng bộ lịch sử…",10,MUTED,false));return c;}int tp=p.optInt("tp",0),sl=p.optInt("sl",0),n=p.optInt("resolved",tp+sl);c.addView(line("WIN RATE",p.optString("winRateLabel","—"),GREEN));c.addView(line("RESOLVED",String.valueOf(n),TEXT));c.addView(line("TP / SL",tp+" / "+sl,TEXT));c.addView(line("NET R",String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)),p.optDouble("netRResolved",0)>=0?GREEN:RED));c.addView(tv(p.optBoolean("sampleAdequate",false)?"Sample ≥30 • đủ để tham khảo tốt hơn":"Sample <30 • dữ liệu còn sơ bộ",9,p.optBoolean("sampleAdequate",false)?MUTED:YELLOW,false));return c;}

    private void renderSources(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("DATA SOURCES • FRESHNESS • CONNECTION HEALTH");content.addView(tv("NGUỒN DỮ LIỆU",16,TEXT,true));LinearLayout fx=card();fx.addView(tv("FOREX • EXNESS MT5",13,TEXT,true));fx.addView(line("STATUS",fxState,stateColor(fxState)));fx.addView(line("QUOTE AGE",fxQuoteAgeMs<0?"—":String.format(Locale.US,"%.1fs",fxQuoteAgeMs/1000.0),stateColor(fxState)));fx.addView(line("SYMBOLS",String.valueOf(fxCount),TEXT));fx.addView(tv("Exness là execution-price/fill authority cho Forex.",9,MUTED,false));content.addView(fx);LinearLayout cr=card();cr.addView(tv("CRYPTO • "+cryptoProvider,13,TEXT,true));cr.addView(line("STATUS",cryptoState,stateColor(cryptoState)));cr.addView(line("SYMBOLS",String.valueOf(cryptoCount),TEXT));cr.addView(tv("Bybit ưu tiên; fallback phải được gắn đúng tên nguồn, không giả nhãn Bybit LIVE.",9,MUTED,false));content.addView(cr);LinearLayout rule=card();rule.addView(tv("FRESHNESS GATE",12,CYAN,true));rule.addView(tv("LIVE → được phép đánh giá entry. DELAYED/STALE/OFFLINE → app giữ dữ liệu cũ để xem nhưng không được coi là quote live mới.",10,MUTED,false));content.addView(rule);};if(animate)swap(body);else body.run();}

    private void loadSystemStatus(){try{JSONObject p=new JSONObject(ApiClient.get("/v3/status"));systemStatus=p;systemState=p.optBoolean("ok",false)?"RUNNING":"DEGRADED";lastApiOkMs=System.currentTimeMillis();if(screen.equals("SYSTEM"))main.post(()->renderSystem(false));}catch(Throwable e){systemState=lastApiOkMs==0?"OFFLINE":"DEGRADED";if(screen.equals("SYSTEM"))main.post(()->renderSystem(false));}}
    private void renderSystem(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("SYSTEM STATUS • SIGNAL ENGINE • LIVE FEEDS");content.addView(tv("HỆ THỐNG",16,TEXT,true));LinearLayout c=card();c.addView(statusRow("Signal Engine",systemState));c.addView(statusRow("Quote Feed • Forex",fxState));c.addView(statusRow("Quote Feed • Crypto",cryptoState));c.addView(statusRow("Push Monitor",monitorStarted?"RUNNING":"OFFLINE"));c.addView(statusRow("API Connectivity",lastApiOkMs>0&&System.currentTimeMillis()-lastApiOkMs<15000?"ONLINE":"DEGRADED"));content.addView(c);LinearLayout meta=card();meta.addView(line("APP VERSION",APP_VERSION,BLUE));if(systemStatus!=null){meta.addView(line("BACKEND",systemStatus.optString("version","—"),TEXT));meta.addView(line("CHECKPOINT",systemStatus.optString("checkpoint","—"),TEXT));}meta.addView(line("LAST API SYNC",lastApiOkMs==0?"—":relativeAge(System.currentTimeMillis()-lastApiOkMs),MUTED));content.addView(meta);};if(animate)swap(body);else body.run();}
    private View statusRow(String name,String state){LinearLayout r=row();r.setPadding(0,dp(5),0,dp(5));r.addView(tv(name,11,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));r.addView(chip(state,stateColor(state)));return r;}

    private void refreshForexLive(){if(!fxBusy.compareAndSet(false,true))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/forex/live"));JSONArray a=p.optJSONArray("quotes");fxPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null){double mid=q.optDouble("mid",0);if(mid>0)fxPrices.put(q.optString("symbol",""),mid);}}fxState=p.optString("state","OFFLINE");fxQuoteAgeMs=p.optLong("quoteAgeMs",-1);fxCount=p.optInt("count",a==null?0:a.length());fxLastOkMs=System.currentTimeMillis();lastApiOkMs=fxLastOkMs;}catch(Throwable e){long age=fxLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-fxLastOkMs;fxState=age<10000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{fxBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);});}});}
    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000"));JSONArray a=p.optJSONArray("tickers");cryptoPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null)cryptoPrices.put(q.optString("symbol",""),q);}cryptoProvider=p.optString("provider","CRYPTO");cryptoState=p.optBoolean("live",true)?"LIVE":"DELAYED";cryptoCount=p.optInt("count",a==null?0:a.length());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;}catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;cryptoState=age<10000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);});}});}

    private void updateConnectionViews(){int fc=stateColor(fxState),cc=stateColor(cryptoState);fxLive.setText("EXNESS • "+fxState+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.1fs",fxQuoteAgeMs/1000.0):""));fxLive.setTextColor(fc);fxLive.setBackground(shape(Color.argb(28,Color.red(fc),Color.green(fc),Color.blue(fc)),9,fc));cryptoLive.setText(cryptoProvider+" • "+cryptoState);cryptoLive.setTextColor(cc);cryptoLive.setBackground(shape(Color.argb(28,Color.red(cc),Color.green(cc),Color.blue(cc)),9,cc));}
    private void updateAllPriceViews(){for(Map.Entry<String,TextView> e:priceViews.entrySet()){String id=e.getKey(),m=viewMarkets.getOrDefault(id,"FOREX");JSONObject s=findSignal(id);double fallback=s==null?0:s.optDouble("entry",0),px=s==null?fallback:priceFor(s,fallback);e.getValue().setText(fmt(px));e.getValue().setTextColor(CYAN);TextView sv=sourceViews.get(id);if(sv!=null){String state=m.equals("FOREX")?fxState:cryptoState;sv.setText(sourceText(m));sv.setTextColor(stateColor(state));}}}
    private JSONObject findSignal(String id){if(selectedSignal!=null&&id.equals(selectedSignal.optString("signalId",selectedSignal.optString("id",""))))return selectedSignal;for(JSONArray a:signalCache.values())for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s!=null&&id.equals(s.optString("signalId",s.optString("id",""))))return s;}return null;}
    private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol",""),m=s.optString("market","FOREX");if(m.equals("CRYPTO")){JSONObject q=cryptoPrices.get(sym);return q==null?fallback:q.optDouble("lastPrice",fallback);}Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}
    private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS • "+fxState+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.1fs",fxQuoteAgeMs/1000.0):"");long age=cryptoLastOkMs==0?-1:System.currentTimeMillis()-cryptoLastOkMs;return cryptoProvider+" • "+cryptoState+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}

    private String lifecycleVi(JSONObject s){String x=s.optString("lifecycle","").toUpperCase(Locale.US);if(x.isEmpty()){String st=s.optString("status","");if(st.equals("PENDING"))x="PENDING_ENTRY";else if(st.equals("OPEN"))x="ACTIVE";else x=st;}return switch(x){case "PENDING_ENTRY"->"CHỜ ENTRY";case "ACTIVE"->s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP":"ĐANG CHẠY";case "TP1_HIT"->"TP1";case "TP2_HIT"->"TP2";case "TP3_HIT"->"TP ĐẠT";case "STOP_LOSS_HIT"->"SL";case "CANCELLED"->"ĐÃ HỦY";case "EXPIRED"->"HẾT HẠN";default->x.isEmpty()?"WATCHING":x;};}
    private int lifecycleColor(JSONObject s){String x=lifecycleVi(s);if(x.contains("SL")||x.contains("HỦY")||x.contains("HẾT"))return RED;if(x.contains("CHỜ"))return YELLOW;return GREEN;}
    private String sideVi(String s){String x=s.toUpperCase(Locale.US);return (x.equals("LONG")||x.equals("BUY"))?"BUY":(x.equals("SHORT")||x.equals("SELL"))?"SELL":x;}
    private String grade(int score){return score>=95?"A+":score>=90?"A":score>=85?"A-":score>=80?"B+":"B";}
    private int stateColor(String s){String x=String.valueOf(s).toUpperCase(Locale.US);if(x.equals("LIVE")||x.equals("ONLINE")||x.equals("RUNNING"))return GREEN;if(x.equals("DELAYED")||x.equals("DEGRADED")||x.equals("CONNECTING"))return YELLOW;return RED;}
    private boolean notifyPermission(){return Build.VERSION.SDK_INT<33||checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;}
    private void ensureMonitor(boolean ask){if(monitorStarted)return;if(!notifyPermission()){if(ask&&Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},REQ_NOTIFICATIONS);return;}try{Intent i=new Intent(this,MonitorService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);monitorStarted=true;}catch(Throwable ignored){}}
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] grantResults){super.onRequestPermissionsResult(requestCode,permissions,grantResults);if(requestCode==REQ_NOTIFICATIONS&&grantResults.length>0&&grantResults[0]==PackageManager.PERMISSION_GRANTED)ensureMonitor(false);}

    private String fmt(double v){if(!Double.isFinite(v)||v<=0)return"—";if(v>=1000)return String.format(Locale.US,"%.2f",v);if(v>=100)return String.format(Locale.US,"%.3f",v);if(v>=10)return String.format(Locale.US,"%.4f",v);if(v>=1)return String.format(Locale.US,"%.5f",v);return String.format(Locale.US,"%.7f",v);}
    private long parseMs(String iso){try{return Instant.parse(iso).toEpochMilli();}catch(Exception e){return 0;}}
    private String time(String iso){try{return DateTimeFormatter.ofPattern("dd/MM HH:mm:ss",Locale.US).withZone(ZoneId.systemDefault()).format(Instant.parse(iso));}catch(Exception e){return iso.isEmpty()?"—":iso;}}
    private String relativeAge(long ms){if(ms<1000)return"vừa xong";if(ms<60000)return(ms/1000)+"s trước";return(ms/60000)+"m trước";}
}
