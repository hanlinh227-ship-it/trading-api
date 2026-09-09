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
import android.widget.ImageView;
import android.widget.EditText;
import android.widget.Toast;
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
    private static final String APP_VERSION="3.17.0";
    private static final long LIVE_REFRESH_MS=500L; // REST fallback; WebSocket is primary
    private static final long PAGE_REFRESH_MS=2500L;
    private static final long SCAN_MS=30000L;
    private static final int BG=Color.rgb(5,9,14),PANEL=Color.rgb(11,18,26),PANEL2=Color.rgb(16,27,38),BORDER=Color.rgb(31,48,63);
    private static final int TEXT=Color.rgb(246,249,252),MUTED=Color.rgb(139,160,177),GREEN=Color.rgb(57,217,138),RED=Color.rgb(255,91,110),YELLOW=Color.rgb(246,200,95),BLUE=Color.rgb(110,168,254),CYAN=Color.rgb(75,215,230);

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
    private final Map<String,JSONObject> watchCache=new ConcurrentHashMap<>();
    private final Map<String,Boolean> watchLoading=new ConcurrentHashMap<>();

    private LinearLayout content,bottom,signalControls;
    private TextView fxLive,cryptoLive,subtitle;
    private Button scalpBtn,swingBtn;
    private boolean resumed,detail,monitorStarted;
    private String screen="HOME",style="SCALP",filter="CRYPTO";
    private JSONObject selectedSignal,systemStatus;
    private volatile String fxState="OFFLINE",cryptoState="OFFLINE",cryptoProvider="CRYPTO",systemState="CONNECTING";
    private volatile long fxQuoteAgeMs=-1,fxLastOkMs=0,cryptoLastOkMs=0,lastApiOkMs=0,lastUiPageRefreshMs=0;
    private volatile int fxCount=0,cryptoCount=0;
    private volatile long fxStreamLastMs=0,watchLastBulkMs=0,watchLastRenderMs=0;
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
    private TextView tv(String s,int sp,int color,boolean bold){TextView v=new TextView(this);v.setText(s);v.setTextSize(sp);v.setTextColor(color);v.setTypeface(Typeface.create(Typeface.DEFAULT,bold?Typeface.BOLD:Typeface.NORMAL));v.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);return v;}
    private LinearLayout row(){LinearLayout r=new LinearLayout(this);r.setOrientation(LinearLayout.HORIZONTAL);r.setGravity(Gravity.CENTER_VERTICAL);return r;}
    private LinearLayout column(){LinearLayout c=new LinearLayout(this);c.setOrientation(LinearLayout.VERTICAL);return c;}
    private LinearLayout card(){LinearLayout c=column();c.setPadding(dp(16),dp(15),dp(16),dp(15));c.setBackground(shape(PANEL,18,BORDER));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(7),0,dp(7));c.setLayoutParams(p);return c;}
    private TextView chip(String s,int color){TextView v=tv(s,9,color,true);v.setPadding(dp(9),dp(5),dp(9),dp(5));v.setGravity(Gravity.CENTER);v.setBackground(shape(Color.argb(24,Color.red(color),Color.green(color),Color.blue(color)),10,Color.argb(150,Color.red(color),Color.green(color),Color.blue(color))));return v;}
    private Button button(String s,boolean selected,View.OnClickListener l){Button b=new Button(this);b.setText(s);b.setAllCaps(false);b.setTextSize(11);b.setTypeface(Typeface.DEFAULT,Typeface.BOLD);b.setTextColor(selected?BG:TEXT);b.setPadding(dp(10),0,dp(10),0);b.setMinHeight(0);b.setMinimumHeight(0);b.setStateListAnimator(null);b.setBackground(shape(selected?CYAN:PANEL2,14,selected?CYAN:BORDER));b.setOnClickListener(l);pressFeedback(b);return b;}
    private void pressFeedback(View v){v.setOnTouchListener((x,e)->{if(e.getAction()==MotionEvent.ACTION_DOWN)x.animate().scaleX(.985f).scaleY(.985f).alpha(.82f).setDuration(55).start();else if(e.getAction()==MotionEvent.ACTION_UP||e.getAction()==MotionEvent.ACTION_CANCEL)x.animate().scaleX(1f).scaleY(1f).alpha(1f).setDuration(90).start();return false;});}
    private TextView line(String k,String v,int c){TextView t=tv(k+"  "+v,11,c,true);t.setPadding(0,dp(3),0,dp(3));return t;}

    private View sectionHeader(String title,String sub,int color){LinearLayout c=column();c.setPadding(0,dp(8),0,dp(3));TextView t=tv(title,15,TEXT,true);c.addView(t);if(sub!=null&&!sub.isEmpty())c.addView(tv(sub,9,color,false));return c;}
    private View levelBox(String label,String value,int color){LinearLayout c=column();c.setPadding(dp(10),dp(9),dp(10),dp(9));c.setBackground(shape(PANEL2,12,Color.TRANSPARENT));c.addView(tv(label,8,MUTED,true));TextView v=tv(value,12,color,true);v.setPadding(0,dp(2),0,0);c.addView(v);return c;}
    private View miniStat(String label,String value,String sub,int color){LinearLayout c=column();c.setPadding(dp(13),dp(12),dp(13),dp(12));c.setBackground(shape(PANEL,16,BORDER));c.addView(tv(label,9,MUTED,true));c.addView(tv(value,22,TEXT,true));c.addView(tv(sub,9,color,false));return c;}
    private View navItem(String key,String label,int icon){boolean on=screen.equals(key);LinearLayout c=column();c.setGravity(Gravity.CENTER);c.setPadding(dp(3),dp(5),dp(3),dp(4));c.setBackground(shape(on?PANEL2:PANEL,14,on?BORDER:Color.TRANSPARENT));ImageView im=new ImageView(this);im.setImageResource(icon);im.setColorFilter(on?CYAN:MUTED);im.setContentDescription(label);c.addView(im,new LinearLayout.LayoutParams(dp(21),dp(21)));TextView t=tv(label,9,on?TEXT:MUTED,on);t.setGravity(Gravity.CENTER);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(20));lp.setMargins(0,dp(3),0,0);c.addView(t,lp);c.setClickable(true);c.setOnClickListener(v->selectScreen(key));pressFeedback(c);return c;}
    private void openSignalDetail(JSONObject s){style=s.optString("style",style).toUpperCase(Locale.US);screen="SIGNALS";detail=true;selectedSignal=s;signalControls.setVisibility(View.VISIBLE);paintControls();drawBottom();renderDetail(s,true);}
    private View homeSignalRow(JSONObject s){LinearLayout c=card();String sym=s.optString("symbol","—"),st=s.optString("style","SCALP"),side=sideVi(s.optString("side",""));double e=s.optDouble("entry",0),px=priceFor(s,e);int col=side.equals("BUY")?GREEN:RED;LinearLayout h=row();LinearLayout names=column();names.addView(tv(sym,16,TEXT,true));names.addView(tv(st+" • "+orderDisplay(s,px),9,MUTED,true));h.addView(names,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));c.addView(h);LinearLayout q=row();q.setPadding(0,dp(9),0,0);LinearLayout left=column();left.addView(tv("GIÁ HIỆN TẠI",8,MUTED,true));left.addView(tv(fmt(px),16,TEXT,true));q.addView(left,new LinearLayout.LayoutParams(0,-2,1f));LinearLayout right=column();right.setGravity(Gravity.END);right.addView(tv("ENTRY",8,MUTED,true));TextView ev=tv(fmt(e),12,orderColor(s,px),true);ev.setGravity(Gravity.END);right.addView(ev);q.addView(right,new LinearLayout.LayoutParams(0,-2,1f));c.addView(q);TextView state=tv(tradeStatusText(s,px),9,tradeStatusColor(s,px),true);state.setPadding(0,dp(7),0,0);c.addView(state);c.setClickable(true);c.setOnClickListener(v->openSignalDetail(s));pressFeedback(c);return c;}

    private void buildUi(){
        LinearLayout root=column();root.setBackgroundColor(BG);
        LinearLayout head=column();head.setPadding(dp(16),dp(12),dp(16),dp(8));
        LinearLayout top=row();ImageView brand=new ImageView(this);brand.setImageResource(R.drawable.ic_signalhub);brand.setColorFilter(CYAN);brand.setContentDescription("SignalHub");LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(dp(32),dp(32));bp.setMargins(0,0,dp(10),0);top.addView(brand,bp);
        LinearLayout titles=column();TextView logo=tv("SignalHub",20,TEXT,true);subtitle=tv("CRYPTO • 2 SCALP + 2 SWING",9,MUTED,false);titles.addView(logo);titles.addView(subtitle);top.addView(titles,new LinearLayout.LayoutParams(0,-2,1f));cryptoLive=chip("ĐANG KẾT NỐI",YELLOW);top.addView(cryptoLive);head.addView(top);
        signalControls=column();LinearLayout segment=row();segment.setPadding(dp(4),dp(4),dp(4),dp(4));segment.setBackground(shape(PANEL,16,BORDER));scalpBtn=button("SCALP",true,v->setStyle("SCALP"));swingBtn=button("SWING",false,v->setStyle("SWING"));LinearLayout.LayoutParams s1=new LinearLayout.LayoutParams(0,dp(40),1f);s1.setMargins(0,0,dp(3),0);LinearLayout.LayoutParams s2=new LinearLayout.LayoutParams(0,dp(40),1f);s2.setMargins(dp(3),0,0,0);segment.addView(scalpBtn,s1);segment.addView(swingBtn,s2);LinearLayout.LayoutParams sg=new LinearLayout.LayoutParams(-1,-2);sg.setMargins(0,dp(10),0,0);signalControls.addView(segment,sg);head.addView(signalControls);root.addView(head);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setVerticalScrollBarEnabled(false);content=column();content.setPadding(dp(16),dp(3),dp(16),dp(24));scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1f));bottom=row();bottom.setPadding(dp(7),dp(6),dp(7),dp(8));bottom.setBackgroundColor(PANEL);root.addView(bottom,new LinearLayout.LayoutParams(-1,dp(66)));setContentView(root);drawBottom();signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);
    }

    private void setStyle(String s){if(style.equals(s))return;style=s;detail=false;selectedSignal=null;paintControls();renderSignals(true);kickScanIfDue();refreshPage(true);}
    private void setFilter(String f){if(filter.equals(f))return;filter=f;detail=false;selectedSignal=null;paintControls();renderSignals(true);kickScanIfDue();refreshPage(false);}
    private void paintControls(){setBtn(scalpBtn,style.equals("SCALP"));setBtn(swingBtn,style.equals("SWING"));for(Map.Entry<String,Button> e:filterButtons.entrySet())setBtn(e.getValue(),e.getKey().equals(filter));}
    private void setBtn(Button b,boolean on){b.setTextColor(on?BG:TEXT);b.setBackground(shape(on?CYAN:PANEL2,14,on?CYAN:BORDER));}
    private void selectScreen(String s){
        if(screen.equals(s)&&!detail)return;
        screen=s;detail=false;selectedSignal=null;
        signalControls.setVisibility(screen.equals("SIGNALS")?View.VISIBLE:View.GONE);
        drawBottom();renderCurrent(true);refreshPage(true);
    }
    private void drawBottom(){
        bottom.removeAllViews();String[] keys={"HOME","SIGNALS","WATCH","STATS","SETTINGS"},names={"Trang chủ","Tín hiệu","Theo dõi","Thống kê","Cài đặt"};int[] icons={R.drawable.ic_home,R.drawable.ic_signal,R.drawable.ic_watchlist,R.drawable.ic_stats,R.drawable.ic_settings};
        for(int i=0;i<keys.length;i++){View v=navItem(keys[i],names[i],icons[i]);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(52),1f);p.setMargins(dp(2),0,dp(2),0);bottom.addView(v,p);}
    }
    private void swap(Runnable r){content.animate().cancel();content.setAlpha(.78f);r.run();content.animate().alpha(1f).setDuration(120).start();}

    private void renderCurrent(boolean animate){
        if(screen.equals("HOME"))renderHome(animate);
        else if(screen.equals("SIGNALS"))renderSignals(animate);
        else if(screen.equals("WATCH"))renderWatchlist(animate);
        else if(screen.equals("STATS"))renderStats(animate);
        else renderSettings(animate);
    }

    private void refreshPage(boolean force){
        if(!resumed&&!force)return;
        if(screen.equals("WATCH")){refreshWatchlistAnalyses(force);return;}
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

    private String performanceSummary(){JSONObject p=perfCache.get("CRYPTO:"+style);if(p==null)return "Chưa đủ dữ liệu đóng lệnh";int n=p.optInt("resolved",0);return n==0?"Chưa có lệnh đóng":("WR "+p.optString("winRateLabel","—")+" • "+n+" mẫu • Net "+String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)));}
    private View signalCard(JSONObject s){
        LinearLayout c=card();String sym=s.optString("symbol","—"),side=sideVi(s.optString("side","—")),signalStyle=s.optString("style",style),id=s.optString("signalId",s.optString("id",sym+":"+signalStyle));int col=side.equals("BUY")?GREEN:RED;double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp3=s.optDouble("tp3",s.optDouble("tp",0)),px=priceFor(s,e);
        LinearLayout h=row();ImageView coin=new ImageView(this);coin.setImageResource(R.drawable.ic_crypto_coin);coin.setColorFilter(CYAN);coin.setContentDescription(sym);LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(dp(28),dp(28));cp.setMargins(0,0,dp(10),0);h.addView(coin,cp);LinearLayout names=column();names.addView(tv(sym,18,TEXT,true));names.addView(tv(signalStyle+" • "+s.optString("executionPriceAuthority",s.optString("provider","CRYPTO")),9,MUTED,false));h.addView(names,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));LinearLayout.LayoutParams op=new LinearLayout.LayoutParams(-2,-2);op.setMargins(dp(6),0,0,0);h.addView(chip(orderDisplay(s,px),orderColor(s,px)),op);c.addView(h);
        LinearLayout priceRow=row();priceRow.setPadding(0,dp(10),0,0);LinearLayout priceCol=column();priceCol.addView(tv("GIÁ HIỆN TẠI",8,MUTED,true));TextView pv=tv(fmt(px),22,TEXT,true);priceCol.addView(pv);priceRow.addView(priceCol,new LinearLayout.LayoutParams(0,-2,1f));TextView pnl=tv(tradeStatusText(s,px),10,tradeStatusColor(s,px),true);pnl.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);priceRow.addView(pnl,new LinearLayout.LayoutParams(0,-2,1f));c.addView(priceRow);priceViews.put(id,pv);viewMarkets.put(id,"CRYPTO");pnlViews.put(id,pnl);
        if(isDisplayLive(s,px)){TradeGauge g=new TradeGauge();g.setData(currentR(s,px),targetR(s));LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-1,dp(55));gp.setMargins(0,dp(5),0,0);c.addView(g,gp);gaugeViews.put(id,g);}else{EntryGauge g=new EntryGauge();g.setData(s,px);LinearLayout.LayoutParams gp=new LinearLayout.LayoutParams(-1,dp(59));gp.setMargins(0,dp(5),0,0);c.addView(g,gp);entryGaugeViews.put(id,g);}
        LinearLayout lv=row();LinearLayout.LayoutParams a=new LinearLayout.LayoutParams(0,-2,1f);a.setMargins(0,dp(6),dp(3),0);LinearLayout.LayoutParams b=new LinearLayout.LayoutParams(0,-2,1f);b.setMargins(dp(3),dp(6),dp(3),0);LinearLayout.LayoutParams d=new LinearLayout.LayoutParams(0,-2,1f);d.setMargins(dp(3),dp(6),0,0);lv.addView(levelBox("ENTRY",fmt(e),TEXT),a);lv.addView(levelBox("SL",fmt(sl),RED),b);lv.addView(levelBox("TP3",fmt(tp3),GREEN),d);c.addView(lv);
        TextView foot=tv(shortReason(s)+"  •  Chạm để xem phân tích",9,MUTED,false);foot.setPadding(0,dp(9),0,0);c.addView(foot);pressFeedback(c);c.setClickable(true);c.setOnClickListener(v->openSignalDetail(s));return c;
    }
    private View simpleLevel(String k,String v,int color){LinearLayout x=column();x.setPadding(dp(2),dp(7),dp(2),0);x.addView(tv(k,8,MUTED,true));x.addView(tv(v,11,color,true));return x;}
    private String shortReason(JSONObject s){String r=s.optString("marketRegime","MARKET READ").replace('_',' '),cluster=s.optString("riskCluster","");return cluster.isEmpty()?r:(r+" • "+cluster);}
    private TextView metric(String k,String v,int color){TextView t=tv(String.format(Locale.US,"%-6s %s",k,v),11,color,true);t.setPadding(0,dp(3),0,dp(3));return t;}
    private String historicalWr(String market){return historicalWr(market,style);}

    private void renderSignals(boolean animate){
        if(detail&&selectedSignal!=null){renderDetail(selectedSignal,animate);return;}Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText(style+" • CRYPTO REALTIME");
            List<JSONObject> rows=collectSignals(),liveRows=new ArrayList<>(),waitRows=new ArrayList<>();for(JSONObject x:rows){double px=priceFor(x,x.optDouble("entry",0));if(isDisplayLive(x,px))liveRows.add(x);else waitRows.add(x);}
            LinearLayout top=row();LinearLayout title=column();title.addView(tv(style,20,TEXT,true));title.addView(tv(style.equals("SCALP")?"Giao dịch ngắn • 5m / 15m / 1h":"Giữ theo cấu trúc • 1h / 4h / 1D",9,MUTED,false));top.addView(title,new LinearLayout.LayoutParams(0,-2,1f));top.addView(chip(cryptoState,stateColor(cryptoState)));content.addView(top);
            LinearLayout stats=row();View live=miniStat("LIVE",String.valueOf(liveRows.size()),"đã khớp",GREEN),wait=miniStat("CHỜ ENTRY",String.valueOf(waitRows.size()),"limit / stop",YELLOW);LinearLayout.LayoutParams p1=new LinearLayout.LayoutParams(0,-2,1f);p1.setMargins(0,dp(8),dp(4),dp(7));LinearLayout.LayoutParams p2=new LinearLayout.LayoutParams(0,-2,1f);p2.setMargins(dp(4),dp(8),0,dp(7));stats.addView(live,p1);stats.addView(wait,p2);content.addView(stats);content.addView(tv(performanceSummary(),9,MUTED,false));
            addCryptoSignalGroup("ĐANG CHẠY",liveRows,GREEN);addCryptoSignalGroup("CHỜ KHỚP ENTRY",waitRows,YELLOW);
        };if(animate)swap(body);else body.run();updateAllPriceViews();
    }
    private void addCryptoSignalGroup(String name,List<JSONObject> rows,int color){
        LinearLayout h=row();h.addView(tv(name,13,color,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(String.valueOf(rows.size()),color));content.addView(h);
        if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Chưa có setup phù hợp lúc này.",10,MUTED,true));content.addView(z);return;}
        for(JSONObject x:rows)content.addView(signalCard(x));
    }

    private void renderDetail(JSONObject s,boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText("CHI TIẾT TÍN HIỆU");
        Button back=button("‹  Quay lại tín hiệu",false,v->{detail=false;selectedSignal=null;renderSignals(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(44)));
        String market=s.optString("market","CRYPTO"),signalStyle=s.optString("style",style),side=sideVi(s.optString("side","—")),id=s.optString("signalId",s.optString("id","detail"));int col=side.equals("BUY")?GREEN:RED;double px=priceFor(s,s.optDouble("entry",0));
        LinearLayout trade=card();LinearLayout h=row();LinearLayout names=column();names.addView(tv(s.optString("symbol","—"),24,TEXT,true));names.addView(tv(signalStyle+" • "+orderDisplay(s,px)+" • "+lifecycleVi(s),10,orderColor(s,px),true));h.addView(names,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(side,col));trade.addView(h);
        TextView pv=tv(fmt(px),30,TEXT,true);pv.setPadding(0,dp(12),0,0);trade.addView(pv);priceViews.put(id,pv);viewMarkets.put(id,market);TextView sv=tv(sourceText(market),9,stateColor(cryptoState),true);trade.addView(sv);sourceViews.put(id,sv);TextView pnl=tv(tradeStatusText(s,px),13,tradeStatusColor(s,px),true);pnl.setPadding(0,dp(10),0,dp(2));trade.addView(pnl);pnlViews.put(id,pnl);
        if(isDisplayLive(s,px)){TradeGauge gauge=new TradeGauge();gauge.setData(currentR(s,px),targetR(s));trade.addView(gauge,new LinearLayout.LayoutParams(-1,dp(70)));gaugeViews.put(id,gauge);}else{EntryGauge eg=new EntryGauge();eg.setData(s,px);trade.addView(eg,new LinearLayout.LayoutParams(-1,dp(72)));entryGaugeViews.put(id,eg);}
        LinearLayout l1=row();LinearLayout.LayoutParams x1=new LinearLayout.LayoutParams(0,-2,1f);x1.setMargins(0,dp(5),dp(3),0);LinearLayout.LayoutParams x2=new LinearLayout.LayoutParams(0,-2,1f);x2.setMargins(dp(3),dp(5),dp(3),0);LinearLayout.LayoutParams x3=new LinearLayout.LayoutParams(0,-2,1f);x3.setMargins(dp(3),dp(5),0,0);l1.addView(levelBox("ENTRY",fmt(s.optDouble("entry",0)),TEXT),x1);l1.addView(levelBox("SL",fmt(s.optDouble("sl",0)),RED),x2);l1.addView(levelBox("TP3",fmt(s.optDouble("tp3",s.optDouble("tp",0))),GREEN),x3);trade.addView(l1);LinearLayout l2=row();LinearLayout.LayoutParams y1=new LinearLayout.LayoutParams(0,-2,1f);y1.setMargins(0,dp(6),dp(3),0);LinearLayout.LayoutParams y2=new LinearLayout.LayoutParams(0,-2,1f);y2.setMargins(dp(3),dp(6),dp(3),0);LinearLayout.LayoutParams y3=new LinearLayout.LayoutParams(0,-2,1f);y3.setMargins(dp(3),dp(6),0,0);l2.addView(levelBox("TP1",fmt(s.optDouble("tp1",0)),GREEN),y1);l2.addView(levelBox("TP2",fmt(s.optDouble("tp2",0)),GREEN),y2);l2.addView(levelBox("RR","1 : "+String.format(Locale.US,"%.2f",targetR(s)),CYAN),y3);trade.addView(l2);content.addView(trade);
        content.addView(sectionHeader("Phân tích thị trường","Cấu trúc và logic của chính setup này",CYAN));LinearLayout analysis=card();analysis.addView(line("REGIME",s.optString("marketRegime","MARKET READ").replace('_',' '),BLUE));analysis.addView(line("STYLE",s.optString("styleExecutionModel",signalStyle.equals("SCALP")?"SCALP MICROSTRUCTURE":"SWING HTF STRUCTURE").replace('_',' '),CYAN));analysis.addView(line("ENTRY",s.optString("entryModel","BOT MARKET JUDGMENT").replace('_',' '),YELLOW));analysis.addView(line("STOP",s.optString("slModel","STRUCTURE INVALIDATION").replace('_',' '),RED));analysis.addView(line("TARGET",s.optString("tpModel","STRUCTURE TARGETS").replace('_',' '),GREEN));content.addView(analysis);
        JSONArray why=s.optJSONArray("rationale");if(why!=null&&why.length()>0){content.addView(sectionHeader("Vì sao có tín hiệu","Các điều kiện chính đã được engine xác nhận",MUTED));LinearLayout reasons=card();for(int i=0;i<why.length();i++){TextView r=tv("• "+why.optString(i),10,MUTED,false);r.setPadding(0,dp(3),0,dp(3));reasons.addView(r);}content.addView(reasons);}
        LinearLayout meta=card();meta.addView(tv("WR chỉ dựa trên lệnh đã đóng • không phải xác suất thắng dự đoán.",9,YELLOW,false));meta.addView(tv("Phát "+time(s.optString("issuedAt",""))+" • "+historicalWr(market,signalStyle),9,MUTED,false));content.addView(meta);
    };if(animate)swap(body);else body.run();updateAllPriceViews();}

    private void loadDashboardData(){
        loadSignalPartitions("SCALP");loadSignalPartitions("SWING");loadAllPerformance();loadSystemStatus();
        if(screen.equals("HOME"))main.post(()->renderHome(false));
    }

    private List<JSONObject> allSignals(){
        List<JSONObject> out=new ArrayList<>();for(String st:new String[]{"SCALP","SWING"}){JSONArray arr=signalCache.get("CRYPTO:"+st);if(arr==null)continue;for(int i=0;i<arr.length();i++){JSONObject s=arr.optJSONObject(i);if(s!=null)out.add(s);}}out.sort(Comparator.comparingLong((JSONObject x)->parseMs(x.optString("issuedAt",""))).reversed());return out;
    }

    private int activeCount(String st){int n=0;for(JSONObject s:allSignals())if((st==null||st.equals(s.optString("style","")))&&isDisplayLive(s,priceFor(s,s.optDouble("entry",0))))n++;return n;}
    private int pendingCount(){int n=0;for(JSONObject s:allSignals())if(!isDisplayLive(s,priceFor(s,s.optDouble("entry",0))))n++;return n;}
    private double totalNetR(){double r=0;for(JSONObject p:perfCache.values())r+=p.optDouble("netRResolved",0);return r;}
    private String combinedWr(){int tp=0,sl=0;for(JSONObject p:perfCache.values()){tp+=p.optInt("tp",0);sl+=p.optInt("sl",0);}int n=tp+sl;return n==0?"—":String.format(Locale.US,"%.0f%%",tp*100.0/n);}

    private View statTile(String icon,String title,String value,String sub,int color){return miniStat(title,value,sub,color);}

    private void renderHome(boolean animate){Runnable body=()->{content.removeAllViews();priceViews.clear();sourceViews.clear();viewMarkets.clear();gaugeViews.clear();entryGaugeViews.clear();pnlViews.clear();subtitle.setText("CRYPTO • 2 SCALP + 2 SWING");
        LinearLayout hero=card();LinearLayout h=row();LinearLayout left=column();left.addView(tv("SIGNALHUB CRYPTO",10,CYAN,true));left.addView(tv(systemState.equals("RUNNING")?"Sẵn sàng theo dõi":"Đang kết nối lại",22,TEXT,true));left.addView(tv(cryptoProvider+" • "+cryptoState,9,stateColor(cryptoState),true));h.addView(left,new LinearLayout.LayoutParams(0,-2,1f));ImageView mark=new ImageView(this);mark.setImageResource(R.drawable.ic_signalhub);mark.setColorFilter(CYAN);mark.setContentDescription("SignalHub");h.addView(mark,new LinearLayout.LayoutParams(dp(42),dp(42)));hero.addView(h);TextView promise=tv("Bảng tham khảo luôn ưu tiên 2 SCALP + 2 SWING. Watchlist phân tích riêng coin bạn chọn.",9,MUTED,false);promise.setPadding(0,dp(10),0,0);hero.addView(promise);content.addView(hero);
        LinearLayout counts=row();View sc=miniStat("SCALP",String.valueOf(countStyle("SCALP")),"mục tiêu 2 active",CYAN),sw=miniStat("SWING",String.valueOf(countStyle("SWING")),"mục tiêu 2 active",BLUE);LinearLayout.LayoutParams p1=new LinearLayout.LayoutParams(0,-2,1f);p1.setMargins(0,0,dp(4),0);LinearLayout.LayoutParams p2=new LinearLayout.LayoutParams(0,-2,1f);p2.setMargins(dp(4),0,0,0);counts.addView(sc,p1);counts.addView(sw,p2);content.addView(counts);
        JSONObject ps=perfCache.get("CRYPTO:SCALP"),pw=perfCache.get("CRYPTO:SWING");content.addView(sectionHeader("Hiệu suất đã đóng","Không dùng WR dự đoán",MUTED));LinearLayout evidence=card();evidence.addView(evidenceLine("SCALP",ps));evidence.addView(evidenceLine("SWING",pw));content.addView(evidence);
        List<JSONObject> rows=allSignals();content.addView(sectionHeader("4 tín hiệu tham khảo","Chạm vào từng coin để xem Entry / SL / TP và phân tích",MUTED));if(rows.isEmpty()){LinearLayout z=card();z.addView(tv("Đang đồng bộ tín hiệu từ server…",10,MUTED,false));content.addView(z);}else{for(int i=0;i<Math.min(4,rows.size());i++)content.addView(homeSignalRow(rows.get(i)));}
    };if(animate)swap(body);else body.run();updateAllPriceViews();}
    private int countStyle(String st){int n=0;for(JSONObject s:allSignals())if(st.equals(s.optString("style","")))n++;return n;}
    private View evidenceLine(String st,JSONObject p){LinearLayout r=row();r.setPadding(0,dp(7),0,dp(7));r.addView(tv(st,11,st.equals("SCALP")?CYAN:BLUE,true),new LinearLayout.LayoutParams(0,-2,1f));if(p==null){r.addView(tv("đang tải",9,MUTED,false));return r;}int n=p.optInt("resolved",0);String x=n==0?"chưa có mẫu":p.optString("winRateLabel","—")+" • "+n+" mẫu • "+String.format(Locale.US,"%+.1fR",p.optDouble("netRResolved",0));r.addView(tv(x,10,n>=30?TEXT:YELLOW,true));return r;}

    private void renderAlerts(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("THÔNG BÁO • TÍN HIỆU • TP/SL • HỆ THỐNG");content.addView(tv("THÔNG BÁO",16,TEXT,true));
        SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);String raw=p.getString("alert_history_v33","[]");try{JSONArray a=new JSONArray(raw);if(a.length()==0){LinearLayout z=card();z.addView(tv("Chưa có thông báo mới.",11,MUTED,true));z.addView(tv("SignalHub sẽ lưu các sự kiện MỚI / ACTIVE / TP / SL tại đây.",9,MUTED,false));content.addView(z);}for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i);if(x==null)continue;LinearLayout c=card();String title=x.optString("title","SignalHub"),bodyText=x.optString("body","");int color=title.contains("SL")?RED:title.contains("TP")||title.contains("BUY")?GREEN:title.contains("SELL")?RED:CYAN;c.addView(tv(title,12,color,true));c.addView(tv(bodyText,9,MUTED,false));long ts=x.optLong("ts",0);if(ts>0)c.addView(tv(relativeAge(Math.max(0,System.currentTimeMillis()-ts)),8,MUTED,false));content.addView(c);}}catch(Exception ex){LinearLayout z=card();z.addView(tv("Không đọc được lịch sử thông báo.",10,RED,true));content.addView(z);}
    };if(animate)swap(body);else body.run();}

    private void renderSettings(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("CÀI ĐẶT • CRYPTO ONLY");content.addView(tv("Cài đặt",20,TEXT,true));content.addView(tv("Chỉ giữ các trạng thái quan trọng để dễ kiểm tra.",9,MUTED,false));
        LinearLayout notify=card();notify.addView(tv("Thông báo & nền",13,TEXT,true));notify.addView(statusRow("Theo dõi nền",monitorStarted?"RUNNING":"OFFLINE"));notify.addView(statusRow("Quyền thông báo",notifyPermission()?"ONLINE":"OFFLINE"));if(!monitorStarted){Button b=button("Bật theo dõi",true,v->ensureMonitor(true));LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(-1,dp(44));bp.setMargins(0,dp(7),0,0);notify.addView(b,bp);}content.addView(notify);
        LinearLayout data=card();data.addView(tv("Dữ liệu thị trường",13,TEXT,true));data.addView(statusRow(cryptoProvider,cryptoState));data.addView(line("Pending","Server theo dõi liên tục",GREEN));data.addView(line("Execution","Đúng provider của signal",CYAN));content.addView(data);
        LinearLayout engine=card();engine.addView(tv("Signal engine",13,TEXT,true));engine.addView(line("SCALP","5m • 15m • 1h",CYAN));engine.addView(line("SWING","1h • 4h • 1D",BLUE));engine.addView(line("Danh mục","2 SCALP + 2 SWING",GREEN));engine.addView(line("App",APP_VERSION,TEXT));if(systemStatus!=null)engine.addView(line("Backend",systemStatus.optString("version","—"),MUTED));content.addView(engine);
    };if(animate)swap(body);else body.run();}

    private double pxForOrder(JSONObject s){return priceFor(s,s.optDouble("entry",0));}
    private boolean pendingTriggered(JSONObject s,double px){
        if(!"PENDING".equalsIgnoreCase(s.optString("status",""))||!(px>0))return false;
        String market=s.optString("market","CRYPTO").toUpperCase(Locale.US),sym=s.optString("symbol","");
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

    private String historicalWr(String market,String st){JSONObject p=perfCache.get("CRYPTO:"+st);if(p==null)return"WR: chưa đủ dữ liệu";return "WR lịch sử "+p.optString("winRateLabel","—");}
    private double targetR(JSONObject s){double rr=s.optDouble("targetRR",0);if(rr>0)return rr;double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp3",s.optDouble("tp",0));double risk=Math.abs(e-sl);return risk>0&&tp>0?Math.max(0.1,Math.abs(tp-e)/risk):1.0;}
    private double currentR(JSONObject s,double px){double e=s.optDouble("entry",0),sl=s.optDouble("sl",0),risk=Math.abs(e-sl);if(!(risk>0)||!(px>0))return 0;String side=sideVi(s.optString("side",""));return (side.equals("SELL")?(e-px):(px-e))/risk;}
    private String tradeStatusText(JSONObject s,double px){if(!isDisplayLive(s,px))return pendingDistanceText(s,px);double r=currentR(s,px),rr=targetR(s);if(r<0){int pct=(int)Math.round(Math.min(100,Math.max(0,-r*100)));return String.format(Locale.US,"ÂM  %+.2fR  •  %d%% TỚI SL",r,pct);}int pct=(int)Math.round(Math.min(100,Math.max(0,r/Math.max(.1,rr)*100)));return String.format(Locale.US,"DƯƠNG  %+.2fR  •  %d%% TỚI TP3",r,pct);}
    private int tradeStatusColor(JSONObject s,double px){if(!isDisplayLive(s,px))return orderColor(s,px);return currentR(s,px)>=0?GREEN:RED;}

    private class EntryGauge extends View{
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double progress=0,current=0,entry=0;
        EntryGauge(){super(SignalHubActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setData(JSONObject s,double px){current=px;entry=s.optDouble("entry",0);progress=entryProgressPct(s,px);invalidate();}
        @Override protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight(),cy=h*.62f,barH=dp(11);p.setStyle(Paint.Style.FILL);p.setColor(Color.rgb(47,42,20));c.drawRoundRect(new RectF(dp(2),cy-barH/2,w-dp(2),cy+barH/2),barH/2,barH/2,p);float x=dp(2)+(float)((w-dp(4))*progress/100.0);p.setColor(YELLOW);p.setShadowLayer(dp(8),0,0,YELLOW);c.drawRoundRect(new RectF(dp(2),cy-barH/2,Math.max(dp(3),x),cy+barH/2),barH/2,barH/2,p);p.clearShadowLayer();p.setColor(TEXT);c.drawCircle(x,cy,dp(5),p);p.setTypeface(Typeface.DEFAULT_BOLD);p.setTextSize(dp(9));p.setTextAlign(Paint.Align.LEFT);p.setColor(MUTED);c.drawText("NOW  "+fmt(current),dp(2),dp(13),p);p.setTextAlign(Paint.Align.RIGHT);p.setColor(YELLOW);c.drawText("ENTRY  "+fmt(entry),w-dp(2),dp(13),p);p.setTextAlign(Paint.Align.CENTER);p.setColor(YELLOW);c.drawText(String.format(Locale.US,"%.0f%% TỚI ENTRY",progress),w*.5f,h-dp(3),p);}
    }

    private class TradeGauge extends View{
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);private double r=0,target=1;
        TradeGauge(){super(SignalHubActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void setData(double rr,double t){r=Double.isFinite(rr)?rr:0;target=t>0?t:1;invalidate();}
        @Override protected void onDraw(Canvas c){super.onDraw(c);float w=getWidth(),h=getHeight(),cy=h*.58f,barH=dp(12),mid=w*.5f;p.setStyle(Paint.Style.FILL);p.setColor(Color.rgb(120,25,39));c.drawRoundRect(new RectF(dp(2),cy-barH/2,mid,cy+barH/2),barH/2,barH/2,p);p.setColor(Color.rgb(12,112,75));c.drawRoundRect(new RectF(mid,cy-barH/2,w-dp(2),cy+barH/2),barH/2,barH/2,p);p.setColor(Color.WHITE);p.setStrokeWidth(dp(2));c.drawLine(mid,cy-dp(13),mid,cy+dp(13),p);double clamped=r<0?Math.max(-1,Math.min(0,r)):Math.max(0,Math.min(target,r));float x=r<0?(float)(mid*(1+clamped)):(float)(mid+(w-mid)*(clamped/target));p.setColor(r>=0?GREEN:RED);p.setShadowLayer(dp(7),0,0,p.getColor());c.drawCircle(x,cy,dp(6),p);p.clearShadowLayer();p.setTextSize(dp(9));p.setTypeface(Typeface.DEFAULT_BOLD);p.setColor(RED);p.setTextAlign(Paint.Align.LEFT);c.drawText("SL  -100%",dp(2),dp(12),p);p.setColor(TEXT);p.setTextAlign(Paint.Align.CENTER);c.drawText("ENTRY",mid,dp(12),p);p.setColor(GREEN);p.setTextAlign(Paint.Align.RIGHT);c.drawText("TP3  +100%",w-dp(2),dp(12),p);}
    }


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
    private int watchStateColor(String state){String x=state==null?"":state.toUpperCase(Locale.US);if(x.equals("ACTIVE_SIGNAL"))return GREEN;if(x.equals("TRADEABLE_NOW"))return CYAN;if(x.equals("CONDITIONAL_WAIT")||x.equals("DATA_UNAVAILABLE"))return YELLOW;return RED;}
    private String watchStateVi(String state){String x=state==null?"":state.toUpperCase(Locale.US);return switch(x){case "ACTIVE_SIGNAL"->"CÓ LỆNH";case "TRADEABLE_NOW"->"SETUP ĐẸP";case "CONDITIONAL_WAIT"->"CHỜ ĐIỀU KIỆN";case "DATA_UNAVAILABLE"->"DỮ LIỆU TẠM THIẾU";case "NO_TRADE"->"NO TRADE";default->"ĐANG PHÂN TÍCH";};}
    private View watchStyleBlock(String styleName,JSONObject x){LinearLayout c=column();c.setPadding(0,dp(9),0,dp(4));String state=x==null?"LOADING":x.optString("state","NO_TRADE"),side=sideVi(x==null?"":x.optString("side","")),order=x==null?"":x.optString("orderType","");LinearLayout h=row();h.addView(tv(styleName,11,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(watchStateVi(state),watchStateColor(state)));c.addView(h);if(x==null){TextView z=tv("Đang đọc cấu trúc…",9,MUTED,false);z.setPadding(0,dp(5),0,0);c.addView(z);return c;}String regime=x.optString("marketRegime","");if(!side.isEmpty()&&!order.isEmpty()){TextView d=tv(side+" • "+order+(regime.isEmpty()?"":" • "+regime),10,side.equals("BUY")?GREEN:RED,true);d.setPadding(0,dp(5),0,0);c.addView(d);}else if(!regime.isEmpty()){TextView d=tv(regime,9,MUTED,true);d.setPadding(0,dp(5),0,0);c.addView(d);}double e=x.optDouble("entry",0),sl=x.optDouble("sl",0),tp=x.optDouble("tp3",0);if(e>0&&sl>0&&tp>0)c.addView(tv("Entry "+fmt(e)+"  •  SL "+fmt(sl)+"  •  TP3 "+fmt(tp),9,TEXT,true));String story=x.optString("marketStory","");if(!story.isEmpty()&&(state.equals("TRADEABLE_NOW")||state.equals("ACTIVE_SIGNAL")||state.equals("CONDITIONAL_WAIT")))c.addView(tv(story,9,MUTED,false));JSONArray failed=x.optJSONArray("failedChecks");if(state.equals("NO_TRADE")&&failed!=null&&failed.length()>0)c.addView(tv("Chưa đạt: "+failed.optString(0),8,YELLOW,false));return c;}
    private void renderWatchlist(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("WATCHLIST • PHÂN TÍCH RIÊNG");content.addView(tv("Theo dõi coin",20,TEXT,true));content.addView(tv("Không chiếm 4 slot tín hiệu chính",9,MUTED,false));LinearLayout add=row();EditText input=new EditText(this);input.setHint("Nhập BTC, ETH, XRP…");input.setHintTextColor(MUTED);input.setTextColor(TEXT);input.setTextSize(12);input.setSingleLine(true);input.setPadding(dp(13),0,dp(13),0);input.setBackground(shape(PANEL2,14,BORDER));Button addBtn=button("Thêm",true,v->{String x=input.getText().toString();input.setText("");addWatch(x);});LinearLayout.LayoutParams ip=new LinearLayout.LayoutParams(0,dp(46),1f);ip.setMargins(0,dp(12),dp(5),dp(8));add.addView(input,ip);LinearLayout.LayoutParams ab=new LinearLayout.LayoutParams(dp(78),dp(46));ab.setMargins(dp(5),dp(12),0,dp(8));add.addView(addBtn,ab);content.addView(add);List<String> symbols=watchSymbols();if(symbols.isEmpty()){LinearLayout z=card();z.addView(tv("Chưa có coin nào trong Watchlist.",11,TEXT,true));z.addView(tv("Nhập mã phía trên để xem phân tích SCALP và SWING riêng.",9,MUTED,false));content.addView(z);return;}for(String sym:symbols){JSONObject root=watchCache.get(sym),ticker=root==null?null:root.optJSONObject("ticker"),live=cryptoPrices.get(sym);double px=live!=null?live.optDouble("lastPrice",0):(ticker==null?0:ticker.optDouble("lastPrice",0));LinearLayout c=card();LinearLayout h=row();LinearLayout n=column();n.addView(tv(sym.replace("USDT"," / USDT"),16,TEXT,true));String provider=live!=null?cryptoProvider:(ticker==null?"—":ticker.optString("provider","—"));n.addView(tv(provider+" • "+cryptoState,8,stateColor(cryptoState),false));h.addView(n,new LinearLayout.LayoutParams(0,-2,1f));TextView price=tv(fmt(px),15,CYAN,true);h.addView(price);Button rm=button("×",false,v->removeWatch(sym));LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(dp(40),dp(36));rp.setMargins(dp(8),0,0,0);h.addView(rm,rp);c.addView(h);JSONObject styles=root==null?null:root.optJSONObject("styles");c.addView(watchStyleBlock("SCALP  •  5m / 15m / 1h",styles==null?null:styles.optJSONObject("SCALP")));c.addView(watchStyleBlock("SWING  •  1h / 4h / 1D",styles==null?null:styles.optJSONObject("SWING")));Button refresh=button(Boolean.TRUE.equals(watchLoading.get(sym))?"Đang phân tích…":"Phân tích lại",false,v->refreshWatchSymbol(sym,true));LinearLayout.LayoutParams fp=new LinearLayout.LayoutParams(-1,dp(42));fp.setMargins(0,dp(7),0,0);c.addView(refresh,fp);content.addView(c);} };if(animate)swap(body);else body.run();}

    private void loadAllPerformance(){boolean changed=false;for(String st:new String[]{"SCALP","SWING"}){try{JSONObject p=new JSONObject(ApiClient.get("/v3/performance?market=CRYPTO&style="+st)).optJSONObject("performance");if(p!=null){String k="CRYPTO:"+st,old=perfCache.containsKey(k)?perfCache.get(k).toString():"";perfCache.put(k,p);if(!old.equals(p.toString()))changed=true;lastApiOkMs=System.currentTimeMillis();}}catch(Throwable ignored){}}if(changed&&screen.equals("STATS"))main.post(()->renderStats(false));}
    private void renderStats(boolean animate){Runnable body=()->{content.removeAllViews();subtitle.setText("THỐNG KÊ • CHỈ LỆNH ĐÃ ĐÓNG");content.addView(tv("Hiệu suất",20,TEXT,true));content.addView(tv("Win rate chỉ là kết quả lịch sử, không phải xác suất thắng của lệnh kế tiếp.",9,MUTED,false));for(String st:new String[]{"SCALP","SWING"})content.addView(perfCard("CRYPTO",st));};if(animate)swap(body);else body.run();}
    private View perfCard(String m,String st){LinearLayout c=card(),h=row();LinearLayout names=column();names.addView(tv(st,16,TEXT,true));names.addView(tv(st.equals("SCALP")?"5m / 15m / 1h":"1h / 4h / 1D",9,MUTED,false));h.addView(names,new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(st,st.equals("SCALP")?CYAN:BLUE));c.addView(h);JSONObject p=perfCache.get(m+":"+st);if(p==null){c.addView(tv("Đang đồng bộ lịch sử…",10,MUTED,false));return c;}int tp=p.optInt("tp",0),sl=p.optInt("sl",0),n=p.optInt("resolved",tp+sl);LinearLayout big=row();big.setPadding(0,dp(12),0,dp(5));LinearLayout wr=column();wr.addView(tv("WIN RATE",8,MUTED,true));wr.addView(tv(p.optString("winRateLabel","—"),26,TEXT,true));big.addView(wr,new LinearLayout.LayoutParams(0,-2,1f));LinearLayout nr=column();nr.setGravity(Gravity.END);nr.addView(tv("NET R",8,MUTED,true));TextView rv=tv(String.format(Locale.US,"%+.2fR",p.optDouble("netRResolved",0)),18,p.optDouble("netRResolved",0)>=0?GREEN:RED,true);rv.setGravity(Gravity.END);nr.addView(rv);big.addView(nr,new LinearLayout.LayoutParams(0,-2,1f));c.addView(big);c.addView(line("MẪU",String.valueOf(n),TEXT));c.addView(line("TP / SL",tp+" / "+sl,TEXT));c.addView(tv(n>=30?"Sample ≥30 • đáng tham khảo hơn":"Sample <30 • dữ liệu còn sơ bộ",9,n>=30?MUTED:YELLOW,false));return c;}

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
    private void refreshCryptoLive(){if(!cryptoBusy.compareAndSet(false,true))return;io.execute(()->{try{JSONObject p=new JSONObject(ApiClient.getLive("/v3/crypto/tickers?limit=1000"));JSONArray a=p.optJSONArray("tickers");cryptoPrices.clear();if(a!=null)for(int i=0;i<a.length();i++){JSONObject q=a.optJSONObject(i);if(q!=null)cryptoPrices.put(q.optString("symbol",""),q);}cryptoProvider=p.optString("provider","CRYPTO");cryptoState=p.optBoolean("live",true)?"LIVE":"DELAYED";cryptoCount=p.optInt("count",a==null?0:a.length());cryptoLastOkMs=System.currentTimeMillis();lastApiOkMs=cryptoLastOkMs;}catch(Throwable e){long age=cryptoLastOkMs==0?Long.MAX_VALUE:System.currentTimeMillis()-cryptoLastOkMs;cryptoState=age<10000?"DELAYED":age<30000?"STALE":"OFFLINE";}finally{cryptoBusy.set(false);main.post(()->{updateConnectionViews();updateAllPriceViews();if(screen.equals("SOURCES"))renderSources(false);if(screen.equals("SYSTEM"))renderSystem(false);if(screen.equals("WATCH")&&System.currentTimeMillis()-watchLastRenderMs>2000){watchLastRenderMs=System.currentTimeMillis();renderWatchlist(false);}});}});}

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
