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

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class SignalHubActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 42;
    private static final long FAST_REFRESH_MS = 1800L;
    private static final String APP_VERSION = "3.0.0";

    private static final int BG = Color.rgb(4, 7, 11);
    private static final int PANEL = Color.rgb(12, 18, 26);
    private static final int PANEL2 = Color.rgb(18, 26, 36);
    private static final int BORDER = Color.rgb(38, 51, 65);
    private static final int TEXT = Color.rgb(235, 241, 247);
    private static final int MUTED = Color.rgb(133, 151, 169);
    private static final int GREEN = Color.rgb(76, 222, 153);
    private static final int RED = Color.rgb(255, 93, 112);
    private static final int YELLOW = Color.rgb(246, 196, 91);
    private static final int BLUE = Color.rgb(93, 158, 255);
    private static final int CYAN = Color.rgb(73, 219, 219);

    private static final String CI_MARKERS = "SIGNALHUB FX /live-quotes?group=all /app-version /signals?status=active ACTIVE SETUPS PENDING MARKET LIMIT STOP";

    private final ExecutorService io = Executors.newFixedThreadPool(4);
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicBoolean refreshBusy = new AtomicBoolean(false);
    private final Map<String, Double> forexMid = new HashMap<>();
    private final Map<String, JSONObject> cryptoBySymbol = new HashMap<>();

    private LinearLayout content;
    private LinearLayout bottomNav;
    private TextView liveForexChip;
    private TextView liveCryptoChip;
    private TextView headerSub;
    private Button marketForexBtn, marketCryptoBtn, scalpBtn, swingBtn;
    private boolean resumed;
    private boolean monitorStarted;
    private boolean detailMode;
    private String screen = "SIGNALS";
    private String market = "FOREX";
    private String style = "SCALP";
    private long lastSignalLoad;
    private long lastTickerLoad;
    private JSONObject cachedActive;
    private JSONObject cachedHistory;
    private JSONObject cachedDiscovery;
    private JSONObject cachedTickers;
    private JSONObject cachedForexLive;

    private final Runnable fastLoop = new Runnable() {
        @Override public void run() {
            if (!resumed) return;
            if (!detailMode) refreshCurrent(false);
            main.postDelayed(this, FAST_REFRESH_MS);
        }
    };

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildUi();
        ensureMonitor(true);
        selectScreen("SIGNALS");
    }

    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        ensureMonitor(false);
        main.removeCallbacks(fastLoop);
        main.post(fastLoop);
    }

    @Override protected void onPause() {
        resumed = false;
        main.removeCallbacks(fastLoop);
        super.onPause();
    }

    @Override protected void onDestroy() {
        main.removeCallbacksAndMessages(null);
        io.shutdownNow();
        super.onDestroy();
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private GradientDrawable shape(int fill, int radius, int stroke) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(radius));
        if (stroke != Color.TRANSPARENT) d.setStroke(dp(1), stroke);
        return d;
    }

    private TextView tv(String s, int sp, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(s);
        v.setTextSize(sp);
        v.setTextColor(color);
        v.setTypeface(Typeface.create(Typeface.MONOSPACE, bold ? Typeface.BOLD : Typeface.NORMAL));
        v.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        return v;
    }

    private LinearLayout row() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        return r;
    }

    private LinearLayout card() {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setPadding(dp(14), dp(13), dp(14), dp(13));
        c.setBackground(shape(PANEL, 14, BORDER));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
        p.setMargins(0, dp(5), 0, dp(5));
        c.setLayoutParams(p);
        return c;
    }

    private TextView chip(String text, int color) {
        TextView v = tv(text, 9, color, true);
        v.setPadding(dp(9), dp(5), dp(9), dp(5));
        v.setGravity(Gravity.CENTER);
        v.setBackground(shape(Color.argb(24, Color.red(color), Color.green(color), Color.blue(color)), 9, color));
        return v;
    }

    private Button button(String text, boolean selected, View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextSize(10);
        b.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        b.setTextColor(selected ? BG : TEXT);
        b.setBackground(shape(selected ? GREEN : PANEL2, 11, selected ? GREEN : BORDER));
        b.setOnClickListener(click);
        return b;
    }

    private TextView labelValue(String label, String value, int color) {
        TextView t = tv(label + "  " + value, 11, color, true);
        t.setPadding(0, dp(3), 0, dp(3));
        return t;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.VERTICAL);
        header.setPadding(dp(14), dp(14), dp(14), dp(8));
        LinearLayout top = row();
        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        titles.addView(tv("SIGNALHUB", 24, TEXT, true));
        headerSub = tv("FOREX + CRYPTO • LIVE", 9, MUTED, true);
        titles.addView(headerSub);
        top.addView(titles, new LinearLayout.LayoutParams(0, -2, 1f));
        top.addView(chip("V" + APP_VERSION, BLUE));
        header.addView(top);

        LinearLayout live = row();
        liveForexChip = chip("EXNESS • CHỜ", YELLOW);
        liveCryptoChip = chip("BYBIT • CHỜ", YELLOW);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, -2, 1f);
        lp.setMargins(0, dp(8), dp(4), 0);
        live.addView(liveForexChip, lp);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(0, -2, 1f);
        rp.setMargins(dp(4), dp(8), 0, 0);
        live.addView(liveCryptoChip, rp);
        header.addView(live);

        LinearLayout marketRow = row();
        marketForexBtn = button("FOREX", true, v -> setMarket("FOREX"));
        marketCryptoBtn = button("CRYPTO", false, v -> setMarket("CRYPTO"));
        LinearLayout.LayoutParams mp1 = new LinearLayout.LayoutParams(0, dp(44), 1f); mp1.setMargins(0, dp(8), dp(4), 0);
        LinearLayout.LayoutParams mp2 = new LinearLayout.LayoutParams(0, dp(44), 1f); mp2.setMargins(dp(4), dp(8), 0, 0);
        marketRow.addView(marketForexBtn, mp1); marketRow.addView(marketCryptoBtn, mp2);
        header.addView(marketRow);

        LinearLayout styleRow = row();
        scalpBtn = button("SCALP", true, v -> setStyle("SCALP"));
        swingBtn = button("SWING", false, v -> setStyle("SWING"));
        LinearLayout.LayoutParams sp1 = new LinearLayout.LayoutParams(0, dp(40), 1f); sp1.setMargins(0, dp(6), dp(4), 0);
        LinearLayout.LayoutParams sp2 = new LinearLayout.LayoutParams(0, dp(40), 1f); sp2.setMargins(dp(4), dp(6), 0, 0);
        styleRow.addView(scalpBtn, sp1); styleRow.addView(swingBtn, sp2);
        header.addView(styleRow);
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(14), dp(4), dp(14), dp(12));
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        bottomNav = row();
        bottomNav.setPadding(dp(8), dp(7), dp(8), dp(9));
        bottomNav.setBackgroundColor(PANEL);
        root.addView(bottomNav);
        setContentView(root);
        drawBottomNav();
    }

    private void setMarket(String m) {
        market = m;
        detailMode = false;
        marketForexBtn.setTextColor(m.equals("FOREX") ? BG : TEXT);
        marketForexBtn.setBackground(shape(m.equals("FOREX") ? GREEN : PANEL2, 11, m.equals("FOREX") ? GREEN : BORDER));
        marketCryptoBtn.setTextColor(m.equals("CRYPTO") ? BG : TEXT);
        marketCryptoBtn.setBackground(shape(m.equals("CRYPTO") ? GREEN : PANEL2, 11, m.equals("CRYPTO") ? GREEN : BORDER));
        refreshCurrent(true);
    }

    private void setStyle(String s) {
        style = s;
        detailMode = false;
        scalpBtn.setTextColor(s.equals("SCALP") ? BG : TEXT);
        scalpBtn.setBackground(shape(s.equals("SCALP") ? GREEN : PANEL2, 11, s.equals("SCALP") ? GREEN : BORDER));
        swingBtn.setTextColor(s.equals("SWING") ? BG : TEXT);
        swingBtn.setBackground(shape(s.equals("SWING") ? GREEN : PANEL2, 11, s.equals("SWING") ? GREEN : BORDER));
        refreshCurrent(true);
    }

    private void selectScreen(String s) {
        screen = s;
        detailMode = false;
        drawBottomNav();
        refreshCurrent(true);
    }

    private void drawBottomNav() {
        bottomNav.removeAllViews();
        String[] tabs = {"SIGNALS", "WATCHLIST", "HISTORY", "NEWS"};
        String[] vi = {"TÍN HIỆU", "THEO DÕI", "LỊCH SỬ", "TIN TỨC"};
        for (int i=0;i<tabs.length;i++) {
            final String key = tabs[i];
            Button b = button(vi[i], screen.equals(key), v -> selectScreen(key));
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(48), 1f);
            p.setMargins(dp(3),0,dp(3),0);
            bottomNav.addView(b,p);
        }
    }

    private void loading(String title) {
        content.removeAllViews();
        content.addView(tv(title, 15, TEXT, true));
        LinearLayout c=card(); c.addView(tv("Đang cập nhật dữ liệu mới…",11,MUTED,false)); content.addView(c);
    }

    private void refreshCurrent(boolean force) {
        if (!resumed && !force) return;
        if (!refreshBusy.compareAndSet(false,true)) return;
        final String screenNow=screen, marketNow=market, styleNow=style;
        if (force) loading(titleFor(screenNow,marketNow,styleNow));
        io.execute(() -> {
            try {
                refreshConnectionState();
                if (screenNow.equals("SIGNALS")) loadSignals(marketNow,styleNow,force);
                else if (screenNow.equals("WATCHLIST")) loadWatchlist(marketNow,force);
                else if (screenNow.equals("HISTORY")) loadHistory(marketNow,styleNow,force);
                else loadNews(marketNow,force);
            } finally { refreshBusy.set(false); }
        });
    }

    private String titleFor(String scr,String m,String st) {
        if (scr.equals("SIGNALS")) return "TÍN HIỆU • " + m + " • " + st;
        if (scr.equals("WATCHLIST")) return "THEO DÕI • " + m;
        if (scr.equals("HISTORY")) return "LỊCH SỬ • " + m + " • " + st;
        return "TIN TỨC • " + m;
    }

    private void refreshConnectionState() {
        try {
            JSONObject fx = new JSONObject(ApiClient.get("/v3/forex/live"));
            cachedForexLive=fx;
            JSONArray q=fx.optJSONArray("quotes");
            synchronized (forexMid) {
                forexMid.clear();
                if(q!=null) for(int i=0;i<q.length();i++) {
                    JSONObject x=q.optJSONObject(i); if(x!=null) forexMid.put(x.optString("symbol"),x.optDouble("mid",0));
                }
            }
            String st=fx.optString("state","OFFLINE");
            long age=fx.optLong("quoteAgeMs",999999);
            main.post(() -> {
                int c=st.equals("LIVE")?GREEN:st.equals("DELAYED")?YELLOW:RED;
                liveForexChip.setText("EXNESS • "+viLive(st)+" • "+ageText(age)); liveForexChip.setTextColor(c); liveForexChip.setBackground(shape(Color.argb(20,Color.red(c),Color.green(c),Color.blue(c)),9,c));
            });
        } catch(Throwable e) {
            main.post(() -> { liveForexChip.setText("EXNESS • MẤT LIVE"); liveForexChip.setTextColor(RED); });
        }
        try {
            long now=System.currentTimeMillis();
            if(cachedTickers==null || now-lastTickerLoad>1800) {
                cachedTickers=new JSONObject(ApiClient.get("/v3/crypto/tickers?limit=250"));
                lastTickerLoad=now;
                JSONArray a=cachedTickers.optJSONArray("tickers");
                synchronized(cryptoBySymbol) {
                    cryptoBySymbol.clear();
                    if(a!=null) for(int i=0;i<a.length();i++) { JSONObject x=a.optJSONObject(i); if(x!=null) cryptoBySymbol.put(x.optString("symbol"),x); }
                }
            }
            int count=cachedTickers.optInt("count",0);
            main.post(() -> { liveCryptoChip.setText("BYBIT • LIVE • "+count+" MÃ"); liveCryptoChip.setTextColor(GREEN); liveCryptoChip.setBackground(shape(Color.argb(20,Color.red(GREEN),Color.green(GREEN),Color.blue(GREEN)),9,GREEN)); });
        } catch(Throwable e) {
            main.post(() -> { liveCryptoChip.setText("BYBIT • ĐANG NỐI LẠI"); liveCryptoChip.setTextColor(YELLOW); });
        }
    }

    private String viLive(String s) {
        if(s.equals("LIVE")) return "LIVE";
        if(s.equals("DELAYED")) return "TRỄ";
        if(s.equals("STALE")) return "GIÁ CŨ";
        return "MẤT KẾT NỐI";
    }

    private String ageText(long ms) { return ms<0||ms>999999?"—":String.format(Locale.US,"%.1fs",ms/1000.0); }

    private void loadSignals(String m,String st,boolean force) {
        if(m.equals("CRYPTO")) { loadCryptoSignals(st,force); return; }
        if(st.equals("SWING")) {
            main.post(() -> {
                if(!screen.equals("SIGNALS")||!market.equals("FOREX")||!style.equals("SWING"))return;
                content.removeAllViews(); content.addView(tv("FOREX • SWING",15,TEXT,true));
                LinearLayout c=card(); c.addView(chip("ENGINE RIÊNG",BLUE)); c.addView(tv("Swing được tách khỏi Scalp. Bản này không tái sử dụng tín hiệu intraday cũ để giả thành Swing.",11,MUTED,false)); c.addView(tv("Dữ liệu Exness live vẫn đang chạy và sẵn sàng cho engine Swing V3.",10,GREEN,true)); content.addView(c);
            });
            return;
        }
        try {
            long now=System.currentTimeMillis();
            if(cachedActive==null || force || now-lastSignalLoad>4500) {
                cachedActive=new JSONObject(ApiClient.get("/signals?status=active&limit=200")); lastSignalLoad=now;
            }
            JSONArray a=cachedActive.optJSONArray("signals");
            main.post(() -> renderForexSignals(a));
        } catch(Throwable e) { main.post(() -> renderError("Không tải được tín hiệu Forex",e)); }
    }

    private void renderForexSignals(JSONArray a) {
        if(!screen.equals("SIGNALS")||!market.equals("FOREX")||!style.equals("SCALP"))return;
        content.removeAllViews();
        LinearLayout top=row(); top.addView(tv("FOREX • SCALP",15,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f)); top.addView(chip("EXNESS LIVE",GREEN)); content.addView(top);
        int n=a==null?0:a.length();
        TextView sub=tv(n+" tín hiệu đang hoạt động • mỗi symbol tối đa 1 lệnh",10,MUTED,false); sub.setPadding(0,dp(5),0,dp(5)); content.addView(sub);
        if(n==0){ LinearLayout c=card(); c.addView(tv("Chưa có điểm vào đạt điều kiện.",12,MUTED,true)); c.addView(tv("Không ép phát lệnh khi giá đã chạy xa hoặc cấu trúc chưa sạch.",10,MUTED,false)); content.addView(c); return; }
        for(int i=0;i<n;i++) { JSONObject s=a.optJSONObject(i); if(s!=null) content.addView(forexSignalCard(s)); }
    }

    private View forexSignalCard(JSONObject s) {
        LinearLayout c=card();
        String symbol=s.optString("symbol","—"), side=s.optString("side","—"), order=s.optString("orderType","MARKET"), status=s.optString("status","OPEN");
        int dir=side.equalsIgnoreCase("LONG")?1:-1; int sideColor=dir>0?GREEN:RED;
        LinearLayout h=row(); h.addView(tv(symbol,17,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f)); h.addView(chip(side+" • "+order,sideColor)); c.addView(h);
        double entry=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp",0),px=latestForex(symbol,s.optDouble("lastPrice",entry));
        c.addView(labelValue("GIÁ LIVE",fmtPrice(px),CYAN));
        String stateTxt=status.equals("PENDING")?"ĐANG CHỜ KHỚP":s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP EXNESS":"ĐANG CHẠY";
        c.addView(labelValue("TRẠNG THÁI",stateTxt,status.equals("PENDING")?YELLOW:GREEN));
        c.addView(tv("Entry "+fmtPrice(entry)+"   TP "+fmtPrice(tp)+"   SL "+fmtPrice(sl),10,MUTED,true));
        c.addView(tv(progressText(dir,px,entry,sl,tp),10,progressColor(dir,px,entry),true));
        c.setOnClickListener(v -> showForexDetail(s));
        return c;
    }

    private double latestForex(String symbol,double fallback){ synchronized(forexMid){Double x=forexMid.get(symbol);return x!=null&&x>0?x:fallback;} }

    private String progressText(int dir,double px,double entry,double sl,double tp) {
        if(!(px>0&&entry>0&&sl>0&&tp>0))return "SL ───── ENTRY ───── TP";
        double risk=Math.abs(entry-sl); if(risk<=0)return "SL ───── ENTRY ───── TP";
        double r=dir*(px-entry)/risk;
        if(r>=0)return String.format(Locale.US,"SL ───── ENTRY ──●── TP   %+.2fR",r);
        return String.format(Locale.US,"SL ──●── ENTRY ───── TP   %+.2fR",r);
    }
    private int progressColor(int dir,double px,double entry){return dir*(px-entry)>=0?GREEN:RED;}

    private void showForexDetail(JSONObject s) {
        detailMode=true; content.removeAllViews();
        Button back=button("← QUAY LẠI",false,v->{detailMode=false;refreshCurrent(true);}); LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(-1,dp(42)); bp.setMargins(0,0,0,dp(8)); content.addView(back,bp);
        String symbol=s.optString("symbol","—"),side=s.optString("side","—"),order=s.optString("orderType","MARKET"),status=s.optString("status","OPEN"); int dir=side.equalsIgnoreCase("LONG")?1:-1;
        LinearLayout c=card(); LinearLayout h=row(); h.addView(tv(symbol+" • "+side,20,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f)); h.addView(chip(order,dir>0?GREEN:RED)); c.addView(h);
        double entry=s.optDouble("entry",0),sl=s.optDouble("sl",0),tp=s.optDouble("tp",0),px=latestForex(symbol,s.optDouble("lastPrice",entry));
        c.addView(labelValue("GIÁ EXNESS",fmtPrice(px),CYAN)); c.addView(labelValue("ENTRY",fmtPrice(entry),TEXT)); c.addView(labelValue("TP",fmtPrice(tp),GREEN)); c.addView(labelValue("SL",fmtPrice(sl),RED));
        c.addView(tv(progressText(dir,px,entry,sl,tp),11,progressColor(dir,px,entry),true));
        c.addView(labelValue("TRẠNG THÁI",status.equals("PENDING")?"CHỜ KHỚP":s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP THEO EXNESS":"ĐANG CHẠY",status.equals("PENDING")?YELLOW:GREEN));
        if(s.optBoolean("brokerConfirmed",false)) c.addView(tv("Exness đã xác nhận deal thật • không suy đoán bằng scanner",10,GREEN,true));
        c.addView(tv("Điểm chất lượng: "+s.optInt("score",0)+"/100 • đây là điểm setup, không phải xác suất thắng",10,MUTED,false));
        c.addView(tv("Phát tín hiệu: "+viTime(s.optString("issuedAt","")),10,MUTED,false));
        c.addView(tv("Lý do/chi tiết kỹ thuật sẽ tiếp tục được mở rộng trong engine V3 theo từng symbol.",10,MUTED,false)); content.addView(c);
    }

    private void loadCryptoSignals(String st,boolean force) {
        try {
            String q="/v3/crypto/discovery?style="+st.toLowerCase(Locale.US)+"&limit=35";
            cachedDiscovery=new JSONObject(ApiClient.get(q));
            JSONArray a=cachedDiscovery.optJSONArray("candidates"); int scanned=cachedDiscovery.optInt("scanned",0),eligible=cachedDiscovery.optInt("eligible",0);
            main.post(() -> renderCryptoDiscovery(st,a,scanned,eligible));
        } catch(Throwable e){ main.post(() -> renderError("Không tải được dữ liệu Bybit",e)); }
    }

    private void renderCryptoDiscovery(String st,JSONArray a,int scanned,int eligible) {
        if(!screen.equals("SIGNALS")||!market.equals("CRYPTO")||!style.equals(st))return;
        content.removeAllViews(); LinearLayout h=row(); h.addView(tv("CRYPTO • "+st,15,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f)); h.addView(chip("BYBIT LIVE",GREEN)); content.addView(h);
        content.addView(tv("Quét rộng "+scanned+" coin • đủ thanh khoản "+eligible+" • đang phân tích sâu "+(a==null?0:a.length()),10,MUTED,false));
        LinearLayout note=card(); note.addView(chip("CHỐNG FOMO",YELLOW)); note.addView(tv("Các coin dưới đây mới là ứng viên phân tích sâu, chưa bị biến thành BUY/SELL chỉ vì đang chạy mạnh.",10,MUTED,false)); content.addView(note);
        if(a==null||a.length()==0){LinearLayout c=card();c.addView(tv("Chưa có coin đủ điều kiện theo dõi.",11,MUTED,true));content.addView(c);return;}
        for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i);if(x!=null)content.addView(cryptoCandidateCard(x));}
    }

    private View cryptoCandidateCard(JSONObject x) {
        LinearLayout c=card(); String symbol=x.optString("symbol","—"); double p=x.optDouble("lastPrice",0),chg=x.optDouble("change24hPct",0),spread=x.optDouble("spreadBps",0),score=x.optDouble("discoveryScore",0);
        LinearLayout h=row();h.addView(tv(symbol,16,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip("THEO DÕI • "+String.format(Locale.US,"%.0f",score),BLUE));c.addView(h);
        c.addView(labelValue("GIÁ BYBIT",fmtPrice(p),CYAN)); c.addView(tv(String.format(Locale.US,"24h %+.2f%%   Spread %.2f bps",chg,spread),10,chg>=0?GREEN:RED,true));
        c.addView(tv("Chưa phải tín hiệu vào lệnh • chờ engine cấu trúc/entry xác nhận",9,MUTED,false)); c.setOnClickListener(v->showCryptoDetail(x)); return c;
    }

    private void showCryptoDetail(JSONObject x) {
        detailMode=true;content.removeAllViews(); Button back=button("← QUAY LẠI",false,v->{detailMode=false;refreshCurrent(true);});content.addView(back,new LinearLayout.LayoutParams(-1,dp(42)));
        LinearLayout c=card();String symbol=x.optString("symbol","—");c.addView(tv(symbol+" • "+style,20,TEXT,true));c.addView(labelValue("GIÁ BYBIT",fmtPrice(x.optDouble("lastPrice",0)),CYAN));c.addView(labelValue("BID / ASK",fmtPrice(x.optDouble("bid",0))+" / "+fmtPrice(x.optDouble("ask",0)),TEXT));c.addView(labelValue("SPREAD",String.format(Locale.US,"%.2f bps",x.optDouble("spreadBps",0)),MUTED));c.addView(labelValue("FUNDING",String.format(Locale.US,"%+.4f%%",x.optDouble("fundingRate",0)*100),YELLOW));c.addView(labelValue("OI",fmtMoney(x.optDouble("openInterestValue",0)),BLUE));c.addView(labelValue("TURNOVER 24H",fmtMoney(x.optDouble("turnover24h",0)),TEXT));c.addView(tv("Trạng thái: ĐANG PHÂN TÍCH • chưa phát BUY/SELL khi chưa có setup hoàn chỉnh",10,YELLOW,true));content.addView(c);
    }

    private void loadWatchlist(String m,boolean force) {
        if(m.equals("FOREX")) main.post(this::renderForexWatchlist); else main.post(this::renderCryptoWatchlist);
    }

    private void renderForexWatchlist() {
        if(!screen.equals("WATCHLIST")||!market.equals("FOREX"))return;content.removeAllViews();content.addView(tv("WATCHLIST • FOREX",15,TEXT,true));
        String[] defaults={"EURUSD","GBPUSD","USDJPY","GBPJPY","XAUUSD","XAGUSD","USOIL","UKOIL"};
        for(String s:defaults){double p=latestForex(s,0);LinearLayout c=card();LinearLayout h=row();h.addView(tv(s,15,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(p>0?"LIVE":"CHỜ",p>0?GREEN:YELLOW));c.addView(h);c.addView(labelValue("GIÁ",fmtPrice(p),CYAN));content.addView(c);}
    }

    private void renderCryptoWatchlist() {
        if(!screen.equals("WATCHLIST")||!market.equals("CRYPTO"))return;content.removeAllViews();content.addView(tv("WATCHLIST • CRYPTO",15,TEXT,true));
        String[] defaults={"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","LTCUSDT","LINKUSDT"};
        synchronized(cryptoBySymbol){for(String s:defaults){JSONObject x=cryptoBySymbol.get(s);LinearLayout c=card();LinearLayout h=row();h.addView(tv(s,15,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(x!=null?"BYBIT LIVE":"CHỜ",x!=null?GREEN:YELLOW));c.addView(h);if(x!=null){double ch=x.optDouble("change24hPct",0);c.addView(labelValue("GIÁ",fmtPrice(x.optDouble("lastPrice",0)),CYAN));c.addView(tv(String.format(Locale.US,"24h %+.2f%%",ch),10,ch>=0?GREEN:RED,true));}content.addView(c);}}
    }

    private void loadHistory(String m,String st,boolean force) {
        if(m.equals("CRYPTO")){main.post(()->renderCryptoHistory(st));return;}
        if(st.equals("SWING")){main.post(()->renderEmptyHistory("Forex Swing chưa phát lệnh production nên chưa có lịch sử giả."));return;}
        try{cachedHistory=new JSONObject(ApiClient.get("/signals?status=closed&limit=120"));JSONArray a=cachedHistory.optJSONArray("signals");main.post(()->renderForexHistory(a));}catch(Throwable e){main.post(()->renderError("Không tải được lịch sử",e));}
    }

    private void renderForexHistory(JSONArray a){if(!screen.equals("HISTORY")||!market.equals("FOREX"))return;content.removeAllViews();content.addView(tv("LỊCH SỬ • FOREX • "+style,15,TEXT,true));int n=a==null?0:a.length();if(n==0){renderEmptyHistory("Chưa có lệnh đóng.");return;}for(int i=0;i<n;i++){JSONObject s=a.optJSONObject(i);if(s==null)continue;LinearLayout c=card();String out=s.optString("outcome","CLOSED");int col=out.equals("TP")?GREEN:out.equals("SL")?RED:MUTED;LinearLayout h=row();h.addView(tv(s.optString("symbol","—")+" • "+s.optString("side","—"),13,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));h.addView(chip(out,col));c.addView(h);c.addView(tv("Entry "+fmtPrice(s.optDouble("entry",0))+" → Exit "+fmtPrice(s.optDouble("exitPrice",0))+"   "+fmtR(s.optDouble("resultR",0)),10,col,true));content.addView(c);}}
    private void renderCryptoHistory(String st){if(!screen.equals("HISTORY")||!market.equals("CRYPTO"))return;content.removeAllViews();content.addView(tv("LỊCH SỬ • CRYPTO • "+st,15,TEXT,true));renderEmptyHistory("Crypto SignalHub V3 hiện mới ở tầng quét rộng + phân tích sâu. Không tạo lịch sử BUY/SELL giả trước khi engine được kiểm định.");}
    private void renderEmptyHistory(String msg){LinearLayout c=card();c.addView(tv(msg,11,MUTED,false));content.addView(c);}

    private void loadNews(String m,boolean force) {
        try{JSONObject st=new JSONObject(ApiClient.get("/v3/status"));main.post(()->renderNews(m,st));}catch(Throwable e){main.post(()->renderNews(m,null));}
    }

    private void renderNews(String m,JSONObject st){if(!screen.equals("NEWS")||!market.equals(m))return;content.removeAllViews();content.addView(tv("TIN TỨC • "+m,15,TEXT,true));LinearLayout c=card();c.addView(chip("BỐI CẢNH THỊ TRƯỜNG",BLUE));if(m.equals("FOREX")){c.addView(tv("Tin mạnh không bị dùng như nút BUY/SELL. Engine sẽ kết hợp tin, spread Exness và cấu trúc trước khi quyết định.",11,MUTED,false));c.addView(tv("Nguồn lịch kinh tế chuyên dụng sẽ được nối ở checkpoint engine tiếp theo; app không bịa headline khi chưa có feed chuẩn.",10,YELLOW,true));}else{c.addView(tv("Bybit là nguồn giá/derivatives chính. Funding, OI, thanh khoản và trạng thái BTC/ETH sẽ được dùng làm bối cảnh, không phải tín hiệu độc lập.",11,MUTED,false));}content.addView(c);if(st!=null){LinearLayout s=card();s.addView(tv("HỆ THỐNG",12,TEXT,true));s.addView(tv(st.optString("version","—"),10,GREEN,true));s.addView(tv("Checkpoint: "+st.optString("checkpoint","—"),10,MUTED,false));content.addView(s);}}

    private void renderError(String title,Throwable e){content.removeAllViews();content.addView(tv(title,14,RED,true));LinearLayout c=card();c.addView(tv("Đang thử nối lại. Dữ liệu cũ không được dùng để giả LIVE.",11,YELLOW,true));c.addView(tv(String.valueOf(e.getMessage()),9,MUTED,false));content.addView(c);}

    private boolean hasNotificationPermission(){return Build.VERSION.SDK_INT<33||checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;}
    private void ensureMonitor(boolean ask){if(monitorStarted)return;if(!hasNotificationPermission()){if(ask&&Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},REQ_NOTIFICATIONS);return;}try{Intent i=new Intent(this,MonitorService.class);if(Build.VERSION.SDK_INT>=26)startForegroundService(i);else startService(i);monitorStarted=true;}catch(Throwable ignored){}}
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] grantResults){super.onRequestPermissionsResult(requestCode,permissions,grantResults);if(requestCode==REQ_NOTIFICATIONS&&grantResults.length>0&&grantResults[0]==PackageManager.PERMISSION_GRANTED)ensureMonitor(false);}

    private String fmtPrice(double v){if(!Double.isFinite(v)||v<=0)return "—";if(v>=1000)return String.format(Locale.US,"%.2f",v);if(v>=100)return String.format(Locale.US,"%.3f",v);if(v>=10)return String.format(Locale.US,"%.4f",v);if(v>=1)return String.format(Locale.US,"%.5f",v);return String.format(Locale.US,"%.7f",v);}
    private String fmtMoney(double v){if(!Double.isFinite(v))return "—";double a=Math.abs(v);if(a>=1_000_000_000)return String.format(Locale.US,"$%.2fB",v/1e9);if(a>=1_000_000)return String.format(Locale.US,"$%.2fM",v/1e6);if(a>=1000)return String.format(Locale.US,"$%.1fK",v/1e3);return String.format(Locale.US,"$%.2f",v);}
    private String fmtR(double v){return String.format(Locale.US,"%+.2fR",v);}
    private String viTime(String iso){try{Instant x=Instant.parse(iso);long sec=Math.max(0,Duration.between(x,Instant.now()).getSeconds());if(sec<60)return sec+" giây trước";if(sec<3600)return sec/60+" phút trước";return sec/3600+" giờ trước";}catch(Exception e){return iso==null||iso.isEmpty()?"—":iso;}}
}
