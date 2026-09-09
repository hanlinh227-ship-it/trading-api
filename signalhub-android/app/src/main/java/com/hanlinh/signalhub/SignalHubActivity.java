package com.hanlinh.signalhub;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.content.SharedPreferences;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

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
    private static final String APP_VERSION="3.14.0";
    private static final long LIVE_REFRESH_MS=1000L; // stable crypto REST cadence; background monitor is independent
    private static final long PAGE_REFRESH_MS=3000L;
    private static final long SCAN_MS=30000L;
    private static final int BG=Color.rgb(2,6,10),PANEL=Color.rgb(7,14,21),PANEL2=Color.rgb(12,23,33),BORDER=Color.rgb(28,52,70);
    private static final int TEXT=Color.rgb(242,248,252),MUTED=Color.rgb(123,148,166),GREEN=Color.rgb(48,232,159),RED=Color.rgb(255,76,102),YELLOW=Color.rgb(255,201,67),BLUE=Color.rgb(78,154,255),CYAN=Color.rgb(59,224,238);

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
    private final Map<String,TradeGauge> gaugeViews=new ConcurrentHashMap<>();
    private final Map<String,EntryGauge> entryGaugeViews=new ConcurrentHashMap<>();
    private final Map<String,TextView> pnlViews=new ConcurrentHashMap<>();
    private final Map<String,String> viewMarkets=new ConcurrentHashMap<>();
    private final Map<String,Long> lastScanAt=new ConcurrentHashMap<>();
    private final Map<String,Button> filterButtons=new ConcurrentHashMap<>();

    private LinearLayout content,bottom,signalControls;
    private TextView fxLive,cryptoLive,subtitle;
    private Button scalpBtn,swingBtn;
    private boolean resumed,detail,monitorStarted;
    private String screen="HOME",style="SCALP",filter="CRYPTO";
    private JSONObject selectedSignal,systemStatus;
    private volatile String fxState="OFFLINE",cryptoState="OFFLINE",cryptoProvider="CRYPTO",systemState="CONNECTING";
    private volatile long fxQuoteAgeMs=-1,fxLastOkMs=0,cryptoLastOkMs=0,lastApiOkMs=0,lastUiPageRefreshMs=0;
    private volatile int fxCount=0,cryptoCount=0;
    private volatile long fxStreamLastMs=0;
    private WebSocket fxSocket;

    private final Runnable loop=new Runnable(){@Override public void run(){
        if(!resumed)return;
        refreshCryptoLive();
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
        TextView logo=tv("SIGNALHUB CRYPTO",22,TEXT,true);subtitle=tv("CRYPTO ONLY • SCALP ≠ SWING • REALTIME • V3.14",8,MUTED,true);
        titles.addView(logo);titles.addView(subtitle);top.addView(titles,new LinearLayout.LayoutParams(0,-2,1f));top.addView(chip("V"+APP_VERSION,BLUE));head.addView(top);

        LinearLayout live=row();fxLive=chip("FOREX • DISABLED",MUTED);cryptoLive=chip("CRYPTO • OFFLINE",RED);
        LinearLayout.LayoutParams lp2=new LinearLayout.LayoutParams(0,-2,1f);lp2.setMargins(0,dp(8),0,0);live.addView(cryptoLive,lp2);head.addView(live);

        signalControls=column();
        LinearLayout styles=row();scalpBtn=button("SCALP",true,v->setStyle("SCALP"));swingBtn=button("SWING",false,v->setStyle("SWING"));
        LinearLayout.LayoutParams sp1=new LinearLayout.LayoutParams(0,dp(43),1f);sp1.setMargins(0,dp(9),dp(4),0);LinearLayout.LayoutParams sp2=new LinearLayout.LayoutParams(0,dp(43),1f);sp2.setMargins(dp(4),dp(9),0,0);styles.addView(scalpBtn,sp1);styles.addView(swingBtn,sp2);signalControls.addView(styles);
        head.addView(signalControls);root.addView(head);

        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);content=column();content.setPadding(dp(14),dp(3),dp(14),dp(12));scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1f));
        bottom=row();bottom.setPadding(dp(7),dp(6),dp(7),dp(8));bottom.setBackgroundColor(PANEL);root.addView(bottom);setContentView(root);drawBottom();signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);
    }

    private void setStyle(String s){if(style.equals(s))return;style=s;detail=false;selectedSignal=null;paintControls();renderSignals(true);kickScanIfDue();refreshPage(true);}
    private void setFilter(String f){if(filter.equals(f))return;filter=f;detail=false;selectedSignal=null;paintControls();renderSignals(true);kickScanIfDue();refreshPage(false);}
    private void paintControls(){setBtn(scalpBtn,style.equals("SCALP"));setBtn(swingBtn,style.equals("SWING"));for(Map.Entry<String,Button> e:filterButtons.entrySet())setBtn(e.getValue(),e.getKey().equals(filter));}
    private void setBtn(Button b,boolean on){b.setTextColor(on?BG:TEXT);b.setBackground(shape(on?GREEN:PANEL2,11,on?GREEN:BORDER));}
    private void selectScreen(String s){
        if(screen.equals(s)&&!detail)return;
        screen=s;detail=false;selectedSignal=null;
        signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);
        drawBottom();renderCurrent(true);refreshPage(true);
    }
    private void drawBottom(){
        bottom.removeAllViews();
        String[] keys={"HOME","SIGNALS","STATS","ALERTS","SETTINGS"};
        String[] names={"⌂\nTRANG CHỦ","⚡\nTÍN HIỆU","▥\nTHỐNG KÊ","♢\nTHÔNG BÁO","⚙\nCÀI ĐẶT"};
        for(int i=0;i<keys.length;i++){
            final String x=keys[i];Button b=button(names[i],screen.equals(x),v->selectScreen(x));
            b.setTextSize(8);b.setGravity(Gravity.CENTER);b.setPadding(dp(2),0,dp(2),0);
            LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(54),1f);p.setMargins(dp(1),0,dp(1),0);bottom.addView(b,p);
        }
    }
    private void swap(Runnable r){content.animate().cancel();content.setAlpha(.78f);r.run();content.animate().alpha(1f).setDuration(120).start();}

    private void renderCurrent(boolean animate){
        if(screen.equals("HOME"))renderHome(animate);
        else if(screen.equals("SIGNALS"))renderSignals(animate);
        else if(screen.equals("STATS"))renderStats(animate);
        else if(screen.equals("ALERTS"))renderAlerts(animate);
        else renderSettings(animate);
    }

    private void refreshPage(boolean force){
        if(!resumed&&!force)return;
        if(!pageBusy.compareAndSet(false,true))return;
        final String scr=screen,st=style;
        io.execute(()->{try{
            if(scr.equals("HOME"))loadDashboardData();
            else if(scr.equals("SIGNALS"))loadSignalPartitions(st);
            else if(scr.equals("STATS"))loadAllPerformance();
            else if(scr.equals("SETTINGS"))loadSystemStatus();
        }finally{pageBusy.set(false);}});
        if(scr.equals("SIGNALS"))kickScanIfDue();
    }

    private void loadSignalPartitions(String st){
        boolean changed=false;String m="CRYPTO";
        try{
            JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market=CRYPTO&style="+st+"&status=active&limit=100"));
            JSONArray arr=root.optJSONArray("signals");if(arr==null)arr=new JSONArray();String key="CRYPTO:"+st,fp=fingerprint(arr),old=signalFingerprints.put(key,fp);signalCache.put(key,arr);lastApiOkMs=System.currentTimeMillis();if(old==null||!old.equals(fp))changed=true;
            try{JSONObject perf=new JSONObject(ApiClient.get("/v3/performance?market=CRYPTO&style="+st)).optJSONObject("performance");if(perf!=null)perfCache.put(key,perf);}catch(Throwable ignored){}
        }catch(Throwable ignored){}
        if(changed&&style.equals(st)&&screen.equals("SIGNALS")&&!detail)main.post(()->renderSignals(false));
    }

    private String fingerprint(JSONArray a){StringBuilder b=new StringBuilder();for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s==null)continue;b.append(s.optString("signalId",s.optString("id",""))).append('|').append(s.optString("status","")).append('|').append(s.optString("outcome","")).append('|').append(s.optDouble("entry",0)).append('|').append(s.optDouble("sl",0)).append('|').append(s.optDouble("tp",0)).append(';');}return b.toString();}

    private void kickScanIfDue(){
        if(!screen.equals("SIGNALS")||!scanBusy.compareAndSet(false,true))return;
        final String st=style;io.execute(()->{try{long now=System.currentTimeMillis();String key="CRYPTO:"+st;long last=lastScanAt.getOrDefault(key,0L);if(now-last>=SCAN_MS){try{ApiClient.get("/v3/scan?market=CRYPTO&style="+st);lastScanAt.put(key,System.currentTimeMillis());}catch(Throwable ignored){}}}finally{scanBusy.set(false);}});
    }

    private List<JSONObject> collectSignals(){
        List<JSONObject> out=new ArrayList<>();JSONArray arr=signalCache.get("CRYPTO:"+style);if(arr!=null)for(int i=0;i<arr.length();i++){JSONObject s=arr.optJSONObject(i);if(s!=null)out.add(s);}out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }
    private boolean acceptFilter(JSONObject s,String fallbackMarket){return "CRYPTO".equalsIgnoreCase(s.optString("market",fallbackMarket));}
    private void addOrderSection(String title,List<JSONObject> rows,int color,String sub){
        LinearLayout h=row();TextView t=tv(title,13,color,true);h.addView(t,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(String.valueOf(rows.size()),color));content.addView(h);content.addView(tv(sub,9,MUTED,false));
        if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Không có lệnh trong nhóm này.",10,MUTED,true));content.addView(z);return;}
        for(JSONObject s:rows)content.addView(signalCard(s));
    }

    private String performanceSummary(){StringBuilder b=new StringBuilder();for(String m:new String[]{"FOREX","CRYPTO"}){if(filter.equals("CRYPTO")&&!m.equals("CRYPTO"))continue;if(!filter.equals("ALL")&&!filter.equals("CRYPTO")&&!m.equals("FOREX"))continue;JSONObject p=perfCache.get(m+":"+style);if(p==null)continue;if(b.length()>0)b.append("  •  ");b.append(m).append(" WR ").append(p.optString("winRateLabel","—"));int n=p.optInt("resolved",p.optInt("tp",0)+p.optInt("sl",0));if(n>0)b.append(" (").append(n).append(" lệnh)");}return b.length()==0?"WR chỉ tính từ lệnh đã TP/SL":""+b;}

    private View signalCard(JSONObject s){
        LinearLayout c=card();String sym=s.optString("symbol","—"),side=sideVi(s.optString("side","—")),order=s.optString("orderType","MARKET"),market=s.optString("market","FOREX"),signalStyle=s.optString("style",style);int col=side.equals("BUY")?GREEN:side.equals("SELL")?RED:MUTED;
        LinearLayout h=row();h.addView(tv(sym,18,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));TextView regime=chip(s.optString("marketRegime","MARKET READ").replace('_',' '),BLUE);LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-2,-2);gp.setMargins(dp(7),0,0,0);h.addView(regime,gp);c.addView(h);
        LinearLayout meta=row();meta.addView(tv(signalStyle+" • "+orderDisplay(s,pxForOrder(s)),10,orderColor(s,pxForOrder(s)),true),new LinearLayout.LayoutParams(0,-2,1f));meta.addView(chip(lifecycleVi(s),lifecycleColor(s)));c.addView(meta);
        String id=s.optString("signalId",s.optString("id",sym+":"+signalStyle));double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp3=s.optDouble("tp3",s.optDouble("tp",0));double px=priceFor(s,e);
        c.addView(tv("GIÁ LIVE",8,MUTED,true));TextView pv=tv(fmt(px),21,CYAN,true);pv.setPadding(0,dp(4),0,0);c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);
        TextView sv=tv(sourceText(market),9,stateColor(market.equals("FOREX")?fxState:cryptoState),true);c.addView(sv);sourceViews.put(id,sv);
        TextView pnl=tv(tradeStatusText(s,px),11,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(7),0,dp(2));c.addView(pnl);pnlViews.put(id,pnl);
        if(isDisplayLive(s,px)){TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(58)));gaugeViews.put(id,gauge);}else{EntryGauge eg=new EntryGauge();eg.setData(s,px);c.addView(eg,new LinearLayout.LayoutParams(-1,dp(64)));entryGaugeViews.put(id,eg);}
        LinearLayout levels=row();LinearLayout left=column(),right=column();left.addView(metric("ENTRY",fmt(e),TEXT));left.addView(metric("SL",fmt(sl),RED));left.addView(metric("RR","1 : "+String.format(Locale.US,"%.2f",targetR(s)),CYAN));right.addView(metric("TP1",fmt(s.optDouble("tp1",0)),GREEN));right.addView(metric("TP2",fmt(s.optDouble("tp2",0)),GREEN));right.addView(metric("TP3",fmt(tp3),GREEN));levels.addView(left,new LinearLayout.LayoutParams(0,-2,1f));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(0,-2,1f);rp.setMargins(dp(16),0,0,0);levels.addView(right,rp);c.addView(levels);
        c.addView(tv("BOT • "+s.optString("judgment",s.optString("marketRegime","MARKET JUDGMENT").replace('_',' '))+" • "+historicalWr(market,signalStyle),9,MUTED,false));
        pressFeedback(c);c.setClickable(true);c.setOnClickListener(v->{selectedSignal=s;detail=true;renderDetail(s,true);});return c;
    }

    private TextView metric(String k,String v,int color){TextView t=tv(String.format(Locale.US,"%-6s %s",k,v),11,color,true);t.setPadding(0,dp(3),0,dp(3));return t;}
    private String historicalWr(String market){return historicalWr(market,style);}

    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}
        Runnable body=()->{
            content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();
            subtitle.setText("CRYPTO REALTIME • CHỌN SCALP HOẶC SWING • ENTRY / SL / TP");
            LinearLayout title=row();title.addView(tv("CRYPTO SIGNALS",16,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));title.addView(chip(style,CYAN));content.addView(title);
            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),limitRows=new ArrayList<>(),stopRows=new ArrayList<>();
            for(JSONObject x:rows){double px=priceFor(x,x.optDouble("entry",0));if(isDisplayLive(x,px))liveRows.add(x);else if("STOP".equalsIgnoreCase(x.optString("orderType","")))stopRows.add(x);else limitRows.add(x);}
            LinearLayout summary=card();summary.addView(tv("CRYPTO ONLY • QUALITY-FIRST",10,CYAN,true));summary.addView(tv("ĐANG XEM: "+style+" • KHÔNG TRỘN STYLE",12,CYAN,true));summary.addView(tv("LIVE "+liveRows.size()+" • LIMIT "+limitRows.size()+" • STOP "+stopRows.size(),11,TEXT,true));summary.addView(tv(performanceSummary(),9,MUTED,true));content.addView(summary);
            addCryptoSignalGroup("●  LIVE",liveRows,GREEN);
            addCryptoSignalGroup("◷  LIMIT",limitRows,YELLOW);
            addCryptoSignalGroup("△  STOP",stopRows,YELLOW);
        };
        if(animate)swap(body);else body.run();updateAllPriceViews();
    }

    private void addCryptoSignalGroup(String name,List<JSONObject> rows,int color){
        LinearLayout h=row();h.addView(tv(name,13,color,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(String.valueOf(rows.size()),color));content.addView(h);
        if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Chưa có setup đạt hard-quality trong nhóm này.",10,MUTED,true));content.addView(z);return;}
        for(JSONObject x:rows)content.addView(signalCard(x));
    }

    private void renderDetail(JSONObject s,boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText("CHI TIẾT LỆNH • LIVE / PENDING ENTRY");
        Button back=button("‹  QUAY LẠI",false,v->{detail=false;selectedSignal=null;renderSignals(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(42)));
        LinearLayout c=card();String market=s.optString("market","FOREX"),signalStyle=s.optString("style",style),side=sideVi(s.optString("side","—")),id=s.optString("signalId",s.optString("id","detail"));int col=side.equals("BUY")?GREEN:RED;
        LinearLayout h=row();h.addView(tv(s.optString("symbol","—"),24,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));c.addView(h);c.addView(tv(signalStyle+" • "+orderDisplay(s,priceFor(s,s.optDouble("entry",0)))+" • "+lifecycleVi(s),10,orderColor(s,priceFor(s,s.optDouble("entry",0))),true));
        double px=priceFor(s,s.optDouble("entry",0));c.addView(tv("GIÁ LIVE HIỆN TẠI",8,MUTED,true));TextView pv=tv(fmt(px),29,TEXT,true);pv.setPadding(0,dp(5),0,dp(3));c.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);TextView sv=tv(sourceText(market),10,stateColor(market.equals("FOREX")?fxState:cryptoState),true);c.addView(sv);sourceViews.put(id,sv);
        TextView pnl=tv(tradeStatusText(s,px),14,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(12),0,dp(5));c.addView(pnl);pnlViews.put(id,pnl);if(isDisplayLive(s,px)){TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));c.addView(gauge,new LinearLayout.LayoutParams(-1,dp(72)));gaugeViews.put(id,gauge);}else{EntryGauge eg=new EntryGauge();eg.setData(s,px);c.addView(eg,new LinearLayout.LayoutParams(-1,dp(76)));entryGaugeViews.put(id,eg);}
        c.addView(line("ENTRY",fmt(s.optDouble("entry",0)),TEXT));c.addView(line("SL",fmt(s.optDouble("sl",0)),RED));c.addView(line("TP1",fmt(s.optDouble("tp1",0)),GREEN));c.addView(line("TP2",fmt(s.optDouble("tp2",0)),GREEN));c.addView(line("TP3",fmt(s.optDouble("tp3",s.optDouble("tp",0))),GREEN));c.addView(line("RR","1 : "+String.format(Locale.US,"%.2f",targetR(s)),CYAN));
        c.addView(line("MARKET REGIME",s.optString("marketRegime","MARKET READ").replace('_',' '),BLUE));c.addView(line("STYLE MODEL",s.optString("styleExecutionModel",signalStyle.equals("SCALP")?"SCALP MICROSTRUCTURE":"SWING HTF STRUCTURE").replace('_',' '),CYAN));c.addView(line("ENTRY MODEL",s.optString("entryModel","BOT MARKET JUDGMENT").replace('_',' '),YELLOW));c.addView(line("SL MODEL",s.optString("slModel","STRUCTURE INVALIDATION").replace('_',' '),RED));c.addView(line("TP MODEL",s.optString("tpModel","STRUCTURE TARGETS").replace('_',' '),GREEN));c.addView(line("BOT DECISION",s.optString("judgment","BOT MARKET JUDGMENT"),CYAN));c.addView(tv("Không chấm điểm • không score gate • không cooldown tín hiệu. "+historicalWr(market,signalStyle)+".",9,YELLOW,false));
        JSONArray why=s.optJSONArray("rationale");if(why!=null&&why.length()>0){TextView w=tv("LÝ DO VÀO LỆNH",11,TEXT,true);w.setPadding(0,dp(10),0,dp(2));c.addView(w);for(int i=0;i<why.length();i++)c.addView(tv("• "+why.optString(i),10,MUTED,false));}
        c.addView(tv("Phát: "+time(s.optString("issuedAt",""))+" • ID: "+id,9,MUTED,false));content.addView(c);
    };if(animate)swap(body);else body.run();updateAllPriceViews();}


    private void loadDashboardData(){
        loadSignalPartitions("SCALP");loadSignalPartitions("SWING");loadAllPerformance();loadSystemStatus();
        if(screen.equals("HOME"))main.post(()->renderHome(false));
    }

    private List<JSONObject> allSignals(){
        List<JSONObject> out=new ArrayList<>();
        for(String st:new String[]{"SCALP","SWING"})for(String m:new String[]{"FOREX","CRYPTO"}){JSONArray a=signalCache.get(m+":"+st);if(a==null)continue;for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s!=null)out.add(s);}}
        out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }

    private int activeCount(String st){int n=0;for(JSONObject s:allSignals())if((st==null||st.equals(s.optString("style","")))&&isDisplayLive(s,priceFor(s,s.optDouble("entry",0))))n++;return n;}
    private int pendingCount(){int n=0;for(JSONObject s:allSignals())if(!isDisplayLive(s,priceFor(s,s.optDouble("entry",0))))n++;return n;}
    private double totalNetR(){double r=0;for(JSONObject p:perfCache.values())r+=p.optDouble("netRResolved",0);return r;}
    private String combinedWr(){int tp=0,sl=0;for(JSONObject p:perfCache.values()){tp+=p.optInt("tp",0);sl+=p.optInt("sl",0);}int n=tp+sl;return n==0?"—":String.format(Locale.US,"%.0f%%",tp*100.0/n);}

    private View statTile(String icon,String title,String value,String sub,int color){LinearLayout c=card();LinearLayout h=row();h.addView(tv(icon,18,color,true));TextView t=tv(title,9,MUTED,true);LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(0,-2,1f);tp.setMargins(dp(8),0,0,0);h.addView(t,tp);c.addView(h);c.addView(tv(value,23,TEXT,true));c.addView(tv(sub,9,color,false));return c;}

    private void renderHome(boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText("CRYPTO EXECUTION INTELLIGENCE • QUALITY-FIRST");
        LinearLayout hero=card();LinearLayout h=row();LinearLayout l=column();l.addView(tv("EXECUTION INTELLIGENCE",15,TEXT,true));l.addView(tv("REALTIME CONTROL",21,CYAN,true));l.addView(tv("LIVE  •  LIMIT  •  STOP  •  STRUCTURE ASSESSMENT",9,MUTED,true));h.addView(l,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(cryptoProvider+" • "+cryptoState,stateColor(cryptoState)));hero.addView(h);content.addView(hero);
        LinearLayout r1=row();View a=statTile("◎","Tín hiệu đang chạy",String.valueOf(activeCount(null)),"LIVE • chờ "+pendingCount(),CYAN);View b=statTile("⚡","Scalp",String.valueOf(activeCount("SCALP")),"đang theo dõi",GREEN);LinearLayout.LayoutParams p1=new LinearLayout.LayoutParams(0,-2,1f);p1.setMargins(0,0,dp(3),0);LinearLayout.LayoutParams p2=new LinearLayout.LayoutParams(0,-2,1f);p2.setMargins(dp(3),0,0,0);r1.addView(a,p1);r1.addView(b,p2);content.addView(r1);
        LinearLayout r2=row();View d=statTile("▥","Swing",String.valueOf(activeCount("SWING")),"đang theo dõi",BLUE);View e=statTile("★","Tỷ lệ thắng",combinedWr(),"resolved TP/SL",GREEN);r2.addView(d,p1);r2.addView(e,p2);content.addView(r2);
        LinearLayout r3=row();View f=statTile("$","Net kết quả",String.format(Locale.US,"%+.1fR",totalNetR()),"lịch sử đã đóng",totalNetR()>=0?GREEN:RED);View g=statTile("✓","Hệ thống",systemState,"API + engine",stateColor(systemState));r3.addView(f,p1);r3.addView(g,p2);content.addView(r3);
        LinearLayout conn=card();conn.addView(tv("KẾT NỐI",12,TEXT,true));conn.addView(statusRow("Quote Feed • "+cryptoProvider,cryptoState));conn.addView(statusRow("Signal Engine",systemState));content.addView(conn);
        content.addView(tv("TÍN HIỆU ĐANG CHẠY",13,TEXT,true));List<JSONObject> rows=allSignals();int max=Math.min(4,rows.size());if(max==0){LinearLayout z=card();z.addView(tv("Đang đồng bộ tín hiệu…",10,MUTED,false));content.addView(z);}else for(int i=0;i<max;i++)content.addView(signalCard(rows.get(i)));
    };if(animate)swap(body);else body.run();updateAllPriceViews();}

    private void renderAlerts(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("THÔNG BÁO • TÍN HIỆU • TP/SL • HỆ THỐNG");content.addView(tv("THÔNG BÁO",16,TEXT,true));
        SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);String raw=p.getString("alert_history_v33","[]");try{JSONArray a=new JSONArray(raw);if(a.length()==0){LinearLayout z=card();z.addView(tv("Chưa có thông báo mới.",11,MUTED,true));z.addView(tv("SignalHub sẽ lưu các sự kiện MỚI / ACTIVE / TP / SL tại đây.",9,MUTED,false));content.addView(z);}for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i);if(x==null)continue;LinearLayout c=card();String title=x.optString("title","SignalHub"),bodyText=x.optString("body","");int color=title.contains("SL")?RED:title.contains("TP")||title.contains("BUY")?GREEN:title.contains("SELL")?RED:CYAN;c.addView(tv(title,12,color,true));c.addView(tv(bodyText,9,MUTED,false));long ts=x.optLong("ts",0);if(ts>0)c.addView(tv(relativeAge(Math.max(0,System.currentTimeMillis()-ts)),8,MUTED,false));content.addView(c);}}catch(Exception ex){LinearLayout z=card();z.addView(tv("Không đọc được lịch sử thông báo.",10,RED,true));content.addView(z);}
    };if(animate)swap(body);else body.run();}

    private void renderSettings(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CÀI ĐẶT • CRYPTO DATA • QUALITY ENGINE");content.addView(tv("CÀI ĐẶT",16,TEXT,true));
        LinearLayout notify=card();notify.addView(tv("🔔  THÔNG BÁO",12,TEXT,true));notify.addView(statusRow("Push Monitor",monitorStarted?"RUNNING":"OFFLINE"));notify.addView(statusRow("Quyền thông báo",notifyPermission()?"ONLINE":"OFFLINE"));if(!monitorStarted){Button b=button("BẬT PUSH MONITOR",true,v->ensureMonitor(true));notify.addView(b,new LinearLayout.LayoutParams(-1,dp(42)));}content.addView(notify);
        LinearLayout source=card();source.addView(tv("◉  NGUỒN DỮ LIỆU CRYPTO",12,TEXT,true));source.addView(statusRow(cryptoProvider,cryptoState));source.addView(line("Crypto symbols",String.valueOf(cryptoCount),TEXT));source.addView(line("Price authority","Provider-pinned per signal",CYAN));content.addView(source);
        LinearLayout sys=card();sys.addView(tv("⚙  HỆ THỐNG",12,TEXT,true));sys.addView(statusRow("Crypto Signal Engine",systemState));sys.addView(statusRow("API Connectivity",lastApiOkMs>0&&System.currentTimeMillis()-lastApiOkMs<15000?"ONLINE":"DEGRADED"));sys.addView(line("App version",APP_VERSION,BLUE));if(systemStatus!=null){sys.addView(line("Backend",systemStatus.optString("version","—"),TEXT));sys.addView(line("Mode",systemStatus.optString("mode","—"),CYAN));}content.addView(sys);
        LinearLayout ui=card();ui.addView(tv("✦  CRYPTO QUALITY ENGINE",12,TEXT,true));ui.addView(line("SCALP","5m / 15m / 1h",CYAN));ui.addView(line("SWING","1h / 4h / 1d",BLUE));ui.addView(line("Entry Routing","MARKET / LIMIT / STOP tự động",TEXT));ui.addView(line("Pending Trigger","Server monitor 1s • provider-pinned",GREEN));ui.addView(line("Quality","Structure + context + spread + liquidity + RR",CYAN));ui.addView(line("Coverage","Mục tiêu ≥1 setup đạt chuẩn mỗi style",GREEN));ui.addView(line("Forex","ĐÃ TẮT",MUTED));content.addView(ui);
    };if(animate)swap(body);else body.run();}

    private double pxForOrder(JSONObject s){return priceFor(s,s.optDouble("entry",0));}
    private boolean pendingTriggered(JSONObject s,double px){
        if(!"PENDING".equalsIgnoreCase(s.optString("status",""))||!(px>0))return false;
        String market=s.optString("market","FOREX").toUpperCase(Locale.US),sym=s.optString("symbol","");
        if(market.equals("FOREX")&&(!fxPrices.containsKey(sym)||!fxState.equals("LIVE")))return false;
        if(market.equals("CRYPTO")&&!cryptoPrices.containsKey(sym))return false;
        String type=s.optString("orderType","LIMIT").toUpperCase(Locale.US),side=sideVi(s.optString("side",""));double entry=s.optDouble("entry",0);if(!(entry>0))return false;
        if(type.equals("LIMIT"))return side.equals("BUY")?px<=entry:px>=entry;
        if(type.equals("STOP"))return side.equals("BUY")?px>=entry:px<=entry;
        return false;
    }
    private boolean isDisplayLive(JSONObject s,double px){return "OPEN".equalsIgnoreCase(s.optString("status",""));}
    private String orderDisplay(JSONObject s,double px){if(isDisplayLive(s,px))return "LIVE";String o=s.optString("orderType","MARKET").toUpperCase(Locale.US);return o.equals("LIMIT")?"LIMIT":o.equals("STOP")?"STOP":"MARKET";}
    private int orderColor(JSONObject s,double px){String o=orderDisplay(s,px);return o.equals("LIVE")?GREEN:o.equals("LIMIT")?YELLOW:o.equals("STOP")?BLUE:CYAN;}
    private double entryProgressPct(JSONObject s,double px){double e=s.optDouble("entry",0),start=s.optDouble("sourcePrice",s.optDouble("lastPrice",0));double initial=Math.abs(start-e);if(!(initial>0)){double sl=s.optDouble("sl",0);initial=Math.max(Math.abs(e-sl),1e-12);}double remaining=Math.abs(px-e);return Math.max(0,Math.min(100,(1.0-remaining/initial)*100.0));}
    private String pendingDistanceText(JSONObject s,double px){double e=s.optDouble("entry",0);double pct=entryProgressPct(s,px),remain=Math.abs(px-e);return s.optString("orderType","LIMIT").toUpperCase(Locale.US)+" • CHỜ ENTRY • "+String.format(Locale.US,"%.0f%% tiến độ • còn %s",pct,fmt(remain));}

    private String historicalWr(String market,String st){JSONObject p=perfCache.get(market+":"+st);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}
    private double targetR(JSONObject s){double rr=s.optDouble("targetRR",0);if(rr>0)return rr;double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp3",s.optDouble("tp",0));double risk=Math.abs(e-sl);return risk>0&&tp>0?Math.max(0.1,Math.abs(tp-e)/risk):1.0;}
    private double currentR(JSONObject s,double px){double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),risk=Math.abs(e-sl);if(!(risk>0)||!(px>0))return 0;String side=sideVi(s.optString("side",""));return (side.equals("SELL")?(e-px):(px-e))/risk;}
    private String tradeStatusText(JSONObject s,double px){if(!isDisplayLive(s,px))return pendingDistanceText(s,px);double r=currentR(s,px),rr=targetR(s);if(r<0){int pct=(int)Math.round(Math.min(100,Math.max(0,-r*100)));return String.format(Locale.US,"ÂM  %+.2fR  •  %d%% TỚI SL",r,pct);}int pct=(int)Math.round(Math.min(100,Math.max(0,r/Math.max(.1,rr)*100)));return String.format(Locale.US,"DƯƠNG  %+.2fR  •  %d%% TỚI TP3",r,pct);}
    private int tradeStatusColor(JSONObject s,double px){if(!isDisplayLive(s,px))return orderColor(s,px);return currentR(s,px)>=0?GREEN:RED;}

    private class EntryGauge extends View{
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double progress=0,current=0,entry=0;
        EntryGauge(){super(SignalHubActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setData(JSONObject s,double px){current=px;entry=s.optDouble("entry",0);progress=entryProgressPct(s,px);invalidate();}
        @Override protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight(),cy=h*.62f,barH=dp(11);p.setStyle(Paint.Style.FILL);p.setColor(Color.rgb(47,42,20));c.drawRoundRect(new RectF(dp(2),cy-barH/2,w-dp(2),cy+barH/2),barH/2,barH/2,p);float x=dp(2)+(float)((w-dp(4))*progress/100.0);p.setColor(YELLOW);p.setShadowLayer(dp(8),0,0,YELLOW);c.drawRoundRect(new RectF(dp(2),cy-barH/2,Math.max(dp(3),x),cy+barH/2),barH/2,barH/2,p);p.clearShadowLayer();p.setColor(TEXT);c.drawCircle(x,cy,dp(5),p);p.setTypeface(Typeface.create(Typeface.MONOSPACE,Typeface.BOLD));p.setTextSize(dp(9));p.setTextAlign(Paint.Align.LEFT);p.setColor(MUTED);c.drawText("NOW  "+fmt(current),dp(2),dp(13),p);p.setTextAlign(Paint.Align.RIGHT);p.setColor(YELLOW);c.drawText("ENTRY  "+fmt(entry),w-dp(2),dp(13),p);p.setTextAlign(Paint.Align.CENTER);p.setColor(YELLOW);c.drawText(String.format(Locale.US,"%.0f%% TỚI ENTRY",progress),w*.5f,h-dp(3),p);}
    }

    private class TradeGauge extends View{
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double r=0,target=1;
        TradeGauge(){super(SignalHubActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setData(double rr,double t){r=Double.isFinite(rr)?rr:0;target=t>0?t:1;invalidate();}
        @Override protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight(),cy=h*.58f,barH=dp(12),mid=w*.5f;p.setStyle(Paint.Style.FILL);p.setColor(Color.rgb(120,25,39));c.drawRoundRect(new RectF(dp(2),cy-barH/2,mid,cy+barH/2),barH/2,barH/2,p);p.setColor(Color.rgb(12,112,75));c.drawRoundRect(new RectF(mid,cy-barH/2,w-dp(2),cy+barH/2),barH/2,barH/2,p);p.setColor(Color.WHITE);p.setStrokeWidth(dp(2));c.drawLine(mid,cy-dp(13),mid,cy+dp(13),p);double clamped=r<0?Math.max(-1,Math.min(0,r)):Math.max(0,Math.min(target,r));float x=r<0?(float)(mid*(1+clamped)):(float)(mid+(w-mid)*(clamped/target));p.setColor(r>=0?GREEN:RED);p.setShadowLayer(dp(7),0,0,p.getColor());c.drawCircle(x,cy,dp(6),p);p.clearShadowLayer();p.setTextSize(dp(9));p.setTypeface(Typeface.create(Typeface.MONOSPACE,Typeface.BOLD));p.setColor(RED);p.setTextAlign(Paint.Align.LEFT);c.drawText("SL  -100%",dp(2),dp(12),p);p.setColor(TEXT);p.setTextAlign(Paint.Align.CENTER);c.drawText("ENTRY",mid,dp(12),p);p.setColor(GREEN);p.setTextAlign(Paint.Align.RIGHT);c.drawText("TP3  +100%",w-dp(2),dp(12),p);}
    }

    private void loadAllPerformance(){boolean changed=false;for(String st:new String[]{"SCALP","SWING"}){try{JSONObject p=new JSONObject(ApiClient.get("/v3/performance?market=CRYPTO&style="+st)).optJSONObject("performance");if(p!=null){String k="CRYPTO:"+st,old=perfCache.containsKey(k)?perfCache.get(k).toString():"";perfCache.put(k,p);if(!old.equals(p.toString()))changed=true;lastApiOkMs=System.currentTimeMillis();}}catch(Throwable ignored){}}if(changed&&screen.equals("STATS"))main.post(()->renderStats(false));}
    private void renderStats(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("PERFORMANCE STATISTICS • RESOLVED TRADES ONLY");content.addView(tv("THỐNG KÊ HIỆU SUẤT",16,TEXT,true));LinearLayout note=card();note.addView(tv("Win Rate chỉ tính lệnh đã đóng bằng TP/SL.",11,YELLOW,true));note.addView(tv("WATCH/PENDING không được tính thắng thua. Bot không dùng điểm số để quyết định entry.",9,MUTED,false));content.addView(note);for(String st:new String[]{"SCALP","SWING"})content.addView(perfCard("CRYPTO",st));};if(animate)swap(body);else body.run();}
    private View perfCard(String m,String st){LinearLayout c=card(),h=row();h.addView(tv(m+" • "+st,14,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(st,st.equals("SCALP")?CYAN:BLUE));c.addView(h);JSONObject p=perfCache.get(m+":"+st);if(p==null){c.addView(tv("Đang đồng bộ lịch sử…",10,MUTED,false));return c;}int tp=p.optInt("tp",0),sl=p.optInt("sl",0),n=p.optInt("resolved",tp+sl);c.addView(line("WIN RATE",p.optString("winRateLabel","—"),GREEN));c.addView(line("RESOLVED",String.valueOf(n),TEXT));c.addView(line("TP / SL",tp+" / "+sl,TEXT));c.addView(line("NET R",String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)),p.optDouble("netRResolved",0)>=0?GREEN:RED));c.addView(tv(p.optBoolean("sampleAdequate",false)?"Sample ≥30 • đủ để tham khảo tốt hơn":"Sample <30 • dữ liệu còn sơ bộ",9,p.optBoolean("sampleAdequate",false)?MUTED:YELLOW,false));return c;}

    private void renderSources(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CRYPTO DATA • FRESHNESS • CONNECTION HEALTH");content.addView(tv("NGUỒN DỮ LIỆU CRYPTO",16,TEXT,true));LinearLayout cr=card();cr.addView(tv("CRYPTO • "+cryptoProvider,13,TEXT,true));cr.addView(line("STATUS",cryptoState,stateColor(cryptoState)));cr.addView(line("SYMBOLS",String.valueOf(cryptoCount),TEXT));cr.addView(tv("Bybit ưu tiên; OKX/Binance fallback được gắn đúng nguồn. Entry/SL/TP lifecycle luôn dùng đúng executionPriceAuthority của từng tín hiệu.",9,MUTED,false));content.addView(cr);LinearLayout rule=card();rule.addView(tv("QUALITY + DATA INTEGRITY",12,CYAN,true));rule.addView(tv("SCALP và SWING tách riêng. Không giả win-rate dự đoán; chỉ thống kê TP/SL đã đóng. Quote lỗi không được giả thành LIVE.",10,MUTED,false));content.addView(rule);};if(animate)swap(body);else body.run();}

    private void loadSystemStatus(){try{JSONObject p=new JSONObject(ApiClient.get("/v3/status"));systemStatus=p;systemState=p.optBoolean("ok",false)?"RUNNING":"DEGRADED";lastApiOkMs=System.currentTimeMillis();if(screen.equals("SYSTEM"))main.post(()->renderSystem(false));}catch(Throwable e){systemState=lastApiOkMs==0?"OFFLINE":"DEGRADED";if(screen.equals("SYSTEM"))main.post(()->renderSystem(false));}}
    private void renderSystem(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CRYPTO SYSTEM STATUS • SIGNAL ENGINE • LIVE FEED");content.addView(tv("HỆ THỐNG CRYPTO",16,TEXT,true));LinearLayout c=card();c.addView(statusRow("Crypto Signal Engine",systemState));c.addView(statusRow("Quote Feed • "+cryptoProvider,cryptoState));c.addView(statusRow("Push Monitor",monitorStarted?"RUNNING":"OFFLINE"));c.addView(statusRow("API Connectivity",lastApiOkMs>0&&System.currentTimeMillis()-lastApiOkMs<15000?"ONLINE":"DEGRADED"));content.addView(c);LinearLayout meta=card();meta.addView(line("APP VERSION",APP_VERSION,BLUE));if(systemStatus!=null){meta.addView(line("BACKEND",systemStatus.optString("version","—"),TEXT));meta.addView(line("MODE",systemStatus.optString("mode","—"),CYAN));}meta.addView(line("LAST API SYNC",lastApiOkMs==0?"—":relativeAge(System.currentTimeMillis()-lastApiOkMs),MUTED));content.addView(meta);};if(animate)swap(body);else body.run();}
    private View statusRow(String name,String state){LinearLayout r=row();r.setPadding(0,dp(5),0,dp(5));r.addView(tv(name,11,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));r.addView(chip(state,stateColor(state)));return r;}

    private void connectForexStream(){
        closeForexStream();
        try{fxSocket=ApiClient.connectForexStream(new WebSocketListener(){
            @Override public void onOpen(WebSocket webSocket,Response response){fxStreamLastMs=System.currentTimeMillis();}
            @Override public void onMessage(WebSocket webSocket,String text){consumeForexStream(text);}
            @Override public void onFailure(WebSocket webSocket,Throwable t,Response response){fxStreamLastMs=0;main.post(()->updateConnectionViews());}
        });}catch(Throwable ignored){fxStreamLastMs=0;}
    }
    private void closeForexStream(){try{if(fxSocket!=null)fxSocket.close(1000,"pause");}catch(Throwable ignored){}fxSocket=null;}
    private void consumeForexStream(String text){
        try{JSONObject p=new JSONObject(text),packet=p;String type=p.optString("type","");if(type.equals("heartbeat")){return;}if(type.equals("signal_event")){JSONObject sig=p.optJSONObject("signal");if(sig!=null)applyRealtimeSignal(sig);return;}JSONArray a=packet.optJSONArray("quotes");if(a==null)return;Map<String,Double> next=new ConcurrentHashMap<>();for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null){double mid=q.optDouble("mid",0);if(mid>0)next.put(q.optString("symbol",""),mid);}}if(next.isEmpty())return;fxPrices.clear();fxPrices.putAll(next);fxCount=packet.optInt("count",a.length());long received=parseMs(packet.optString("receivedAt",""));fxQuoteAgeMs=received>0?Math.max(0,System.currentTimeMillis()-received):0;fxState=fxQuoteAgeMs<=1800?"LIVE":fxQuoteAgeMs<=4000?"DELAYED":"STALE";fxStreamLastMs=System.currentTimeMillis();fxLastOkMs=fxStreamLastMs;lastApiOkMs=fxStreamLastMs;main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("HOME"))renderHome(false);});}catch(Throwable ignored){}
    }


    private void applyRealtimeSignal(JSONObject sig){
        try{
            String market=sig.optString("market","FOREX").toUpperCase(Locale.US),st=sig.optString("style","SCALP").toUpperCase(Locale.US),key=market+":"+st,id=sig.optString("signalId",sig.optString("id",""));
            JSONArray old=signalCache.get(key),next=new JSONArray();boolean found=false,active="PENDING".equalsIgnoreCase(sig.optString("status",""))||"OPEN".equalsIgnoreCase(sig.optString("status",""));
            if(old!=null)for(int i=0;i<old.length();i++){JSONObject x=old.optJSONObject(i);if(x==null)continue;String xid=x.optString("signalId",x.optString("id",""));if(xid.equals(id)){found=true;if(active)next.put(sig);}else next.put(x);}
            if(!found&&active)next.put(sig);signalCache.put(key,next);
            if(selectedSignal!=null){String sid=selectedSignal.optString("signalId",selectedSignal.optString("id",""));if(sid.equals(id))selectedSignal=sig;}
            main.post(()->{if(screen.equals("SIGNALS")){if(detail&&selectedSignal!=null)renderDetail(selectedSignal,false);else renderSignals(false);}else if(screen.equals("HOME"))renderHome(false);});
        }catch(Throwable ignored){}
    }

    private void refreshForexLive(){if(!fxBusy.compareAndSet(false,true))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/forex/live"));JSONArray a=p.optJSONArray("quotes");fxPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null){double mid=q.optDouble("mid",0);if(mid>0)fxPrices.put(q.optString("symbol",""),mid);}}fxState=p.optString("state","OFFLINE");fxQuoteAgeMs=p.optLong("quoteAgeMs",-1);fxCount=p.optInt("count",a==null?0:a.length());fxLastOkMs=System.currentTimeMillis();lastApiOkMs=fxLastOkMs;}catch(Throwable e){long age=fxLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-fxLastOkMs;fxState=age<10000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{fxBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);});}});}
    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000"));JSONArray a=p.optJSONArray("tickers");cryptoPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null)cryptoPrices.put(q.optString("symbol",""),q);}cryptoProvider=p.optString("provider","CRYPTO");cryptoState=p.optBoolean("live",true)?"LIVE":"DELAYED";cryptoCount=p.optInt("count",a==null?0:a.length());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;}catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;cryptoState=age<10000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);});}});}

    private void updateConnectionViews(){int cc=stateColor(cryptoState);cryptoLive.setText(cryptoProvider+" • "+cryptoState);cryptoLive.setTextColor(cc);cryptoLive.setBackground(shape(Color.argb(28,Color.red(cc),Color.green(cc),Color.blue(cc)),9,cc));}
    private void updateAllPriceViews(){
        for(Map.Entry<String,TextView> e:priceViews.entrySet()){
            String id=e.getKey(),m=viewMarkets.getOrDefault(id,"CRYPTO");JSONObject s=findSignal(id);double fallback=s==null?0:s.optDouble("entry",0),px=s==null?fallback:priceFor(s,fallback);
            e.getValue().setText(fmt(px));e.getValue().setTextColor(TEXT);
            TextView sv=sourceViews.get(id);if(sv!=null){String state=cryptoState;sv.setText(sourceText(m));sv.setTextColor(stateColor(state));}
            if(s!=null){TextView pnl=pnlViews.get(id);if(pnl!=null){pnl.setText(tradeStatusText(s,px));pnl.setTextColor(tradeStatusColor(s,px));}TradeGauge g=gaugeViews.get(id);if(g!=null)g.setData(currentR(s,px),targetR(s));EntryGauge eg=entryGaugeViews.get(id);if(eg!=null)eg.setData(s,px);}
        }
    }
    private JSONObject findSignal(String id){if(selectedSignal!=null&&id.equals(selectedSignal.optString("signalId",selectedSignal.optString("id",""))))return selectedSignal;for(JSONArray a:signalCache.values())for(int i=0;i<a.length();i++){JSONObject s=a.optJSONObject(i);if(s!=null&&id.equals(s.optString("signalId",s.optString("id",""))))return s;}return null;}
    private double priceFor(JSONObject s,double fallback){String sym=s.optString("symbol",""),m=s.optString("market","FOREX");if(m.equals("CRYPTO")){String authority=s.optString("executionPriceAuthority",s.optString("provider","")).toUpperCase(Locale.US);if(!authority.isEmpty()&&!authority.equalsIgnoreCase(cryptoProvider))return s.optDouble("lastPrice",fallback);JSONObject q=cryptoPrices.get(sym);return q==null?fallback:q.optDouble("lastPrice",fallback);}Double p=fxPrices.get(sym);return p==null||p<=0?fallback:p;}
    private String sourceText(String market){if(market.equals("FOREX"))return "EXNESS MT5 • "+fxState+(fxStreamLastMs>0?" • STREAM":" REST")+(fxQuoteAgeMs>=0?" • "+String.format(Locale.US,"%.2fs",fxQuoteAgeMs/1000.0):"");long age=cryptoLastOkMs==0?-1:System.currentTimeMillis()-cryptoLastOkMs;return cryptoProvider+" • "+cryptoState+(age>=0?" • "+String.format(Locale.US,"%.1fs",age/1000.0):"");}

    private String lifecycleVi(JSONObject s){String x=s.optString("lifecycle","").toUpperCase(Locale.US);if(x.isEmpty()){String st=s.optString("status","");if(st.equals("PENDING"))x="PENDING_ENTRY";else if(st.equals("OPEN"))x="ACTIVE";else x=st;}return switch(x){case "PENDING_ENTRY"->"CHỜ ENTRY";case "ACTIVE"->s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP":"ĐANG CHẠY";case "TP1_HIT"->"TP1";case "TP2_HIT"->"TP2";case "TP3_HIT"->"TP ĐẠT";case "STOP_LOSS_HIT"->"SL";case "CANCELLED"->"ĐÃ HỦY";case "EXPIRED"->"HẾT HẠN";default->x.isEmpty()?"WATCHING":x;};}
    private int lifecycleColor(JSONObject s){String x=lifecycleVi(s);if(x.contains("SL")||x.contains("HỦY")||x.contains("HẾT"))return RED;if(x.contains("CHỜ"))return YELLOW;return GREEN;}
    private String sideVi(String s){String x=s.toUpperCase(Locale.US);return (x.equals("LONG")||x.equals("BUY"))?"BUY":(x.equals("SHORT")||x.equals("SELL"))?"SELL":x;}
        private int stateColor(String s){String x=String.valueOf(s).toUpperCase(Locale.US);if(x.equals("LIVE")||x.equals("ONLINE")||x.equals("RUNNING"))return GREEN;if(x.equals("DELAYED")||x.equals("DEGRADED")||x.equals("CONNECTING"))return YELLOW;return RED;}
    private boolean notifyPermission(){return Build.VERSION.SDK_INT<33||checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;}
    private void ensureMonitor(boolean ask){if(monitorStarted)return;if(!notifyPermission()){if(ask&&Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},REQ_NOTIFICATIONS);return;}try{Intent i=new Intent(this,MonitorService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);monitorStarted=true;}catch(Throwable ignored){}}
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] grantResults){super.onRequestPermissionsResult(requestCode,permissions,grantResults);if(requestCode==REQ_NOTIFICATIONS&&grantResults.length>0&&grantResults[0]==PackageManager.PERMISSION_GRANTED)ensureMonitor(false);}

    private String fmt(double v){if(!Double.isFinite(v)||v<=0)return"—";if(v>=1000)return String.format(Locale.US,"%.2f",v);if(v>=100)return String.format(Locale.US,"%.3f",v);if(v>=10)return String.format(Locale.US,"%.4f",v);if(v>=1)return String.format(Locale.US,"%.5f",v);return String.format(Locale.US,"%.7f",v);}
    private long parseMs(String iso){try{return Instant.parse(iso).toEpochMilli();}catch(Exception e){return 0;}}
    private String time(String iso){try{return DateTimeFormatter.ofPattern("dd/MM HH:mm:ss",Locale.US).withZone(ZoneId.systemDefault()).format(Instant.parse(iso));}catch(Exception e){return iso.isEmpty()?"—":iso;}}
    private String relativeAge(long ms){if(ms<1000)return"vừa xong";if(ms<60000)return(ms/1000)+"s trước";return(ms/60000)+"m trước";}
}
