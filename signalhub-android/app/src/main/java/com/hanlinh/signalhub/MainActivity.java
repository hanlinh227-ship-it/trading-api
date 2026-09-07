package com.hanlinh.signalhub;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
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

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 42;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private TextView content;
    private TextView state;
    private boolean monitorStarted = false;

    private static final int BG = Color.rgb(6, 9, 14);
    private static final int PANEL = Color.rgb(14, 20, 28);
    private static final int TEXT = Color.rgb(225, 233, 240);
    private static final int MUTED = Color.rgb(134, 153, 171);
    private static final int ACCENT = Color.rgb(88, 220, 190);

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        showSignals();
        ensureMonitor(true);
    }

    @Override protected void onResume() {
        super.onResume();
        if (state != null) ensureMonitor(false);
    }

    private TextView tv(String text, int sp, int color) {
        TextView v = new TextView(this);
        v.setText(text); v.setTextSize(sp); v.setTextColor(color);
        v.setTypeface(Typeface.MONOSPACE); v.setPadding(12, 10, 12, 10);
        return v;
    }

    private Button button(String label, View.OnClickListener click) {
        Button b = new Button(this);
        b.setText(label); b.setTextSize(11); b.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        b.setTextColor(TEXT); b.setBackgroundColor(PANEL); b.setAllCaps(false); b.setOnClickListener(click);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, 52, 1f);
        p.setMargins(4, 4, 4, 4); b.setLayoutParams(p);
        return b;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL); root.setPadding(14, 18, 14, 14); root.setBackgroundColor(BG);
        TextView title = tv("SIGNALHUB FX", 24, ACCENT); title.setTypeface(Typeface.MONOSPACE, Typeface.BOLD); root.addView(title);
        root.addView(tv("FOREX • GOLD/SILVER • BRENT OIL • LIVE SCAN", 11, MUTED));
        state = tv("MONITOR • STARTING", 11, TEXT); root.addView(state);

        LinearLayout tabs = new LinearLayout(this); tabs.setOrientation(LinearLayout.HORIZONTAL);
        tabs.addView(button("SIGNALS", v -> showSignals()));
        tabs.addView(button("STATS", v -> showStats()));
        tabs.addView(button("SOURCES", v -> showSources()));
        tabs.addView(button("SYSTEM", v -> showSystem()));
        root.addView(tabs);

        LinearLayout actions = new LinearLayout(this); actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.addView(button("SCAN FX", v -> runScan("forex")));
        actions.addView(button("SCAN METAL", v -> runScan("metal")));
        actions.addView(button("SCAN OIL", v -> runScan("energy")));
        root.addView(actions);

        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        content = tv("Loading…", 13, TEXT); content.setTextIsSelectable(true); content.setGravity(Gravity.TOP | Gravity.START);
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        root.addView(tv("Signal only • Score = setup readiness, not guaranteed win probability.", 10, MUTED));
        setContentView(root);
    }

    private boolean hasNotificationPermission() {
        return Build.VERSION.SDK_INT < 33 || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private void ensureMonitor(boolean requestIfNeeded) {
        if (monitorStarted) return;
        if (!hasNotificationPermission()) {
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            state.setText("MONITOR • ALLOW NOTIFICATIONS • DASHBOARD ACTIVE");
            if (requestIfNeeded && Build.VERSION.SDK_INT >= 33) requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS);
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
            state.setText("MONITOR • LIVE • ~5 MIN");
        } catch (Throwable e) {
            monitorStarted = false;
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            state.setText("MONITOR • BACKGROUND OFF • DASHBOARD ACTIVE");
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_NOTIFICATIONS) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) ensureMonitor(false);
        else state.setText("MONITOR • NOTIFICATIONS OFF • DASHBOARD ACTIVE");
    }

    private void setLoading(String title) { content.setText(title + "\n\nLoading fresh state…"); }

    private void showSignals() {
        setLoading("SIGNALS");
        io.execute(() -> {
            StringBuilder b = new StringBuilder();
            for (String g : new String[]{"forex", "metal", "energy"}) {
                try { b.append(SignalFormatter.formatScan(g, ApiClient.get("/latest-scan?group=" + g))); }
                catch (Exception e) { b.append(g.toUpperCase()).append(" • unavailable\n").append(shortError(e)); }
                b.append("\n\n────────────────────────\n\n");
            }
            post(b.toString());
        });
    }

    private void runScan(String group) {
        setLoading("SCAN " + group.toUpperCase()); state.setText("MONITOR • FRESH SCAN " + group.toUpperCase());
        io.execute(() -> {
            try { post(SignalFormatter.formatScan(group, ApiClient.get("/run-now?group=" + group))); }
            catch (Exception e) { post("SCAN ERROR\n\n" + shortError(e)); }
            main.post(() -> state.setText(monitorStarted ? "MONITOR • LIVE • ~5 MIN" : "MONITOR • BACKGROUND OFF • DASHBOARD ACTIVE"));
        });
    }

    private void showStats() {
        setLoading("STATS");
        io.execute(() -> {
            StringBuilder b = new StringBuilder("SIGNAL SERVICE / HISTORY\n\n");
            try { b.append(ApiClient.get("/books")); } catch (Exception e) { b.append("/books unavailable: ").append(shortError(e)); }
            b.append("\n\nSHADOW\n\n");
            try { b.append(ApiClient.get("/shadow")); } catch (Exception e) { b.append("/shadow unavailable: ").append(shortError(e)); }
            post(b.toString());
        });
    }

    private void showSources() {
        setLoading("SOURCES");
        io.execute(() -> {
            try { post(SignalFormatter.formatStatus(ApiClient.get("/status"))); }
            catch (Exception e) { post("STATUS ERROR\n\n" + shortError(e)); }
        });
    }

    private void showSystem() {
        boolean on = getSharedPreferences("signalhub", MODE_PRIVATE).getBoolean("monitoring", false);
        content.setText("SYSTEM\n\n" +
                "APP        SignalHub FX 1.0.2\n" +
                "PACKAGE    com.hanlinh.signalhub\n" +
                "CORE       " + ApiClient.BASE_URL + "\n" +
                "MONITOR    " + (on ? "ON" : "OFF") + "\n" +
                "AUTO SCAN  Forex → Metal → Brent Oil\n" +
                "POLL       ~5 minute cycle\n" +
                "AUTH       No one-time code\n" +
                "MODE       Read-only signal alerts\n\n" +
                "No stale fallback. If the data source is unavailable or a market has no data, SignalHub shows that state instead of recycling an old signal.");
    }

    private String shortError(Throwable e) {
        String m = e == null ? null : e.getMessage();
        if (m == null || m.trim().isEmpty()) return e == null ? "Unknown error" : e.getClass().getSimpleName();
        return m.length() > 240 ? m.substring(0, 240) + "…" : m;
    }

    private void post(String s) { main.post(() -> { if (!isFinishing() && content != null) content.setText(s); }); }

    @Override protected void onDestroy() { super.onDestroy(); io.shutdownNow(); }
}
