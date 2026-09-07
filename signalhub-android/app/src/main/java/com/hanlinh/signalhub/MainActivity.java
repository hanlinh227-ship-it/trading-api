package com.hanlinh.signalhub;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
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
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 42;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    private LinearLayout content;
    private TextView state;
    private TextView sectionTitle;
    private TextView metricOpen, metricWr, metricNetR, metricTp, metricSl, metricResolved;
    private boolean monitorStarted = false;
    private String activeView = "DASHBOARD";

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

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildUi();
        ensureMonitor(true);
        showDashboard();
    }

    @Override protected void onResume() {
        super.onResume();
        if (state != null) ensureMonitor(false);
        refreshSummary();
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
        v.setPadding(dp(9), dp(5), dp(9), dp(5));
        v.setGravity(Gravity.CENTER);
        v.setBackground(bg(Color.argb(35, Color.red(color), Color.green(color), Color.blue(color)), 9, color));
        return v;
    }

    private Button button(String label, View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(10);
        b.setAllCaps(false);
        b.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        b.setTextColor(TEXT);
        b.setPadding(dp(6), 0, dp(6), 0);
        b.setBackground(bg(PANEL_2, 10, BORDER));
        b.setOnClickListener(click);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(44), 1f);
        p.setMargins(dp(3), dp(3), dp(3), dp(3));
        b.setLayoutParams(p);
        return b;
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
        c.setPadding(dp(13), dp(12), dp(13), dp(12));
        c.setBackground(bg(PANEL, 13, BORDER));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        p.setMargins(0, dp(5), 0, dp(5));
        c.setLayoutParams(p);
        return c;
    }

    private LinearLayout metricCard(String label, TextView value, int color) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setPadding(dp(10), dp(9), dp(10), dp(9));
        c.setBackground(bg(PANEL, 12, BORDER));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, dp(74), 1f);
        p.setMargins(dp(3), dp(3), dp(3), dp(3));
        c.setLayoutParams(p);
        TextView l = text(label, 9, MUTED, true);
        value.setTextColor(color);
        c.addView(l);
        c.addView(value);
        return c;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(12), dp(12), dp(8));
        root.setBackgroundColor(BG);

        LinearLayout header = row();
        LinearLayout headerText = new LinearLayout(this);
        headerText.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("SIGNALHUB FX", 25, ACCENT, true);
        headerText.addView(title);
        headerText.addView(text("TRACK • VERIFY • MEASURE", 10, MUTED, true));
        header.addView(headerText, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        header.addView(chip("TRACKER 2.0", BLUE));
        root.addView(header);

        state = text("MONITOR • STARTING", 10, TEXT, true);
        state.setPadding(dp(10), dp(8), dp(10), dp(8));
        state.setBackground(bg(PANEL, 10, BORDER));
        LinearLayout.LayoutParams stateP = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        stateP.setMargins(0, dp(9), 0, dp(5));
        root.addView(state, stateP);

        metricOpen = text("—", 20, ACCENT, true);
        metricWr = text("—", 20, GREEN, true);
        metricNetR = text("—", 20, BLUE, true);
        metricTp = text("—", 18, GREEN, true);
        metricSl = text("—", 18, RED, true);
        metricResolved = text("—", 18, PURPLE, true);

        LinearLayout m1 = row();
        m1.addView(metricCard("OPEN", metricOpen, ACCENT));
        m1.addView(metricCard("WIN RATE", metricWr, GREEN));
        m1.addView(metricCard("NET R", metricNetR, BLUE));
        root.addView(m1);

        LinearLayout m2 = row();
        m2.addView(metricCard("TP", metricTp, GREEN));
        m2.addView(metricCard("SL", metricSl, RED));
        m2.addView(metricCard("RESOLVED", metricResolved, PURPLE));
        root.addView(m2);

        LinearLayout nav1 = row();
        nav1.addView(button("DASHBOARD", v -> showDashboard()));
        nav1.addView(button("LIVE", v -> showLive()));
        nav1.addView(button("OPEN", v -> showOpen()));
        root.addView(nav1);
        LinearLayout nav2 = row();
        nav2.addView(button("HISTORY", v -> showHistory()));
        nav2.addView(button("PERFORMANCE", v -> showPerformance()));
        nav2.addView(button("SYSTEM", v -> showSystem()));
        root.addView(nav2);

        LinearLayout scans = row();
        scans.addView(button("SCAN FX", v -> runScan("forex")));
        scans.addView(button("SCAN METAL", v -> runScan("metal")));
        scans.addView(button("SCAN OIL", v -> runScan("energy")));
        root.addView(scans);

        sectionTitle = text("DASHBOARD", 13, TEXT, true);
        sectionTitle.setPadding(dp(3), dp(8), dp(3), dp(4));
        root.addView(sectionTitle);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(0, 0, 0, dp(16));
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        TextView footer = text("SERVER-SIDE TRACKING • NO STALE FALLBACK • READ-ONLY SIGNAL APP", 9, MUTED, true);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(0, dp(6), 0, dp(2));
        root.addView(footer);
        setContentView(root);
    }

    private boolean hasNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 ||
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private void ensureMonitor(boolean requestIfNeeded) {
        if (monitorStarted) return;
        if (!hasNotificationPermission()) {
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            state.setText("MONITOR • ALLOW NOTIFICATIONS • SERVER TRACKER STILL ACTIVE");
            if (requestIfNeeded && Build.VERSION.SDK_INT >= 33) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS);
            }
            return;
        }
        startMonitorSafely();
    }

    private void startMonitorSafely() {
        try {
            Intent i = new Intent(this, MonitorService.class);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
            monitorStarted = true;
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", true).apply();
            state.setText("MONITOR • LIVE • SERVER TRACKER + PHONE ALERTS");
        } catch (Throwable e) {
            monitorStarted = false;
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            state.setText("PHONE MONITOR OFF • SERVER TRACKER REMAINS ACTIVE");
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_NOTIFICATIONS) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) ensureMonitor(false);
        else state.setText("NOTIFICATIONS OFF • SERVER TRACKER REMAINS ACTIVE");
    }

    private void clearContent(String title) {
        activeView = title;
        sectionTitle.setText(title);
        content.removeAllViews();
        LinearLayout c = card();
        c.addView(text("Loading fresh data…", 12, MUTED, false));
        content.addView(c);
    }

    private void replaceContent(Runnable renderer) {
        main.post(() -> {
            if (isFinishing() || content == null) return;
            content.removeAllViews();
            renderer.run();
        });
    }

    private String get(String path) throws Exception { return ApiClient.get(path); }

    private void refreshSummary() {
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/performance"));
                JSONObject p = root.optJSONObject("performance");
                if (p == null) return;
                main.post(() -> updateSummary(p));
            } catch (Exception ignored) {}
        });
    }

    private void updateSummary(JSONObject p) {
        metricOpen.setText(String.valueOf(p.optInt("open", 0)));
        metricWr.setText(String.format(Locale.US, "%.1f%%", p.optDouble("winRateResolved", 0)));
        double net = p.optDouble("netRResolved", 0);
        metricNetR.setText(String.format(Locale.US, "%+.2fR", net));
        metricNetR.setTextColor(net > 0 ? GREEN : net < 0 ? RED : BLUE);
        metricTp.setText(String.valueOf(p.optInt("tp", 0)));
        metricSl.setText(String.valueOf(p.optInt("sl", 0)));
        metricResolved.setText(String.valueOf(p.optInt("resolved", 0)));
    }

    private void showDashboard() {
        clearContent("DASHBOARD");
        io.execute(() -> {
            try {
                JSONObject perf = new JSONObject(get("/performance")).optJSONObject("performance");
                JSONObject status = new JSONObject(get("/status"));
                JSONObject open = new JSONObject(get("/signals?status=open&limit=8"));
                replaceContent(() -> renderDashboard(status, perf, open));
                if (perf != null) main.post(() -> updateSummary(perf));
            } catch (Exception e) { showError(e); }
        });
    }

    private void renderDashboard(JSONObject status, JSONObject perf, JSONObject openRoot) {
        LinearLayout health = card();
        LinearLayout hrow = row();
        hrow.addView(text("CORE STATUS", 13, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        hrow.addView(chip(status.optBoolean("trackerStorage") ? "TRACKER ONLINE" : "TRACKER ERROR", status.optBoolean("trackerStorage") ? GREEN : RED));
        health.addView(hrow);
        health.addView(infoLine("Backend", status.optString("version", "—")));
        health.addView(infoLine("Data", status.optString("dataSource", "—")));
        health.addView(infoLine("Tracking", status.optString("trackerCheckInterval", "—")));
        health.addView(infoLine("Generated", shortTime(status.optString("generatedAt", "—"))));
        content.addView(health);

        if (perf != null) {
            LinearLayout pc = card();
            pc.addView(text("PERFORMANCE SNAPSHOT", 13, TEXT, true));
            pc.addView(infoLine("Resolved win rate", fmtPct(perf.optDouble("winRateResolved", 0))));
            pc.addView(infoLine("Net resolved", fmtR(perf.optDouble("netRResolved", 0))));
            pc.addView(infoLine("Avg resolved", fmtR(perf.optDouble("avgRResolved", 0))));
            Object pf = perf.opt("profitFactor");
            pc.addView(infoLine("Profit factor", pf == JSONObject.NULL || pf == null ? "∞ / no resolved loss" : String.format(Locale.US, "%.2f", perf.optDouble("profitFactor", 0))));
            pc.addView(infoLine("Max W/L streak", perf.optInt("maxWinStreak", 0) + " / " + perf.optInt("maxLossStreak", 0)));
            content.addView(pc);
        }

        JSONArray arr = openRoot.optJSONArray("signals");
        addSectionLabel("OPEN SIGNALS", arr == null ? 0 : arr.length(), ACCENT);
        if (arr == null || arr.length() == 0) addEmpty("No active tracked signal right now.");
        else for (int i = 0; i < arr.length(); i++) {
            JSONObject s = arr.optJSONObject(i);
            if (s != null) content.addView(signalCard(s, false));
        }
    }

    private void showLive() {
        clearContent("LIVE MARKET");
        io.execute(() -> {
            try {
                JSONObject fx = SignalFormatter.unwrap(get("/latest-scan?group=forex"));
                JSONObject metal = SignalFormatter.unwrap(get("/latest-scan?group=metal"));
                JSONObject energy = SignalFormatter.unwrap(get("/latest-scan?group=energy"));
                replaceContent(() -> {
                    renderLiveGroup("FOREX", fx, BLUE);
                    renderLiveGroup("METALS", metal, YELLOW);
                    renderLiveGroup("BRENT OIL", energy, PURPLE);
                });
                refreshSummary();
            } catch (Exception e) { showError(e); }
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
        head.addView(infoLine("Scan", shortTime(scan.optString("scannedAt", "—"))));
        head.addView(infoLine("Source rows", scan.optInt("sourceRows", 0) + " / " + scan.optInt("requested", 0)));
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
    }

    private LinearLayout analysisCard(JSONObject x, int accent) {
        LinearLayout c = card();
        LinearLayout top = row();
        String symbol = x.optString("symbol", "—");
        String side = x.optString("side", "WAIT");
        TextView sym = text(symbol + "  " + side, 17, side.equals("LONG") ? GREEN : side.equals("SHORT") ? RED : TEXT, true);
        top.addView(sym, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        String st = x.optString("status", "WATCH");
        top.addView(chip(st, "MARKET_SIGNAL".equals(st) ? GREEN : YELLOW));
        c.addView(top);
        c.addView(infoLine("Score", x.optInt("score", 0) + "/100"));

        JSONObject p = x.optJSONObject("planned");
        if (p != null) {
            c.addView(infoLine("Entry / SL / TP", price(p.optDouble("entry")) + "  /  " + price(p.optDouble("sl")) + "  /  " + price(p.optDouble("tp"))));
            c.addView(infoLine("Target RR", String.format(Locale.US, "%.2fR", p.optDouble("targetRR", 0))));
        }
        JSONObject q = x.optJSONObject("analysisQuote");
        if (q != null) c.addView(infoLine("Live price", price(q.optDouble("price")) + "  •  " + q.optString("source", "—")));
        JSONObject t = x.optJSONObject("technical");
        if (t != null) {
            c.addView(infoLine("MTF 5m / 15m", signed(t.optDouble("recommend5m")) + "  /  " + signed(t.optDouble("recommend15m"))));
            c.addView(infoLine("MTF 1h / 4h", signed(t.optDouble("recommend1h")) + "  /  " + signed(t.optDouble("recommend4h"))));
            c.addView(infoLine("RSI15 / ATR15", String.format(Locale.US, "%.1f  /  %s", t.optDouble("rsi15", 0), price(t.optDouble("atr15", 0)))));
            c.addView(infoLine("MACD / EMA", (t.optBoolean("macdAligned") ? "ALIGNED" : "NO") + "  /  " + (t.optBoolean("emaAligned") ? "ALIGNED" : "NO")));
        }
        JSONObject tr = x.optJSONObject("tracker");
        if (tr != null) c.addView(infoLine("Tracker", tr.optString("status", "—") + (tr.has("currentR") ? "  •  " + fmtR(tr.optDouble("currentR")) : "")));
        return c;
    }

    private void showOpen() {
        clearContent("OPEN TRACKER");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/signals?status=open&limit=100"));
                replaceContent(() -> renderSignals(root.optJSONArray("signals"), false));
                refreshSummary();
            } catch (Exception e) { showError(e); }
        });
    }

    private void showHistory() {
        clearContent("SIGNAL HISTORY");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/signals?status=closed&limit=150"));
                replaceContent(() -> renderSignals(root.optJSONArray("signals"), true));
                refreshSummary();
            } catch (Exception e) { showError(e); }
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
    }

    private LinearLayout signalCard(JSONObject s, boolean history) {
        LinearLayout c = card();
        String side = s.optString("side", "—");
        String outcome = s.optString("outcome", "");
        String status = s.optString("status", "OPEN");
        int outcomeColor = outcome.equals("TP") ? GREEN : outcome.equals("SL") ? RED : outcome.equals("AMBIGUOUS") ? YELLOW : outcome.equals("EXPIRED") ? PURPLE : ACCENT;

        LinearLayout top = row();
        top.addView(text(s.optString("symbol", "—") + "  " + side, 18, side.equals("LONG") ? GREEN : RED, true),
                new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        top.addView(chip(history ? (outcome.isEmpty() ? status : outcome) : status, outcomeColor));
        c.addView(top);
        c.addView(infoLine("Group / Score", s.optString("group", "—").toUpperCase(Locale.US) + "  •  " + s.optInt("score", 0) + "/100"));
        c.addView(infoLine("Entry", price(s.optDouble("entry", 0))));
        c.addView(infoLine("SL / TP", price(s.optDouble("sl", 0)) + "  /  " + price(s.optDouble("tp", 0))));

        if (!history) {
            double currentR = s.optDouble("currentR", 0);
            double targetR = s.optDouble("targetRR", 2.2);
            c.addView(infoLine("Last price / R", price(s.optDouble("lastPrice", 0)) + "  •  " + fmtR(currentR)));
            ProgressBar pb = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            pb.setMax(100);
            int progress = (int)Math.round(Math.max(0, Math.min(100, ((currentR + 1.0) / (targetR + 1.0)) * 100.0)));
            pb.setProgress(progress);
            pb.setProgressTintList(ColorStateList.valueOf(currentR >= 0 ? GREEN : RED));
            pb.setProgressBackgroundTintList(ColorStateList.valueOf(BORDER));
            LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(8));
            pp.setMargins(0, dp(8), 0, dp(6));
            c.addView(pb, pp);
            c.addView(infoLine("SL ← progress → TP", progress + "%  •  TP remain " + String.format(Locale.US, "%.2fR", Math.max(0, targetR-currentR))));
            c.addView(infoLine("MFE / MAE", fmtR(s.optDouble("maxFavorableR", 0)) + "  /  " + fmtR(s.optDouble("maxAdverseR", 0))));
            c.addView(infoLine("Issued / Age", shortTime(s.optString("issuedAt", "—")) + "  •  " + age(s.optString("issuedAt", ""))));
            c.addView(infoLine("Expires", shortTime(s.optString("expiresAt", "—"))));
        } else {
            Object rr = s.opt("resultR");
            String result = rr == JSONObject.NULL || rr == null ? "N/A" : fmtR(s.optDouble("resultR", 0));
            c.addView(infoLine("Result", result));
            c.addView(infoLine("Exit", price(s.optDouble("exitPrice", 0))));
            c.addView(infoLine("Issued", shortTime(s.optString("issuedAt", "—"))));
            c.addView(infoLine("Closed", shortTime(s.optString("closedAt", "—")) + "  •  held " + duration(s.optString("issuedAt", ""), s.optString("closedAt", ""))));
            c.addView(infoLine("MFE / MAE", fmtR(s.optDouble("maxFavorableR", 0)) + "  /  " + fmtR(s.optDouble("maxAdverseR", 0))));
            c.addView(infoLine("Resolution", s.optString("resolution", "—")));
        }
        return c;
    }

    private void showPerformance() {
        clearContent("PERFORMANCE");
        io.execute(() -> {
            try {
                JSONObject root = new JSONObject(get("/performance"));
                JSONObject p = root.optJSONObject("performance");
                replaceContent(() -> renderPerformance(p));
                if (p != null) main.post(() -> updateSummary(p));
            } catch (Exception e) { showError(e); }
        });
    }

    private void renderPerformance(JSONObject p) {
        if (p == null) { addEmpty("Performance payload unavailable."); return; }
        LinearLayout overall = card();
        overall.addView(text("RESOLVED PERFORMANCE", 14, TEXT, true));
        overall.addView(infoLine("Signals / Open / Closed", p.optInt("totalSignals") + "  /  " + p.optInt("open") + "  /  " + p.optInt("closed")));
        overall.addView(infoLine("TP / SL", p.optInt("tp") + "  /  " + p.optInt("sl")));
        overall.addView(infoLine("Win rate", fmtPct(p.optDouble("winRateResolved"))));
        overall.addView(infoLine("Net / Avg R", fmtR(p.optDouble("netRResolved")) + "  /  " + fmtR(p.optDouble("avgRResolved"))));
        Object pf = p.opt("profitFactor");
        overall.addView(infoLine("Profit factor", pf == JSONObject.NULL || pf == null ? "∞" : String.format(Locale.US, "%.2f", p.optDouble("profitFactor", 0))));
        overall.addView(infoLine("Expired / Ambiguous", p.optInt("expired") + "  /  " + p.optInt("ambiguous")));
        overall.addView(infoLine("Max W/L streak", p.optInt("maxWinStreak") + "  /  " + p.optInt("maxLossStreak")));
        content.addView(overall);

        JSONObject groups = p.optJSONObject("byGroup");
        if (groups != null) {
            addSectionLabel("BY MARKET", groups.length(), BLUE);
            for (String g : new String[]{"forex","metal","energy"}) {
                JSONObject x = groups.optJSONObject(g);
                if (x == null) continue;
                LinearLayout c = card();
                c.addView(text(g.toUpperCase(Locale.US), 14, TEXT, true));
                c.addView(infoLine("Total / Open", x.optInt("total") + "  /  " + x.optInt("open")));
                c.addView(infoLine("TP / SL", x.optInt("tp") + "  /  " + x.optInt("sl")));
                c.addView(infoLine("Win rate", fmtPct(x.optDouble("winRate"))));
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
            top.addView(text(x.optString("symbol", "—"), 14, TEXT, true), new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
            top.addView(chip(fmtPct(x.optDouble("winRate")), x.optDouble("winRate") >= 50 ? GREEN : RED));
            c.addView(top);
            c.addView(infoLine("Total / Open", x.optInt("total") + "  /  " + x.optInt("open")));
            c.addView(infoLine("TP / SL", x.optInt("tp") + "  /  " + x.optInt("sl")));
            c.addView(infoLine("Net R", fmtR(x.optDouble("netR"))));
            content.addView(c);
        }

        LinearLayout method = card();
        method.addView(text("METHODOLOGY", 12, MUTED, true));
        method.addView(text(p.optString("methodology", "—"), 11, MUTED, false));
        content.addView(method);
    }

    private void showSystem() {
        clearContent("SYSTEM / SOURCES");
        io.execute(() -> {
            try {
                JSONObject s = new JSONObject(get("/status"));
                replaceContent(() -> renderSystem(s));
            } catch (Exception e) { showError(e); }
        });
    }

    private void renderSystem(JSONObject s) {
        boolean on = getSharedPreferences("signalhub", MODE_PRIVATE).getBoolean("monitoring", false);
        LinearLayout app = card();
        app.addView(text("APP", 14, TEXT, true));
        app.addView(infoLine("Version", "SignalHub FX Tracker 2.0.0"));
        app.addView(infoLine("Package", "com.hanlinh.signalhub"));
        app.addView(infoLine("Phone monitor", on ? "ON" : "OFF"));
        app.addView(infoLine("Backend", ApiClient.BASE_URL));
        app.addView(infoLine("Auth", "No OTP / no one-time code"));
        content.addView(app);

        LinearLayout core = card();
        core.addView(text("BACKEND / TRACKER", 14, TEXT, true));
        core.addView(infoLine("Core version", s.optString("version", "—")));
        core.addView(infoLine("Service", s.optString("service", "—")));
        core.addView(infoLine("Source", s.optString("dataSource", "—")));
        core.addView(infoLine("Storage", s.optBoolean("trackerStorage") ? "KV ONLINE" : "OFFLINE"));
        core.addView(infoLine("Server checks", s.optString("trackerCheckInterval", "—")));
        core.addView(infoLine("Bybit isolated", s.optBoolean("independentFromBybit") ? "YES" : "NO"));
        core.addView(infoLine("Stale fallback", s.optBoolean("staleFallback") ? "ON" : "OFF"));
        content.addView(core);

        LinearLayout logic = card();
        logic.addView(text("OUTCOME LOGIC", 14, TEXT, true));
        logic.addView(text("• Signal is persisted when a fresh MARKET_SIGNAL is emitted.\n" +
                "• Server checks open signals every 5 minutes and on manual/app scans.\n" +
                "• TP/SL touch is evaluated from TradingView 5m candle high/low.\n" +
                "• If TP and SL are both inside the same 5m candle and order cannot be known, result = AMBIGUOUS.\n" +
                "• AMBIGUOUS and EXPIRED are excluded from resolved win rate.\n" +
                "• No stale signal is recycled when the source is unavailable.", 11, MUTED, false));
        content.addView(logic);
    }

    private void runScan(String group) {
        clearContent("MANUAL SCAN • " + group.toUpperCase(Locale.US));
        state.setText("MONITOR • RUNNING FRESH " + group.toUpperCase(Locale.US) + " SCAN");
        io.execute(() -> {
            try {
                JSONObject scan = SignalFormatter.unwrap(get("/run-now?group=" + group));
                replaceContent(() -> renderLiveGroup(group.toUpperCase(Locale.US), scan, group.equals("forex") ? BLUE : group.equals("metal") ? YELLOW : PURPLE));
                refreshSummary();
            } catch (Exception e) { showError(e); }
            main.post(() -> state.setText(monitorStarted ? "MONITOR • LIVE • SERVER TRACKER + PHONE ALERTS" : "PHONE MONITOR OFF • SERVER TRACKER REMAINS ACTIVE"));
        });
    }

    private TextView infoLine(String label, String value) {
        TextView t = text(label + "  " + value, 11, TEXT, false);
        t.setPadding(0, dp(3), 0, dp(3));
        return t;
    }

    private void addSectionLabel(String label, int count, int color) {
        LinearLayout r = row();
        TextView l = text(label, 12, color, true);
        l.setPadding(dp(2), dp(9), 0, dp(3));
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
        super.onDestroy();
        io.shutdownNow();
    }
}
