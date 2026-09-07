package com.hanlinh.signalhub;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
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
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class SignalHubActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 42;
    private static final long LIVE_REFRESH_MS = 5000L;

    private static final int BG = Color.rgb(5, 8, 13);
    private static final int PANEL = Color.rgb(13, 19, 28);
    private static final int PANEL2 = Color.rgb(19, 27, 39);
    private static final int BORDER = Color.rgb(38, 52, 68);
    private static final int TEXT = Color.rgb(232, 239, 246);
    private static final int MUTED = Color.rgb(137, 157, 177);
    private static final int ACCENT = Color.rgb(87, 225, 190);
    private static final int BLUE = Color.rgb(91, 157, 255);
    private static final int GREEN = Color.rgb(83, 217, 140);
    private static final int RED = Color.rgb(255, 103, 120);
    private static final int YELLOW = Color.rgb(244, 193, 91);
    private static final int PURPLE = Color.rgb(175, 128, 255);

    private final ExecutorService io = Executors.newFixedThreadPool(3);
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicBoolean quoteBusy = new AtomicBoolean(false);
    private final Map<String, List<QuoteView>> quoteViews = new HashMap<>();

    private LinearLayout content;
    private LinearLayout updateBanner;
    private TextView state;
    private TextView quoteState;
    private TextView sectionTitle;
    private TextView versionChip;
    private TextView metricActive, metricPending, metricWr, metricNet, metricTp, metricSl;
    private boolean resumed;
    private boolean monitorStarted;
    private String view = "OVERVIEW";

    private static class QuoteView {
        final String symbol;
        final String side;
        final String status;
        final double entry;
        final double risk;
        final TextView text;
        double previous = Double.NaN;
        QuoteView(String symbol, String side, String status, double entry, double risk, TextView text) {
            this.symbol = symbol;
            this.side = side;
            this.status = status;
            this.entry = entry;
            this.risk = risk;
            this.text = text;
        }
    }

    private final Runnable quoteLoop = new Runnable() {
        @Override public void run() {
            if (!resumed || !usesQuotes()) return;
            if (quoteBusy.compareAndSet(false, true)) {
                io.execute(() -> {
                    try {
                        JSONObject root = new JSONObject(ApiClient.get("/live-quotes?group=all"));
                        JSONArray quotes = root.optJSONArray("quotes");
                        String at = root.optString("receivedAt", "");
                        main.post(() -> applyQuotes(quotes, at));
                    } catch (Throwable e) {
                        main.post(() -> {
                            quoteState.setText("LIVE PRICE • reconnecting • tracker still runs on server");
                            quoteState.setTextColor(YELLOW);
                        });
                    } finally {
                        quoteBusy.set(false);
                    }
                });
            }
            main.postDelayed(this, LIVE_REFRESH_MS);
        }
    };

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildUi();
        ensureMonitor(true);
        showOverview();
        checkVersion();
    }

    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        ensureMonitor(false);
        refreshSummary();
        checkVersion();
        restartQuotes();
    }

    @Override protected void onPause() {
        resumed = false;
        main.removeCallbacks(quoteLoop);
        super.onPause();
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

    private TextView chip(String s, int color) {
        TextView v = tv(s, 10, color, true);
        v.setPadding(dp(10), dp(6), dp(10), dp(6));
        v.setGravity(Gravity.CENTER);
        v.setBackground(shape(Color.argb(32, Color.red(color), Color.green(color), Color.blue(color)), 10, color));
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
        p.setMargins(0, dp(6), 0, dp(6));
        c.setLayoutParams(p);
        return c;
    }

    private Button button(String label, View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(11);
        b.setAllCaps(false);
        b.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        b.setTextColor(TEXT);
        b.setBackground(shape(PANEL2, 12, BORDER));
        b.setOnClickListener(click);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(50), 1f);
        p.setMargins(dp(4), dp(4), dp(4), dp(4));
        b.setLayoutParams(p);
        return b;
    }

    private LinearLayout metric(String label, TextView value, int color) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setPadding(dp(12), dp(10), dp(12), dp(10));
        c.setBackground(shape(PANEL, 13, BORDER));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(78), 1f);
        p.setMargins(dp(4), dp(4), dp(4), dp(4));
        c.setLayoutParams(p);
        c.addView(tv(label, 9, MUTED, true));
        value.setTextColor(color);
        c.addView(value);
        return c;
    }

    private void buildUi() {
        ScrollView sc = new ScrollView(this);
        sc.setFillViewport(true);
        sc.setBackgroundColor(BG);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(14), dp(12), dp(22));
        root.setBackgroundColor(BG);
        sc.addView(root);

        LinearLayout header = row();
        LinearLayout hText = new LinearLayout(this);
        hText.setOrientation(LinearLayout.VERTICAL);
        hText.addView(tv("SIGNALHUB FX", 25, ACCENT, true));
        hText.addView(tv("LIVE PRICE • MULTI-ORDER TRACKER", 10, MUTED, true));
        header.addView(hText, new LinearLayout.LayoutParams(0, -2, 1f));
        versionChip = chip("APP 2.1.0", BLUE);
        header.addView(versionChip);
        root.addView(header);

        updateBanner = card();
        updateBanner.setVisibility(View.GONE);
        root.addView(updateBanner);

        state = tv("MONITOR • STARTING", 10, TEXT, true);
        state.setPadding(dp(12), dp(10), dp(12), dp(10));
        state.setBackground(shape(PANEL, 11, BORDER));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, -2);
        sp.setMargins(0, dp(10), 0, dp(4));
        root.addView(state, sp);

        quoteState = tv("LIVE PRICE • waiting first 5s refresh", 10, ACCENT, true);
        quoteState.setPadding(dp(12), dp(9), dp(12), dp(9));
        quoteState.setBackground(shape(PANEL2, 11, BORDER));
        LinearLayout.LayoutParams qp = new LinearLayout.LayoutParams(-1, -2);
        qp.setMargins(0, dp(4), 0, dp(8));
        root.addView(quoteState, qp);

        metricActive = tv("—", 22, ACCENT, true);
        metricPending = tv("—", 22, YELLOW, true);
        metricWr = tv("—", 22, GREEN, true);
        metricNet = tv("—", 22, BLUE, true);
        metricTp = tv("—", 20, GREEN, true);
        metricSl = tv("—", 20, RED, true);

        LinearLayout m1 = row(); m1.addView(metric("ACTIVE", metricActive, ACCENT)); m1.addView(metric("PENDING", metricPending, YELLOW)); root.addView(m1);
        LinearLayout m2 = row(); m2.addView(metric("WIN RATE", metricWr, GREEN)); m2.addView(metric("NET R", metricNet, BLUE)); root.addView(m2);
        LinearLayout m3 = row(); m3.addView(metric("TP", metricTp, GREEN)); m3.addView(metric("SL", metricSl, RED)); root.addView(m3);

        TextView nav = tv("NAVIGATION", 10, MUTED, true);
        nav.setPadding(dp(3), dp(10), 0, dp(3));
        root.addView(nav);
        LinearLayout n1 = row(); n1.addView(button("OVERVIEW", v -> showOverview())); n1.addView(button("LIVE MARKET", v -> showLive())); root.addView(n1);
        LinearLayout n2 = row(); n2.addView(button("ACTIVE SETUPS", v -> showActive())); n2.addView(button("HISTORY", v -> showHistory())); root.addView(n2);
        LinearLayout n3 = row(); n3.addView(button("PERFORMANCE", v -> showPerformance())); n3.addView(button("SYSTEM", v -> showSystem())); root.addView(n3);

        sectionTitle = tv("OVERVIEW", 14, TEXT, true);
        sectionTitle.setPadding(dp(3), dp(12), dp(3), dp(4));
        root.addView(sectionTitle);

        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        root.addView(content);

        TextView footer = tv("SERVER HISTORY SURVIVES APP UPDATE/REINSTALL • ONE ACTIVE SETUP PER SYMBOL", 9, MUTED, true);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(dp(4), dp(12), dp(4), 0);
        root.addView(footer);
        setContentView(sc);
    }

    private boolean hasNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private void ensureMonitor(boolean ask) {
        if (monitorStarted) return;
        if (!hasNotificationPermission()) {
            state.setText("PHONE ALERTS OFF • server tracker remains active");
            if (ask && Build.VERSION.SDK_INT >= 33) requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS);
            return;
        }
        try {
            Intent i = new Intent(this, MonitorService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
            monitorStarted = true;
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", true).apply();
            state.setText("MONITOR • LIVE • server tracker + phone alerts");
        } catch (Throwable e) {
            state.setText("PHONE MONITOR OFF • server tracker remains active");
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_NOTIFICATIONS && grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) ensureMonitor(false);
    }

    private void clear(String newView, String title) {
        view = newView;
        sectionTitle.setText(title);
        quoteViews.clear();
        content.removeAllViews();
        LinearLayout c = card(); c.addView(tv("Loading fresh data…", 12, MUTED, false)); content.addView(c);
        restartQuotes();
    }

    private void replace(Runnable draw) {
        main.post(() -> {
            if (isFinishing()) return;
            quoteViews.clear();
            content.removeAllViews();
            draw.run();
            restartQuotes();
        });
    }

    private void refreshSummary() {
        io.execute(() -> {
            try {
                JSONObject p = new JSONObject(ApiClient.get("/performance")).optJSONObject("performance");
                if (p != null) main.post(() -> updateMetrics(p));
            } catch (Throwable ignored) {}
        });
    }

    private void updateMetrics(JSONObject p) {
        metricActive.setText(String.valueOf(p.optInt("active", p.optInt("open", 0))));
        metricPending.setText(String.valueOf(p.optInt("pending", 0)));
        metricWr.setText(fmtPct(p.optDouble("winRateResolved", 0)));
        double net = p.optDouble("netRResolved", 0);
        metricNet.setText(fmtR(net));
        metricNet.setTextColor(net > 0 ? GREEN : net < 0 ? RED : BLUE);
        metricTp.setText(String.valueOf(p.optInt("tp", 0)));
        metricSl.setText(String.valueOf(p.optInt("sl", 0)));
    }

    private long installedVersionCode() {
        try {
            PackageInfo p = getPackageManager().getPackageInfo(getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? p.getLongVersionCode() : p.versionCode;
        } catch (Throwable e) { return 0; }
    }

    private void checkVersion() {
        io.execute(() -> {
            try {
                JSONObject app = new JSONObject(ApiClient.get("/app-version")).optJSONObject("app");
                if (app == null) return;
                boolean newer = app.optLong("versionCode", 0) > installedVersionCode();
                main.post(() -> renderVersion(app, newer));
            } catch (Throwable ignored) {}
        });
    }

    private void renderVersion(JSONObject app, boolean newer) {
        if (!newer) {
            versionChip.setText("APP 2.1.0 • CURRENT");
            updateBanner.setVisibility(View.GONE);
            return;
        }
        String v = app.optString("versionName", "NEW");
        versionChip.setText("UPDATE " + v);
        versionChip.setTextColor(YELLOW);
        updateBanner.removeAllViews();
        LinearLayout top = row();
        top.addView(tv("NEW VERSION AVAILABLE", 13, YELLOW, true), new LinearLayout.LayoutParams(0, -2, 1f));
        top.addView(chip("v" + v, YELLOW));
        updateBanner.addView(top);
        JSONArray notes = app.optJSONArray("notes");
        if (notes != null) for (int i=0;i<notes.length();i++) updateBanner.addView(tv("• " + notes.optString(i), 10, MUTED, false));
        updateBanner.addView(tv("Installing a newer APK does not delete server-side signal history.", 10, ACCENT, true));
        updateBanner.setVisibility(View.VISIBLE);
    }

    private void showOverview() {
        clear("OVERVIEW", "OVERVIEW");
        io.execute(() -> {
            try {
                JSONObject status = new JSONObject(ApiClient.get("/status"));
                JSONObject perf = new JSONObject(ApiClient.get("/performance")).optJSONObject("performance");
                JSONObject active = new JSONObject(ApiClient.get("/signals?status=active&limit=12"));
                replace(() -> renderOverview(status, perf, active.optJSONArray("signals")));
                if (perf != null) main.post(() -> updateMetrics(perf));
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderOverview(JSONObject status, JSONObject perf, JSONArray active) {
        LinearLayout core = card();
        LinearLayout top = row();
        top.addView(tv("SYSTEM STATUS", 13, TEXT, true), new LinearLayout.LayoutParams(0,-2,1f));
        top.addView(chip(status.optBoolean("trackerStorage") ? "ONLINE" : "ERROR", status.optBoolean("trackerStorage") ? GREEN : RED));
        core.addView(top);
        core.addView(info("Orders", "MARKET • LIMIT • STOP"));
        core.addView(info("Symbol lock", status.optBoolean("oneActiveSetupPerSymbol") ? "ONE ACTIVE SETUP / SYMBOL" : "—"));
        core.addView(info("Tracker", status.optString("trackerCheckInterval", "—")));
        core.addView(info("Live display", "~5s foreground refresh"));
        content.addView(core);

        if (perf != null) {
            LinearLayout pc = card();
            pc.addView(tv("PERFORMANCE", 13, TEXT, true));
            pc.addView(info("Active / Pending", perf.optInt("active", 0) + " / " + perf.optInt("pending", 0)));
            pc.addView(info("Resolved WR", fmtPct(perf.optDouble("winRateResolved", 0))));
            pc.addView(info("Net / Avg", fmtR(perf.optDouble("netRResolved", 0)) + " / " + fmtR(perf.optDouble("avgRResolved", 0))));
            content.addView(pc);
        }

        addSection("ACTIVE SETUPS", active == null ? 0 : active.length(), ACCENT);
        if (active == null || active.length() == 0) addEmpty("No active or pending setup right now.");
        else for (int i=0;i<active.length();i++) {
            JSONObject s = active.optJSONObject(i);
            if (s != null) content.addView(signalCard(s, false));
        }
    }

    private void showActive() {
        clear("ACTIVE", "ACTIVE SETUPS");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(ApiClient.get("/signals?status=active&limit=100"));
                replace(() -> {
                    JSONArray a = root.optJSONArray("signals");
                    addSection("PENDING + OPEN", a == null ? 0 : a.length(), ACCENT);
                    if (a == null || a.length() == 0) addEmpty("No active setup right now.");
                    else for (int i=0;i<a.length();i++) { JSONObject s=a.optJSONObject(i); if (s!=null) content.addView(signalCard(s,false)); }
                });
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void showHistory() {
        clear("HISTORY", "SIGNAL HISTORY");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(ApiClient.get("/signals?status=closed&limit=150"));
                replace(() -> {
                    JSONArray a = root.optJSONArray("signals");
                    addSection("CLOSED", a == null ? 0 : a.length(), PURPLE);
                    if (a == null || a.length() == 0) addEmpty("No closed signal yet.");
                    else for (int i=0;i<a.length();i++) { JSONObject s=a.optJSONObject(i); if (s!=null) content.addView(signalCard(s,true)); }
                });
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void showLive() {
        clear("LIVE", "LIVE MARKET");
        io.execute(() -> {
            try {
                JSONObject fx = SignalFormatter.unwrap(ApiClient.get("/latest-scan?group=forex"));
                JSONObject mt = SignalFormatter.unwrap(ApiClient.get("/latest-scan?group=metal"));
                JSONObject en = SignalFormatter.unwrap(ApiClient.get("/latest-scan?group=energy"));
                replace(() -> {
                    LinearLayout ctl = card();
                    ctl.addView(tv("MANUAL TECHNICAL SCAN", 12, TEXT, true));
                    ctl.addView(tv("Live price refresh below is display-only. Manual scan may emit a new setup only when that symbol has no active/pending setup.", 10, MUTED, false));
                    LinearLayout br = row();
                    br.addView(button("SCAN FX", v -> runScan("forex")));
                    br.addView(button("SCAN METAL", v -> runScan("metal")));
                    ctl.addView(br);
                    LinearLayout br2 = row();
                    br2.addView(button("SCAN BRENT", v -> runScan("energy")));
                    br2.addView(button("ACTIVE SETUPS", v -> showActive()));
                    ctl.addView(br2);
                    content.addView(ctl);
                    renderScan("FOREX", fx, BLUE);
                    renderScan("METALS", mt, YELLOW);
                    renderScan("BRENT", en, PURPLE);
                });
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void runScan(String group) {
        clear("LIVE", "SCAN • " + group.toUpperCase(Locale.US));
        io.execute(() -> {
            try {
                JSONObject scan = SignalFormatter.unwrap(ApiClient.get("/run-now?group=" + group));
                replace(() -> {
                    LinearLayout back = card();
                    back.addView(button("BACK TO LIVE MARKET", v -> showLive()));
                    content.addView(back);
                    renderScan(group.toUpperCase(Locale.US), scan, "forex".equals(group) ? BLUE : "metal".equals(group) ? YELLOW : PURPLE);
                });
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderScan(String label, JSONObject scan, int accent) {
        LinearLayout head = card();
        LinearLayout top = row();
        top.addView(tv(label, 14, TEXT, true), new LinearLayout.LayoutParams(0,-2,1f));
        top.addView(chip(scan.optString("status", "—"), "OK".equals(scan.optString("status")) ? GREEN : YELLOW));
        head.addView(top);
        head.addView(info("Technical scan", shortTime(scan.optString("scannedAt", "—"))));
        head.addView(info("Actionable", String.valueOf(scan.optInt("actionableCount", 0))));
        JSONObject mix = scan.optJSONObject("orderMix");
        if (mix != null) head.addView(info("Order mix", "M " + mix.optInt("MARKET",0) + " • L " + mix.optInt("LIMIT",0) + " • S " + mix.optInt("STOP",0)));
        content.addView(head);
        JSONArray a = scan.optJSONArray("analyses");
        if (a == null || a.length()==0) { addEmpty("No setup data."); return; }
        for (int i=0;i<Math.min(8,a.length());i++) { JSONObject x=a.optJSONObject(i); if(x!=null) content.addView(analysisCard(x,accent)); }
    }

    private LinearLayout analysisCard(JSONObject x, int accent) {
        LinearLayout c = card();
        String symbol=x.optString("symbol","—"), side=x.optString("side","WAIT"), order=x.optString("orderType","WATCH");
        LinearLayout top=row();
        top.addView(tv(symbol,19,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));
        top.addView(chip(order, orderColor(order)));
        c.addView(top);
        c.addView(chip(side + " • " + x.optString("status","WATCH") + " • SCORE " + x.optInt("score",0), "LONG".equals(side)?GREEN:"SHORT".equals(side)?RED:YELLOW));
        JSONObject p=x.optJSONObject("planned");
        double entry=p==null?0:p.optDouble("entry",0), sl=p==null?0:p.optDouble("sl",0);
        if(p!=null) {
            c.addView(info("Entry",price(entry)));
            c.addView(info("SL / TP",price(sl)+" / "+price(p.optDouble("tp",0))));
            c.addView(info("RR",String.format(Locale.US,"%.2fR",p.optDouble("targetRR",0))));
        }
        TextView live=liveBox();
        c.addView(live);
        registerQuote(symbol,side,"ANALYSIS",entry,Math.abs(entry-sl),live);
        JSONObject tr=x.optJSONObject("tracker");
        if(tr!=null) c.addView(info("Tracker",tr.optString("status","—") + (tr.optBoolean("duplicateBlocked",false)?" • SYMBOL LOCKED":"")));
        JSONObject t=x.optJSONObject("technical");
        if(t!=null) {
            c.addView(info("MTF 5m / 15m",signed(t.optDouble("recommend5m"))+" / "+signed(t.optDouble("recommend15m"))));
            c.addView(info("MTF 1h / 4h",signed(t.optDouble("recommend1h"))+" / "+signed(t.optDouble("recommend4h"))));
        }
        return c;
    }

    private LinearLayout signalCard(JSONObject s, boolean history) {
        LinearLayout c=card();
        String symbol=s.optString("symbol","—"), side=s.optString("side","—"), status=s.optString("status","OPEN"), order=s.optString("orderType","MARKET"), outcome=s.optString("outcome","");
        LinearLayout top=row();
        top.addView(tv(symbol,20,TEXT,true),new LinearLayout.LayoutParams(0,-2,1f));
        top.addView(chip(order,orderColor(order)));
        c.addView(top);
        int sc="PENDING".equals(status)?YELLOW:"OPEN".equals(status)?ACCENT:outcomeColor(outcome);
        c.addView(chip(side + " • " + (history?(outcome.isEmpty()?status:outcome):status) + " • SCORE " + s.optInt("score",0),sc));
        double entry=s.optDouble("entry",0), sl=s.optDouble("sl",0), tp=s.optDouble("tp",0), risk=Math.abs(entry-sl);
        c.addView(info("Entry",price(entry)));
        c.addView(info("SL / TP",price(sl)+" / "+price(tp)));
        if(!history) {
            TextView live=liveBox(); c.addView(live); registerQuote(symbol,side,status,entry,risk,live);
            if("PENDING".equals(status)) {
                c.addView(info("Waiting entry","TP/SL tracking starts only after trigger"));
                c.addView(info("Pending expires",shortTime(s.optString("pendingExpiresAt","—"))));
            } else {
                double r=s.optDouble("currentR",0), target=s.optDouble("targetRR",2.2);
                ProgressBar pb=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
                pb.setMax(100); int progress=(int)Math.round(Math.max(0,Math.min(100,((r+1)/(target+1))*100)));
                pb.setProgress(progress); pb.setProgressTintList(ColorStateList.valueOf(r>=0?GREEN:RED)); pb.setProgressBackgroundTintList(ColorStateList.valueOf(BORDER));
                LinearLayout.LayoutParams pp=new LinearLayout.LayoutParams(-1,dp(9)); pp.setMargins(0,dp(9),0,dp(5)); c.addView(pb,pp);
                c.addView(info("Tracker R",fmtR(r)+" • TP remain "+String.format(Locale.US,"%.2fR",Math.max(0,target-r))));
                c.addView(info("MFE / MAE",fmtR(s.optDouble("maxFavorableR",0))+" / "+fmtR(s.optDouble("maxAdverseR",0))));
                c.addView(info("Triggered",shortTime(s.optString("triggeredAt",s.optString("issuedAt","—")))));
            }
            c.addView(info("Issued / Age",shortTime(s.optString("issuedAt","—"))+" • "+age(s.optString("issuedAt",""))));
        } else {
            Object rr=s.opt("resultR");
            c.addView(info("Result",rr==null||rr==JSONObject.NULL?"N/A":fmtR(s.optDouble("resultR",0))));
            c.addView(info("Exit",price(s.optDouble("exitPrice",0))));
            c.addView(info("Closed",shortTime(s.optString("closedAt","—"))));
            c.addView(info("Resolution",s.optString("resolution","—")));
        }
        return c;
    }

    private void showPerformance() {
        clear("PERFORMANCE", "PERFORMANCE");
        io.execute(() -> {
            try {
                JSONObject p=new JSONObject(ApiClient.get("/performance")).optJSONObject("performance");
                replace(() -> renderPerformance(p));
                if(p!=null) main.post(() -> updateMetrics(p));
            } catch(Throwable e){showError(e);}
        });
    }

    private void renderPerformance(JSONObject p) {
        if(p==null){addEmpty("Performance unavailable.");return;}
        LinearLayout c=card();
        c.addView(tv("RESOLVED PERFORMANCE",14,TEXT,true));
        c.addView(info("Total / Active / Pending",p.optInt("totalSignals")+" / "+p.optInt("active")+" / "+p.optInt("pending")));
        c.addView(info("Open / Closed",p.optInt("open")+" / "+p.optInt("closed")));
        c.addView(info("TP / SL",p.optInt("tp")+" / "+p.optInt("sl")));
        c.addView(info("Win rate",fmtPct(p.optDouble("winRateResolved"))));
        c.addView(info("Net / Avg R",fmtR(p.optDouble("netRResolved"))+" / "+fmtR(p.optDouble("avgRResolved"))));
        c.addView(info("Expired / Ambiguous",p.optInt("expired")+" / "+p.optInt("ambiguous")));
        content.addView(c);
        JSONObject orders=p.optJSONObject("byOrderType");
        if(orders!=null){
            addSection("BY ORDER TYPE",orders.length(),BLUE);
            for(String type:new String[]{"MARKET","LIMIT","STOP"}){
                JSONObject x=orders.optJSONObject(type); if(x==null)continue;
                LinearLayout oc=card(); oc.addView(tv(type,14,orderColor(type),true));
                oc.addView(info("Total / Active / Pending",x.optInt("total")+" / "+x.optInt("active")+" / "+x.optInt("pending")));
                oc.addView(info("TP / SL",x.optInt("tp")+" / "+x.optInt("sl")));
                oc.addView(info("Win rate",fmtPct(x.optDouble("winRate")))); content.addView(oc);
            }
        }
        LinearLayout method=card(); method.addView(tv("METHODOLOGY",12,MUTED,true)); method.addView(tv(p.optString("methodology","—"),11,MUTED,false)); content.addView(method);
    }

    private void showSystem() {
        clear("SYSTEM", "SYSTEM / SOURCES");
        io.execute(() -> {
            try {
                JSONObject s=new JSONObject(ApiClient.get("/status"));
                JSONObject a=new JSONObject(ApiClient.get("/app-version")).optJSONObject("app");
                replace(() -> {
                    LinearLayout app=card(); app.addView(tv("APP",14,TEXT,true));
                    app.addView(info("Installed","2.1.0 • code "+installedVersionCode()));
                    app.addView(info("Latest",a==null?"—":a.optString("versionName","—")+" • code "+a.optLong("versionCode",0)));
                    app.addView(info("Update alerts","CHECKED AUTOMATICALLY")); content.addView(app);
                    LinearLayout core=card(); core.addView(tv("BACKEND",14,TEXT,true));
                    core.addView(info("Core",s.optString("version","—"))); core.addView(info("Gateway",s.optString("gatewayVersion","—")));
                    core.addView(info("Orders",String.valueOf(s.optJSONArray("supportedOrderTypes"))));
                    core.addView(info("Symbol lock",s.optBoolean("oneActiveSetupPerSymbol")?"ON":"OFF"));
                    core.addView(info("Pending expiry",s.optString("pendingExpiry","—")));
                    core.addView(info("Storage",s.optBoolean("trackerStorage")?"KV ONLINE":"OFFLINE")); content.addView(core);
                    LinearLayout data=card(); data.addView(tv("LIVE DATA",14,TEXT,true));
                    data.addView(tv("Price/pip cards refresh about every 5 seconds while this screen is foregrounded. This is a fast scanner refresh, not a true tick stream, because the source does not expose an exact provider-origin timestamp. Tracker/history remains server-side.",11,MUTED,false)); content.addView(data);
                });
            } catch(Throwable e){showError(e);}
        });
    }

    private TextView liveBox() {
        TextView v=tv("LIVE • waiting quote…",12,ACCENT,true);
        v.setPadding(dp(10),dp(10),dp(10),dp(10)); v.setBackground(shape(PANEL2,10,BORDER));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2); p.setMargins(0,dp(8),0,dp(5)); v.setLayoutParams(p); return v;
    }

    private void registerQuote(String symbol,String side,String status,double entry,double risk,TextView t) {
        if(symbol==null||symbol.isEmpty())return;
        String key=symbol.toUpperCase(Locale.US);
        quoteViews.computeIfAbsent(key,k->new ArrayList<>()).add(new QuoteView(key,side,status,entry,risk,t));
    }

    private boolean usesQuotes(){return "OVERVIEW".equals(view)||"LIVE".equals(view)||"ACTIVE".equals(view);}
    private void restartQuotes(){main.removeCallbacks(quoteLoop);if(resumed&&usesQuotes())main.post(quoteLoop);}

    private void applyQuotes(JSONArray quotes,String at) {
        if(quotes==null)return;
        int updated=0;
        for(int i=0;i<quotes.length();i++){
            JSONObject q=quotes.optJSONObject(i); if(q==null)continue;
            String symbol=q.optString("symbol","").toUpperCase(Locale.US);
            List<QuoteView> list=quoteViews.get(symbol); if(list==null)continue;
            double px=q.optDouble("price",0), pipSize=q.optDouble("pipSize",0); String unit=q.optString("unit","pip");
            for(QuoteView b:new ArrayList<>(list)){
                if(b.text==null)continue;
                String arrow=Double.isFinite(b.previous)?(px>b.previous?"↑":px<b.previous?"↓":"•"):"•";
                if("PENDING".equals(b.status)){
                    double distance=pipSize>0?Math.abs(px-b.entry)/pipSize:0;
                    b.text.setText(String.format(Locale.US,"LIVE %s %s   •   %.1f %s TO ENTRY",arrow,price(px),distance,"pip".equals(unit)?"PIPS":"PTS"));
                    b.text.setTextColor(YELLOW);
                } else {
                    double dir="SHORT".equals(b.side)?-1:1, move=dir*(px-b.entry), units=pipSize>0?move/pipSize:0, r=b.risk>0?move/b.risk:0;
                    b.text.setText(String.format(Locale.US,"LIVE %s %s   •   %+.1f %s   •   %+.2fR",arrow,price(px),units,"pip".equals(unit)?"PIPS":"PTS",r));
                    b.text.setTextColor(units>0?GREEN:units<0?RED:ACCENT);
                }
                b.previous=px; updated++;
            }
        }
        quoteState.setText("LIVE PRICE • ~5s foreground refresh • "+updated+" cards • "+shortTime(at));
        quoteState.setTextColor(GREEN);
    }

    private TextView info(String label,String value){TextView t=tv(label+"   "+value,11,TEXT,false);t.setPadding(0,dp(4),0,dp(4));return t;}
    private void addSection(String label,int count,int color){LinearLayout r=row();TextView l=tv(label,12,color,true);l.setPadding(dp(2),dp(10),0,dp(4));r.addView(l,new LinearLayout.LayoutParams(0,-2,1f));r.addView(chip(String.valueOf(count),color));content.addView(r);}
    private void addEmpty(String s){LinearLayout c=card();c.addView(tv(s,11,MUTED,false));content.addView(c);}
    private void showError(Throwable e){replace(() -> {LinearLayout c=card();c.addView(chip("DATA ERROR",RED));c.addView(tv(shortError(e),11,MUTED,false));c.addView(tv("No stale fallback is shown.",11,YELLOW,true));content.addView(c);});}
    private String shortError(Throwable e){String m=e==null?null:e.getMessage();if(m==null||m.trim().isEmpty())return e==null?"Unknown error":e.getClass().getSimpleName();return m.length()>320?m.substring(0,320)+"…":m;}
    private int orderColor(String s){if("MARKET".equals(s))return GREEN;if("LIMIT".equals(s))return BLUE;if("STOP".equals(s))return PURPLE;return YELLOW;}
    private int outcomeColor(String s){if("TP".equals(s))return GREEN;if("SL".equals(s))return RED;if("AMBIGUOUS".equals(s))return YELLOW;return PURPLE;}
    private String fmtR(double r){return String.format(Locale.US,"%+.2fR",r);}
    private String fmtPct(double p){return String.format(Locale.US,"%.1f%%",p);}
    private String signed(double v){return String.format(Locale.US,"%+.3f",v);}
    private String price(double v){if(!Double.isFinite(v)||v==0)return"—";if(Math.abs(v)>=1000)return String.format(Locale.US,"%.2f",v);if(Math.abs(v)>=100)return String.format(Locale.US,"%.3f",v);if(Math.abs(v)>=10)return String.format(Locale.US,"%.4f",v);return String.format(Locale.US,"%.5f",v);}
    private String shortTime(String iso){try{String s=Instant.parse(iso).toString();return s.substring(5,16).replace('T',' ')+"Z";}catch(Exception e){return iso==null||iso.isEmpty()?"—":iso;}}
    private String age(String iso){try{long sec=Math.max(0,Duration.between(Instant.parse(iso),Instant.now()).getSeconds());if(sec<60)return sec+"s";if(sec<3600)return(sec/60)+"m";return String.format(Locale.US,"%dh %02dm",sec/3600,(sec%3600)/60);}catch(Exception e){return"—";}}

    @Override protected void onDestroy(){resumed=false;main.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}
}
