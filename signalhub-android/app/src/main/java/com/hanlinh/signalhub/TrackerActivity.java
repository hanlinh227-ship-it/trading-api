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

public class TrackerActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 42;
    private static final long QUOTE_REFRESH_MS = 5000L;

    private final ExecutorService io = Executors.newFixedThreadPool(3);
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicBoolean quoteBusy = new AtomicBoolean(false);
    private final Map<String, List<QuoteBinding>> quoteBindings = new HashMap<>();

    private LinearLayout content;
    private LinearLayout updateBanner;
    private TextView state;
    private TextView sectionTitle;
    private TextView quotePulse;
    private TextView versionChip;
    private TextView metricOpen, metricWr, metricNetR, metricResolved, metricTp, metricSl;

    private boolean monitorStarted = false;
    private boolean resumed = false;
    private String activeView = "OVERVIEW";
    private JSONObject latestAppInfo;

    private static final int BG = Color.rgb(5, 8, 13);
    private static final int PANEL = Color.rgb(13, 19, 28);
    private static final int PANEL_2 = Color.rgb(19, 27, 39);
    private static final int BORDER = Color.rgb(38, 52, 68);
    private static final int TEXT = Color.rgb(232, 239, 246);
    private static final int MUTED = Color.rgb(137, 157, 177);
    private static final int ACCENT = Color.rgb(87, 225, 190);
    private static final int BLUE = Color.rgb(91, 157, 255);
    private static final int GREEN = Color.rgb(83, 217, 140);
    private static final int RED = Color.rgb(255, 103, 120);
    private static final int YELLOW = Color.rgb(244, 193, 91);
    private static final int PURPLE = Color.rgb(175, 128, 255);

    private final Runnable quoteLoop = new Runnable() {
        @Override public void run() {
            if (!resumed || !needsLiveQuotes()) return;
            if (quoteBusy.compareAndSet(false, true)) {
                io.execute(() -> {
                    try {
                        JSONObject root = new JSONObject(get("/live-quotes?group=all"));
                        JSONArray quotes = root.optJSONArray("quotes");
                        String receivedAt = root.optString("receivedAt", "");
                        main.post(() -> applyLiveQuotes(quotes, receivedAt));
                    } catch (Throwable e) {
                        main.post(() -> {
                            if (quotePulse != null) {
                                quotePulse.setText("LIVE QUOTE • reconnecting • tracker history remains server-side");
                                quotePulse.setTextColor(YELLOW);
                            }
                        });
                    } finally {
                        quoteBusy.set(false);
                    }
                });
            }
            main.postDelayed(this, QUOTE_REFRESH_MS);
        }
    };

    private static class QuoteBinding {
        final String symbol;
        final String side;
        final String group;
        final double entry;
        final double risk;
        final TextView view;
        double lastPrice = Double.NaN;

        QuoteBinding(String symbol, String side, String group, double entry, double risk, TextView view) {
            this.symbol = symbol;
            this.side = side;
            this.group = group;
            this.entry = entry;
            this.risk = risk;
            this.view = view;
        }
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildUi();
        ensureMonitor(true);
        showOverview();
        checkAppVersion();
    }

    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        if (state != null) ensureMonitor(false);
        refreshSummary();
        checkAppVersion();
        restartQuoteLoop();
    }

    @Override protected void onPause() {
        resumed = false;
        main.removeCallbacks(quoteLoop);
        super.onPause();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable bg(int color, int radius, int strokeColor) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        if (strokeColor != Color.TRANSPARENT) d.setStroke(dp(1), strokeColor);
        return d;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(sp);
        v.setTextColor(color);
        v.setTypeface(Typeface.create(Typeface.MONOSPACE, bold ? Typeface.BOLD : Typeface.NORMAL));
        v.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        return v;
    }

    private TextView chip(String label, int color) {
        TextView v = text(label, 10, color, true);
        v.setPadding(dp(10), dp(6), dp(10), dp(6));
        v.setGravity(Gravity.CENTER);
        v.setBackground(bg(Color.argb(34, Color.red(color), Color.green(color), Color.blue(color)), 10, color));
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
        c.setBackground(bg(PANEL, 14, BORDER));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, dp(6), 0, dp(6));
        c.setLayoutParams(p);
        return c;
    }

    private Button navButton(String label, View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(11);
        b.setAllCaps(false);
        b.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        b.setTextColor(TEXT);
        b.setPadding(dp(8), 0, dp(8), 0);
        b.setBackground(bg(PANEL_2, 12, BORDER));
        b.setOnClickListener(click);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(50), 1f);
        p.setMargins(dp(4), dp(4), dp(4), dp(4));
        b.setLayoutParams(p);
        return b;
    }

    private Button compactButton(String label, int color, View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(10);
        b.setAllCaps(false);
        b.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        b.setTextColor(color);
        b.setPadding(dp(8), 0, dp(8), 0);
        b.setBackground(bg(PANEL_2, 11, color));
        b.setOnClickListener(click);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(46), 1f);
        p.setMargins(dp(4), dp(4), dp(4), dp(4));
        b.setLayoutParams(p);
        return b;
    }

    private LinearLayout metricCard(String label, TextView value, int color) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setPadding(dp(12), dp(11), dp(12), dp(11));
        c.setBackground(bg(PANEL, 13, BORDER));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(78), 1f);
        p.setMargins(dp(4), dp(4), dp(4), dp(4));
        c.setLayoutParams(p);
        c.addView(text(label, 9, MUTED, true));
        value.setTextColor(color);
        c.addView(value);
        return c;
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(14), dp(12), dp(20));
        root.setBackgroundColor(BG);
        scroll.addView(root);

        LinearLayout header = row();
        LinearLayout titleBox = new LinearLayout(this);
        titleBox.setOrientation(LinearLayout.VERTICAL);
        titleBox.addView(text("SIGNALHUB FX", 25, ACCENT, true));
        titleBox.addView(text("LIVE PRICE • TRACK • VERIFY", 10, MUTED, true));
        header.addView(titleBox, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        versionChip = chip("APP 2.1.0", BLUE);
        header.addView(versionChip);
        root.addView(header);

        updateBanner = card();
        updateBanner.setVisibility(View.GONE);
        root.addView(updateBanner);

        state = text("MONITOR • STARTING", 10, TEXT, true);
        state.setPadding(dp(12), dp(10), dp(12), dp(10));
        state.setBackground(bg(PANEL, 11, BORDER));
        LinearLayout.LayoutParams stateP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        stateP.setMargins(0, dp(10), 0, dp(4));
        root.addView(state, stateP);

        quotePulse = text("LIVE QUOTE • waiting first foreground refresh", 10, ACCENT, true);
        quotePulse.setPadding(dp(12), dp(8), dp(12), dp(8));
        quotePulse.setBackground(bg(PANEL_2, 10, BORDER));
        LinearLayout.LayoutParams quoteP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        quoteP.setMargins(0, dp(4), 0, dp(8));
        root.addView(quotePulse, quoteP);

        metricOpen = text("—", 22, ACCENT, true);
        metricWr = text("—", 22, GREEN, true);
        metricNetR = text("—", 22, BLUE, true);
        metricResolved = text("—", 22, PURPLE, true);
        metricTp = text("—", 20, GREEN, true);
        metricSl = text("—", 20, RED, true);

        LinearLayout m1 = row();
        m1.addView(metricCard("OPEN", metricOpen, ACCENT));
        m1.addView(metricCard("WIN RATE", metricWr, GREEN));
        root.addView(m1);
        LinearLayout m2 = row();
        m2.addView(metricCard("NET R", metricNetR, BLUE));
        m2.addView(metricCard("RESOLVED", metricResolved, PURPLE));
        root.addView(m2);
        LinearLayout m3 = row();
        m3.addView(metricCard("TP", metricTp, GREEN));
        m3.addView(metricCard("SL", metricSl, RED));
        root.addView(m3);

        TextView navLabel = text("NAVIGATION", 10, MUTED, true);
        navLabel.setPadding(dp(3), dp(10), 0, dp(3));
        root.addView(navLabel);

        LinearLayout n1 = row();
        n1.addView(navButton("OVERVIEW", v -> showOverview()));
        n1.addView(navButton("LIVE MARKET", v -> showLive()));
        root.addView(n1);
        LinearLayout n2 = row();
        n2.addView(navButton("OPEN TRACKER", v -> showOpen()));
        n2.addView(navButton("HISTORY", v -> showHistory()));
        root.addView(n2);
        LinearLayout n3 = row();
        n3.addView(navButton("PERFORMANCE", v -> showPerformance()));
        n3.addView(navButton("SYSTEM", v -> showSystem()));
        root.addView(n3);

        sectionTitle = text("OVERVIEW", 14, TEXT, true);
        sectionTitle.setPadding(dp(3), dp(12), dp(3), dp(4));
        root.addView(sectionTitle);

        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(0, 0, 0, dp(12));
        root.addView(content);

        TextView footer = text("SERVER HISTORY PERSISTS ACROSS APP UPDATES • LIVE QUOTES ARE FOREGROUND REFRESHES", 9, MUTED, true);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(dp(4), dp(10), dp(4), 0);
        root.addView(footer);

        setContentView(scroll);
    }

    private boolean hasNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 ||
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private void ensureMonitor(boolean requestIfNeeded) {
        if (monitorStarted) return;
        if (!hasNotificationPermission()) {
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            state.setText("PHONE ALERTS OFF • allow notifications • server tracker still active");
            if (requestIfNeeded && Build.VERSION.SDK_INT >= 33) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS);
            }
            return;
        }
        try {
            Intent i = new Intent(this, MonitorService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
            monitorStarted = true;
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", true).apply();
            state.setText("MONITOR • LIVE • server tracker + phone alerts");
        } catch (Throwable e) {
            monitorStarted = false;
            state.setText("PHONE MONITOR OFF • server tracker remains active");
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_NOTIFICATIONS) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) ensureMonitor(false);
        else state.setText("NOTIFICATIONS OFF • server tracker remains active");
    }

    private String get(String path) throws Exception {
        return ApiClient.get(path);
    }

    private void clearContent(String view, String title) {
        activeView = view;
        sectionTitle.setText(title);
        quoteBindings.clear();
        content.removeAllViews();
        LinearLayout loading = card();
        loading.addView(text("Loading fresh data…", 12, MUTED, false));
        content.addView(loading);
        restartQuoteLoop();
    }

    private void replaceContent(Runnable renderer) {
        main.post(() -> {
            if (isFinishing() || content == null) return;
            quoteBindings.clear();
            content.removeAllViews();
            renderer.run();
        });
    }

    private void refreshSummary() {
        io.execute(() -> {
            try {
                JSONObject p = new JSONObject(get("/performance")).optJSONObject("performance");
                if (p != null) main.post(() -> updateSummary(p));
            } catch (Throwable ignored) {}
        });
    }

    private void updateSummary(JSONObject p) {
        metricOpen.setText(String.valueOf(p.optInt("open", 0)));
        metricWr.setText(String.format(Locale.US, "%.1f%%", p.optDouble("winRateResolved", 0)));
        double net = p.optDouble("netRResolved", 0);
        metricNetR.setText(String.format(Locale.US, "%+.2fR", net));
        metricNetR.setTextColor(net > 0 ? GREEN : net < 0 ? RED : BLUE);
        metricResolved.setText(String.valueOf(p.optInt("resolved", 0)));
        metricTp.setText(String.valueOf(p.optInt("tp", 0)));
        metricSl.setText(String.valueOf(p.optInt("sl", 0)));
    }

    private long installedVersionCode() {
        try {
            PackageInfo p = getPackageManager().getPackageInfo(getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? p.getLongVersionCode() : p.versionCode;
        } catch (Exception e) {
            return 0;
        }
    }

    private void checkAppVersion() {
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/app-version"));
                JSONObject app = root.optJSONObject("app");
                if (app == null) return;
                latestAppInfo = app;
                long latest = app.optLong("versionCode", 0);
                long installed = installedVersionCode();
                main.post(() -> renderUpdateState(app, latest > installed));
            } catch (Throwable ignored) {}
        });
    }

    private void renderUpdateState(JSONObject app, boolean updateAvailable) {
        String latestName = app.optString("versionName", "—");
        if (!updateAvailable) {
            versionChip.setText("APP 2.1.0 • CURRENT");
            updateBanner.setVisibility(View.GONE);
            return;
        }
        versionChip.setText("UPDATE " + latestName);
        versionChip.setTextColor(YELLOW);
        updateBanner.removeAllViews();
        LinearLayout top = row();
        top.addView(text("NEW APP VERSION", 13, YELLOW, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        top.addView(chip("v" + latestName, YELLOW));
        updateBanner.addView(top);
        updateBanner.addView(text(app.optString("title", "SignalHub update available"), 12, TEXT, true));
        JSONArray notes = app.optJSONArray("notes");
        if (notes != null) {
            for (int i = 0; i < notes.length(); i++) {
                updateBanner.addView(text("• " + notes.optString(i), 10, MUTED, false));
            }
        }
        updateBanner.addView(text("Your server-side signal history is not deleted by installing the newer APK.", 10, ACCENT, true));
        updateBanner.setVisibility(View.VISIBLE);
    }

    private void showOverview() {
        clearContent("OVERVIEW", "OVERVIEW");
        io.execute(() -> {
            try {
                JSONObject perf = new JSONObject(get("/performance")).optJSONObject("performance");
                JSONObject status = new JSONObject(get("/status"));
                JSONObject open = new JSONObject(get("/signals?status=open&limit=10"));
                replaceContent(() -> renderOverview(status, perf, open));
                if (perf != null) main.post(() -> updateSummary(perf));
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderOverview(JSONObject status, JSONObject perf, JSONObject openRoot) {
        LinearLayout live = card();
        LinearLayout ltop = row();
        ltop.addView(text("LIVE DISPLAY", 13, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        ltop.addView(chip("5s REFRESH", ACCENT));
        live.addView(ltop);
        live.addView(infoLine("Quote mode", "foreground near-real-time scanner refresh"));
        live.addView(infoLine("Signal tracker", status.optString("trackerCheckInterval", "5m scheduled")));
        live.addView(infoLine("Gateway", status.optString("gatewayVersion", "—")));
        live.addView(text("Live quote display does not emit new signals. It only updates price / pip movement on screen.", 10, MUTED, false));
        content.addView(live);

        if (perf != null) {
            LinearLayout pc = card();
            pc.addView(text("PERFORMANCE SNAPSHOT", 13, TEXT, true));
            pc.addView(infoLine("Resolved win rate", fmtPct(perf.optDouble("winRateResolved", 0))));
            pc.addView(infoLine("Net / Avg R", fmtR(perf.optDouble("netRResolved", 0)) + "  /  " + fmtR(perf.optDouble("avgRResolved", 0))));
            pc.addView(infoLine("TP / SL", perf.optInt("tp", 0) + "  /  " + perf.optInt("sl", 0)));
            content.addView(pc);
        }

        JSONArray arr = openRoot.optJSONArray("signals");
        addSectionLabel("OPEN SIGNALS", arr == null ? 0 : arr.length(), ACCENT);
        if (arr == null || arr.length() == 0) addEmpty("No active tracked signal right now.");
        else for (int i = 0; i < arr.length(); i++) {
            JSONObject s = arr.optJSONObject(i);
            if (s != null) content.addView(signalCard(s, false));
        }
        restartQuoteLoop();
    }

    private void showLive() {
        clearContent("LIVE", "LIVE MARKET");
        io.execute(() -> {
            try {
                JSONObject fx = SignalFormatter.unwrap(get("/latest-scan?group=forex"));
                JSONObject metal = SignalFormatter.unwrap(get("/latest-scan?group=metal"));
                JSONObject energy = SignalFormatter.unwrap(get("/latest-scan?group=energy"));
                replaceContent(() -> {
                    LinearLayout controls = card();
                    controls.addView(text("FRESH ANALYSIS", 12, TEXT, true));
                    controls.addView(text("Manual scan refreshes technical setup; live quote refresh below does not create signals.", 10, MUTED, false));
                    LinearLayout buttons = row();
                    buttons.addView(compactButton("FX", BLUE, v -> runScan("forex")));
                    buttons.addView(compactButton("METALS", YELLOW, v -> runScan("metal")));
                    buttons.addView(compactButton("BRENT", PURPLE, v -> runScan("energy")));
                    controls.addView(buttons);
                    content.addView(controls);
                    renderLiveGroup("FOREX", fx, BLUE);
                    renderLiveGroup("METALS", metal, YELLOW);
                    renderLiveGroup("BRENT OIL", energy, PURPLE);
                });
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderLiveGroup(String label, JSONObject scan, int color) {
        JSONArray a = scan.optJSONArray("analyses");
        LinearLayout head = card();
        LinearLayout r = row();
        r.addView(text(label, 14, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        String st = scan.optString("status", "UNKNOWN");
        r.addView(chip(st, "OK".equals(st) ? GREEN : YELLOW));
        head.addView(r);
        head.addView(infoLine("Technical scan", shortTime(scan.optString("scannedAt", "—"))));
        head.addView(infoLine("Actionable", String.valueOf(scan.optInt("actionableCount", 0))));
        content.addView(head);
        if (a == null || a.length() == 0) {
            addEmpty("No fresh setup for " + label + ".");
            return;
        }
        for (int i = 0; i < Math.min(8, a.length()); i++) {
            JSONObject x = a.optJSONObject(i);
            if (x != null) content.addView(analysisCard(x, color));
        }
        restartQuoteLoop();
    }

    private LinearLayout analysisCard(JSONObject x, int accent) {
        LinearLayout c = card();
        String symbol = x.optString("symbol", "—");
        String side = x.optString("side", "WAIT");
        String group = x.optString("group", "forex");
        LinearLayout top = row();
        top.addView(text(symbol, 19, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        top.addView(chip(side, "LONG".equals(side) ? GREEN : "SHORT".equals(side) ? RED : MUTED));
        c.addView(top);

        LinearLayout meta = row();
        meta.addView(chip(x.optString("status", "WATCH"), "MARKET_SIGNAL".equals(x.optString("status")) ? GREEN : YELLOW));
        TextView score = text("  SCORE " + x.optInt("score", 0) + "/100", 10, MUTED, true);
        meta.addView(score);
        c.addView(meta);

        JSONObject p = x.optJSONObject("planned");
        double entry = p == null ? 0 : p.optDouble("entry", 0);
        double sl = p == null ? 0 : p.optDouble("sl", 0);
        if (p != null) {
            c.addView(infoLine("ENTRY", price(entry)));
            c.addView(infoLine("SL / TP", price(sl) + "  /  " + price(p.optDouble("tp", 0))));
            c.addView(infoLine("TARGET", String.format(Locale.US, "%.2fR", p.optDouble("targetRR", 0))));
        }

        TextView live = text("LIVE • waiting quote…", 12, accent, true);
        live.setPadding(dp(10), dp(9), dp(10), dp(9));
        live.setBackground(bg(PANEL_2, 10, BORDER));
        c.addView(live);
        registerQuote(symbol, side, group, entry, Math.abs(entry - sl), live);

        JSONObject t = x.optJSONObject("technical");
        if (t != null) {
            c.addView(infoLine("MTF 5m / 15m", signed(t.optDouble("recommend5m")) + "  /  " + signed(t.optDouble("recommend15m"))));
            c.addView(infoLine("MTF 1h / 4h", signed(t.optDouble("recommend1h")) + "  /  " + signed(t.optDouble("recommend4h"))));
            c.addView(infoLine("RSI15 / ATR15", String.format(Locale.US, "%.1f  /  %s", t.optDouble("rsi15", 0), price(t.optDouble("atr15", 0)))));
            c.addView(infoLine("MACD / EMA", (t.optBoolean("macdAligned") ? "ALIGNED" : "NO") + "  /  " + (t.optBoolean("emaAligned") ? "ALIGNED" : "NO")));
        }
        return c;
    }

    private void showOpen() {
        clearContent("OPEN", "OPEN TRACKER");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/signals?status=open&limit=100"));
                replaceContent(() -> renderSignals(root.optJSONArray("signals"), false));
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void showHistory() {
        clearContent("HISTORY", "SIGNAL HISTORY");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/signals?status=closed&limit=150"));
                replaceContent(() -> renderSignals(root.optJSONArray("signals"), true));
                refreshSummary();
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderSignals(JSONArray arr, boolean history) {
        addSectionLabel(history ? "CLOSED SIGNALS" : "ACTIVE SIGNALS", arr == null ? 0 : arr.length(), history ? PURPLE : ACCENT);
        if (arr == null || arr.length() == 0) {
            addEmpty(history ? "No signal has closed yet." : "No open signal right now.");
            return;
        }
        for (int i = 0; i < arr.length(); i++) {
            JSONObject s = arr.optJSONObject(i);
            if (s != null) content.addView(signalCard(s, history));
        }
        restartQuoteLoop();
    }

    private LinearLayout signalCard(JSONObject s, boolean history) {
        LinearLayout c = card();
        String side = s.optString("side", "—");
        String outcome = s.optString("outcome", "");
        String status = s.optString("status", "OPEN");
        int outcomeColor = "TP".equals(outcome) ? GREEN : "SL".equals(outcome) ? RED : "AMBIGUOUS".equals(outcome) ? YELLOW : "EXPIRED".equals(outcome) ? PURPLE : ACCENT;

        LinearLayout top = row();
        top.addView(text(s.optString("symbol", "—"), 20, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        top.addView(chip(side, "LONG".equals(side) ? GREEN : RED));
        c.addView(top);
        c.addView(chip(history ? (outcome.isEmpty() ? status : outcome) : status, outcomeColor));
        c.addView(infoLine("GROUP / SCORE", s.optString("group", "—").toUpperCase(Locale.US) + "  •  " + s.optInt("score", 0) + "/100"));
        c.addView(infoLine("ENTRY", price(s.optDouble("entry", 0))));
        c.addView(infoLine("SL / TP", price(s.optDouble("sl", 0)) + "  /  " + price(s.optDouble("tp", 0))));

        if (!history) {
            double entry = s.optDouble("entry", 0);
            double risk = Math.abs(entry - s.optDouble("sl", 0));
            TextView live = text("LIVE • waiting quote…", 13, ACCENT, true);
            live.setPadding(dp(10), dp(10), dp(10), dp(10));
            live.setBackground(bg(PANEL_2, 10, BORDER));
            c.addView(live);
            registerQuote(s.optString("symbol", "—"), side, s.optString("group", "forex"), entry, risk, live);

            double currentR = s.optDouble("currentR", 0);
            double targetR = s.optDouble("targetRR", 2.2);
            ProgressBar pb = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            pb.setMax(100);
            int progress = (int)Math.round(Math.max(0, Math.min(100, ((currentR + 1.0) / (targetR + 1.0)) * 100.0)));
            pb.setProgress(progress);
            pb.setProgressTintList(ColorStateList.valueOf(currentR >= 0 ? GREEN : RED));
            pb.setProgressBackgroundTintList(ColorStateList.valueOf(BORDER));
            LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(9));
            pp.setMargins(0, dp(10), 0, dp(6));
            c.addView(pb, pp);
            c.addView(infoLine("TRACKER R", fmtR(currentR) + "  •  TP remain " + String.format(Locale.US, "%.2fR", Math.max(0, targetR-currentR))));
            c.addView(infoLine("MFE / MAE", fmtR(s.optDouble("maxFavorableR", 0)) + "  /  " + fmtR(s.optDouble("maxAdverseR", 0))));
            c.addView(infoLine("ISSUED / AGE", shortTime(s.optString("issuedAt", "—")) + "  •  " + age(s.optString("issuedAt", ""))));
        } else {
            Object rr = s.opt("resultR");
            String result = rr == JSONObject.NULL || rr == null ? "N/A" : fmtR(s.optDouble("resultR", 0));
            c.addView(infoLine("RESULT", result));
            c.addView(infoLine("EXIT", price(s.optDouble("exitPrice", 0))));
            c.addView(infoLine("ISSUED", shortTime(s.optString("issuedAt", "—"))));
            c.addView(infoLine("CLOSED", shortTime(s.optString("closedAt", "—")) + "  •  held " + duration(s.optString("issuedAt", ""), s.optString("closedAt", ""))));
            c.addView(infoLine("MFE / MAE", fmtR(s.optDouble("maxFavorableR", 0)) + "  /  " + fmtR(s.optDouble("maxAdverseR", 0))));
            c.addView(infoLine("RESOLUTION", s.optString("resolution", "—")));
        }
        return c;
    }

    private void showPerformance() {
        clearContent("PERFORMANCE", "PERFORMANCE");
        io.execute(() -> {
            try {
                JSONObject p = new JSONObject(get("/performance")).optJSONObject("performance");
                replaceContent(() -> renderPerformance(p));
                if (p != null) main.post(() -> updateSummary(p));
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderPerformance(JSONObject p) {
        if (p == null) { addEmpty("Performance payload unavailable."); return; }
        LinearLayout overall = card();
        overall.addView(text("RESOLVED PERFORMANCE", 14, TEXT, true));
        overall.addView(infoLine("SIGNALS / OPEN / CLOSED", p.optInt("totalSignals") + "  /  " + p.optInt("open") + "  /  " + p.optInt("closed")));
        overall.addView(infoLine("TP / SL", p.optInt("tp") + "  /  " + p.optInt("sl")));
        overall.addView(infoLine("WIN RATE", fmtPct(p.optDouble("winRateResolved"))));
        overall.addView(infoLine("NET / AVG R", fmtR(p.optDouble("netRResolved")) + "  /  " + fmtR(p.optDouble("avgRResolved"))));
        Object pf = p.opt("profitFactor");
        overall.addView(infoLine("PROFIT FACTOR", pf == JSONObject.NULL || pf == null ? "∞" : String.format(Locale.US, "%.2f", p.optDouble("profitFactor", 0))));
        overall.addView(infoLine("EXPIRED / AMBIGUOUS", p.optInt("expired") + "  /  " + p.optInt("ambiguous")));
        overall.addView(infoLine("MAX W/L STREAK", p.optInt("maxWinStreak") + "  /  " + p.optInt("maxLossStreak")));
        content.addView(overall);

        JSONObject groups = p.optJSONObject("byGroup");
        if (groups != null) {
            addSectionLabel("BY MARKET", groups.length(), BLUE);
            for (String g : new String[]{"forex","metal","energy"}) {
                JSONObject x = groups.optJSONObject(g);
                if (x == null) continue;
                LinearLayout c = card();
                c.addView(text(g.toUpperCase(Locale.US), 14, TEXT, true));
                c.addView(infoLine("TOTAL / OPEN", x.optInt("total") + "  /  " + x.optInt("open")));
                c.addView(infoLine("TP / SL", x.optInt("tp") + "  /  " + x.optInt("sl")));
                c.addView(infoLine("WIN RATE", fmtPct(x.optDouble("winRate"))));
                content.addView(c);
            }
        }

        JSONArray syms = p.optJSONArray("bySymbol");
        addSectionLabel("BY SYMBOL", syms == null ? 0 : syms.length(), PURPLE);
        if (syms != null) for (int i = 0; i < syms.length(); i++) {
            JSONObject x = syms.optJSONObject(i);
            if (x == null) continue;
            LinearLayout c = card();
            LinearLayout top = row();
            top.addView(text(x.optString("symbol", "—"), 15, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
            top.addView(chip(fmtPct(x.optDouble("winRate")), x.optDouble("winRate") >= 50 ? GREEN : RED));
            c.addView(top);
            c.addView(infoLine("TOTAL / OPEN", x.optInt("total") + "  /  " + x.optInt("open")));
            c.addView(infoLine("TP / SL", x.optInt("tp") + "  /  " + x.optInt("sl")));
            c.addView(infoLine("NET R", fmtR(x.optDouble("netR"))));
            content.addView(c);
        }
    }

    private void showSystem() {
        clearContent("SYSTEM", "SYSTEM / SOURCES");
        io.execute(() -> {
            try {
                JSONObject status = new JSONObject(get("/status"));
                JSONObject app = new JSONObject(get("/app-version")).optJSONObject("app");
                replaceContent(() -> renderSystem(status, app));
            } catch (Throwable e) { showError(e); }
        });
    }

    private void renderSystem(JSONObject s, JSONObject appInfo) {
        boolean on = getSharedPreferences("signalhub", MODE_PRIVATE).getBoolean("monitoring", false);
        LinearLayout app = card();
        app.addView(text("APP", 14, TEXT, true));
        app.addView(infoLine("INSTALLED", "SignalHub FX Tracker 2.1.0 • code " + installedVersionCode()));
        app.addView(infoLine("LATEST", appInfo == null ? "—" : appInfo.optString("versionName", "—") + " • code " + appInfo.optLong("versionCode", 0)));
        app.addView(infoLine("PHONE MONITOR", on ? "ON" : "OFF"));
        app.addView(infoLine("PACKAGE", "com.hanlinh.signalhub"));
        app.addView(infoLine("BACKEND", ApiClient.BASE_URL));
        content.addView(app);

        LinearLayout core = card();
        core.addView(text("BACKEND / TRACKER", 14, TEXT, true));
        core.addView(infoLine("CORE", s.optString("version", "—")));
        core.addView(infoLine("GATEWAY", s.optString("gatewayVersion", "—")));
        core.addView(infoLine("SOURCE", s.optString("dataSource", "—")));
        core.addView(infoLine("STORAGE", s.optBoolean("trackerStorage") ? "KV ONLINE" : "OFFLINE"));
        core.addView(infoLine("TRACKER CHECK", s.optString("trackerCheckInterval", "—")));
        core.addView(infoLine("LIVE QUOTE", "5s foreground refresh"));
        core.addView(infoLine("STALE FALLBACK", s.optBoolean("staleFallback") ? "ON" : "OFF"));
        content.addView(core);

        LinearLayout logic = card();
        logic.addView(text("DATA MEANING", 14, TEXT, true));
        logic.addView(text("• Server tracker/history survives app uninstall and update.\n" +
                "• Technical signals are evaluated separately from the fast display quote feed.\n" +
                "• Price/pip display refreshes about every 5 seconds while this app is foregrounded.\n" +
                "• This source is not claimed as a true tick stream because TradingView scanner does not expose an exact provider-origin timestamp.\n" +
                "• TP/SL outcome tracking remains server-side and is not replaced by the UI quote loop.", 11, MUTED, false));
        content.addView(logic);
    }

    private void runScan(String group) {
        clearContent("LIVE", "MANUAL SCAN • " + group.toUpperCase(Locale.US));
        state.setText("MONITOR • running fresh " + group.toUpperCase(Locale.US) + " technical scan");
        io.execute(() -> {
            try {
                JSONObject scan = SignalFormatter.unwrap(get("/run-now?group=" + group));
                replaceContent(() -> {
                    LinearLayout back = card();
                    back.addView(compactButton("BACK TO LIVE MARKET", ACCENT, v -> showLive()));
                    content.addView(back);
                    renderLiveGroup(group.toUpperCase(Locale.US), scan, "forex".equals(group) ? BLUE : "metal".equals(group) ? YELLOW : PURPLE);
                });
                refreshSummary();
            } catch (Throwable e) { showError(e); }
            main.post(() -> state.setText(monitorStarted ? "MONITOR • LIVE • server tracker + phone alerts" : "PHONE MONITOR OFF • server tracker remains active"));
        });
    }

    private void registerQuote(String symbol, String side, String group, double entry, double risk, TextView view) {
        if (symbol == null || symbol.isEmpty() || view == null) return;
        String key = symbol.toUpperCase(Locale.US);
        List<QuoteBinding> list = quoteBindings.get(key);
        if (list == null) {
            list = new ArrayList<>();
            quoteBindings.put(key, list);
        }
        list.add(new QuoteBinding(key, side, group, entry, risk, view));
    }

    private boolean needsLiveQuotes() {
        return "OVERVIEW".equals(activeView) || "LIVE".equals(activeView) || "OPEN".equals(activeView);
    }

    private void restartQuoteLoop() {
        main.removeCallbacks(quoteLoop);
        if (resumed && needsLiveQuotes()) main.post(quoteLoop);
    }

    private void applyLiveQuotes(JSONArray quotes, String receivedAt) {
        if (quotes == null) return;
        int updated = 0;
        for (int i = 0; i < quotes.length(); i++) {
            JSONObject q = quotes.optJSONObject(i);
            if (q == null) continue;
            String symbol = q.optString("symbol", "").toUpperCase(Locale.US);
            List<QuoteBinding> list = quoteBindings.get(symbol);
            if (list == null || list.isEmpty()) continue;
            double px = q.optDouble("price", 0);
            double pipSize = q.optDouble("pipSize", 0);
            String unit = q.optString("unit", "pip");
            for (QuoteBinding b : new ArrayList<>(list)) {
                if (b.view == null || b.view.getWindowToken() == null) continue;
                double direction = "SHORT".equals(b.side) ? -1.0 : 1.0;
                double move = direction * (px - b.entry);
                double units = pipSize > 0 ? move / pipSize : 0;
                double r = b.risk > 0 ? move / b.risk : 0;
                String arrow = Double.isFinite(b.lastPrice) ? (px > b.lastPrice ? "↑" : px < b.lastPrice ? "↓" : "•") : "•";
                String unitLabel = "pip".equals(unit) ? "PIPS" : "PTS";
                b.view.setText(String.format(Locale.US, "LIVE %s %s   •   %+.1f %s   •   %+.2fR", arrow, price(px), units, unitLabel, r));
                b.view.setTextColor(units > 0 ? GREEN : units < 0 ? RED : ACCENT);
                b.lastPrice = px;
                updated++;
            }
        }
        if (quotePulse != null) {
            quotePulse.setText("LIVE QUOTE • 5s foreground refresh • " + updated + " card updates • " + shortTime(receivedAt));
            quotePulse.setTextColor(GREEN);
        }
    }

    private TextView infoLine(String label, String value) {
        TextView t = text(label + "   " + value, 11, TEXT, false);
        t.setPadding(0, dp(4), 0, dp(4));
        return t;
    }

    private void addSectionLabel(String label, int count, int color) {
        LinearLayout r = row();
        TextView l = text(label, 12, color, true);
        l.setPadding(dp(2), dp(10), 0, dp(4));
        r.addView(l, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        r.addView(chip(String.valueOf(count), color));
        content.addView(r);
    }

    private void addEmpty(String msg) {
        LinearLayout c = card();
        c.addView(text(msg, 11, MUTED, false));
        content.addView(c);
    }

    private void showError(Throwable e) {
        replaceContent(() -> {
            LinearLayout c = card();
            c.addView(chip("DATA ERROR", RED));
            c.addView(text(shortError(e), 11, MUTED, false));
            c.addView(text("No stale fallback is shown.", 11, YELLOW, true));
            content.addView(c);
        });
    }

    private String shortError(Throwable e) {
        String m = e == null ? null : e.getMessage();
        if (m == null || m.trim().isEmpty()) return e == null ? "Unknown error" : e.getClass().getSimpleName();
        return m.length() > 360 ? m.substring(0, 360) + "…" : m;
    }

    private String fmtR(double r) { return String.format(Locale.US, "%+.2fR", r); }
    private String fmtPct(double p) { return String.format(Locale.US, "%.1f%%", p); }
    private String signed(double v) { return String.format(Locale.US, "%+.3f", v); }

    private String price(double v) {
        if (!Double.isFinite(v) || v == 0) return "—";
        if (Math.abs(v) >= 1000) return String.format(Locale.US, "%.2f", v);
        if (Math.abs(v) >= 100) return String.format(Locale.US, "%.3f", v);
        if (Math.abs(v) >= 10) return String.format(Locale.US, "%.4f", v);
        return String.format(Locale.US, "%.5f", v);
    }

    private String shortTime(String iso) {
        try {
            Instant i = Instant.parse(iso);
            String s = i.toString();
            return s.substring(5, 16).replace('T', ' ') + "Z";
        } catch (Exception e) { return iso == null || iso.isEmpty() ? "—" : iso; }
    }

    private String age(String iso) {
        try {
            long sec = Math.max(0, Duration.between(Instant.parse(iso), Instant.now()).getSeconds());
            if (sec < 60) return sec + "s";
            if (sec < 3600) return (sec/60) + "m";
            return String.format(Locale.US, "%dh %02dm", sec/3600, (sec%3600)/60);
        } catch (Exception e) { return "—"; }
    }

    private String duration(String start, String end) {
        try {
            long sec = Math.max(0, Duration.between(Instant.parse(start), Instant.parse(end)).getSeconds());
            if (sec < 3600) return (sec/60) + "m";
            return String.format(Locale.US, "%dh %02dm", sec/3600, (sec%3600)/60);
        } catch (Exception e) { return "—"; }
    }

    @Override protected void onDestroy() {
        resumed = false;
        main.removeCallbacksAndMessages(null);
        io.shutdownNow();
        super.onDestroy();
    }
}
