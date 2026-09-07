package com.hanlinh.signalhub;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.os.Build;
import android.os.IBinder;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MonitorService extends Service {
    private static final String CH_MONITOR = "signalhub_monitor";
    private static final String CH_SIGNAL = "signalhub_signal";
    private static final String CH_UPDATE = "signalhub_update";
    private static final int FOREGROUND_ID = 7001;
    private static final long RECENT_EVENT_SECONDS = 12 * 60;

    private volatile boolean running;
    private ExecutorService worker;

    @Override public void onCreate() {
        super.onCreate();
        createChannels();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        try {
            startForeground(FOREGROUND_ID, monitorNotification("Server tracker active • syncing MARKET/LIMIT/STOP"));
        } catch (Throwable e) {
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!running) {
            running = true;
            worker = Executors.newSingleThreadExecutor();
            worker.execute(this::loop);
        }
        return START_STICKY;
    }

    private void loop() {
        while (running) {
            scanAndSync("forex");
            sleep(20000); if (!running) break;
            scanAndSync("metal");
            sleep(20000); if (!running) break;
            scanAndSync("energy");
            updateForegroundSummary();
            checkAppUpdate();
            sleep(260000);
        }
    }

    private void scanAndSync(String group) {
        try {
            ApiClient.get("/run-now?group=" + group);
            syncTrackedSignals(group);
        } catch (Throwable ignored) {
            // Fail closed: no stale signal recycling and no foreground service crash.
        }
    }

    private void syncTrackedSignals(String group) {
        try {
            JSONObject root = new JSONObject(ApiClient.get("/signals?group=" + group + "&limit=80"));
            JSONArray signals = root.optJSONArray("signals");
            if (signals == null) return;
            SharedPreferences p = getSharedPreferences("signalhub", MODE_PRIVATE);

            for (int i = signals.length() - 1; i >= 0; i--) {
                JSONObject s = signals.optJSONObject(i);
                if (s == null) continue;
                String id = s.optString("id", "");
                if (id.isEmpty()) continue;
                String status = s.optString("status", "OPEN");
                String outcome = s.optString("outcome", "");
                String orderType = s.optString("orderType", "MARKET");
                String currentState = status + ":" + outcome + ":" + orderType;
                String key = "tracker_state_" + id;
                String previous = p.getString(key, null);

                if (previous == null) {
                    p.edit().putString(key, currentState).apply();
                    if (("PENDING".equals(status) || "OPEN".equals(status)) && isRecent(s.optString("issuedAt", ""))) {
                        notifyNewSignal(s);
                    } else if ("CLOSED".equals(status) && isRecent(s.optString("closedAt", ""))) {
                        notifyOutcome(s);
                    }
                    continue;
                }

                if (!previous.equals(currentState)) {
                    p.edit().putString(key, currentState).apply();
                    boolean wasPending = previous.startsWith("PENDING:");
                    if (wasPending && "OPEN".equals(status)) notifyTriggered(s);
                    else if ("CLOSED".equals(status)) notifyOutcome(s);
                    else if ("PENDING".equals(status) || "OPEN".equals(status)) notifyNewSignal(s);
                }
            }
        } catch (Throwable ignored) {}
    }

    private void updateForegroundSummary() {
        try {
            JSONObject p = new JSONObject(ApiClient.get("/performance")).optJSONObject("performance");
            if (p == null) return;
            String text = String.format(Locale.US, "Active %d • Pending %d • WR %.1f%% • Net %+.2fR",
                    p.optInt("active", p.optInt("open", 0)), p.optInt("pending", 0),
                    p.optDouble("winRateResolved", 0), p.optDouble("netRResolved", 0));
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) nm.notify(FOREGROUND_ID, monitorNotification(text));
        } catch (Throwable ignored) {}
    }

    private long installedVersionCode() {
        try {
            PackageInfo p = getPackageManager().getPackageInfo(getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? p.getLongVersionCode() : p.versionCode;
        } catch (Throwable e) {
            return 0;
        }
    }

    private void checkAppUpdate() {
        try {
            JSONObject app = new JSONObject(ApiClient.get("/app-version")).optJSONObject("app");
            if (app == null) return;
            long latest = app.optLong("versionCode", 0);
            if (latest <= installedVersionCode() || latest <= 0) return;
            SharedPreferences p = getSharedPreferences("signalhub", MODE_PRIVATE);
            if (p.getLong("notified_app_version", 0) >= latest) return;
            p.edit().putLong("notified_app_version", latest).apply();
            notifyUpdate(app);
        } catch (Throwable ignored) {}
    }

    private boolean isRecent(String iso) {
        try {
            long sec = Math.abs(Duration.between(Instant.parse(iso), Instant.now()).getSeconds());
            return sec <= RECENT_EVENT_SECONDS;
        } catch (Exception e) {
            return false;
        }
    }

    private void createChannels() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;

        NotificationChannel monitor = new NotificationChannel(CH_MONITOR, "SignalHub tracker", NotificationManager.IMPORTANCE_LOW);
        monitor.setDescription("Persistent SignalHub multi-order tracking status");
        nm.createNotificationChannel(monitor);

        NotificationChannel signal = new NotificationChannel(CH_SIGNAL, "Signal & outcome alerts", NotificationManager.IMPORTANCE_HIGH);
        signal.setDescription("New MARKET/LIMIT/STOP, trigger and TP/SL outcome alerts");
        signal.enableVibration(true);
        nm.createNotificationChannel(signal);

        NotificationChannel update = new NotificationChannel(CH_UPDATE, "SignalHub app updates", NotificationManager.IMPORTANCE_DEFAULT);
        update.setDescription("Alerts when a newer SignalHub app version is available");
        nm.createNotificationChannel(update);
    }

    private PendingIntent openAppIntent() {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification monitorNotification(String text) {
        return new Notification.Builder(this, CH_MONITOR)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("SignalHub FX Tracker • LIVE")
                .setContentText(text)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(openAppIntent())
                .build();
    }

    private void notifyNewSignal(JSONObject s) {
        String order = s.optString("orderType", "MARKET");
        String status = s.optString("status", "OPEN");
        String title = "NEW " + order + " • " + s.optString("symbol", "—") + " • " + s.optString("side", "—") + " • " + s.optInt("score", 0) + "/100";
        String prefix = "PENDING".equals(status) ? "WAIT ENTRY " : "ENTRY ";
        String body = prefix + price(s.optDouble("entry", 0)) +
                " | SL " + price(s.optDouble("sl", 0)) +
                " | TP " + price(s.optDouble("tp", 0)) +
                " | RR " + String.format(Locale.US, "%.2f", s.optDouble("targetRR", 0));
        notifyHigh(title, body, s.optString("id", title) + ":new");
    }

    private void notifyTriggered(JSONObject s) {
        String title = "TRIGGERED • " + s.optString("orderType", "ORDER") + " • " + s.optString("symbol", "—") + " • " + s.optString("side", "—");
        String body = "Entry " + price(s.optDouble("entry", 0)) + " activated | SL " + price(s.optDouble("sl", 0)) + " | TP " + price(s.optDouble("tp", 0));
        notifyHigh(title, body, s.optString("id", title) + ":triggered");
    }

    private void notifyOutcome(JSONObject s) {
        String outcome = s.optString("outcome", "CLOSED");
        String icon = outcome.equals("TP") ? "✓" : outcome.equals("SL") ? "✕" : outcome.equals("AMBIGUOUS") ? "?" : "•";
        String title = icon + " " + outcome + " • " + s.optString("symbol", "—") + " • " + s.optString("orderType", "MARKET");
        Object rrObj = s.opt("resultR");
        String rr = rrObj == null || rrObj == JSONObject.NULL ? "N/A" : String.format(Locale.US, "%+.2fR", s.optDouble("resultR", 0));
        String body = rr + " | E " + price(s.optDouble("entry", 0)) + " → X " + price(s.optDouble("exitPrice", 0));
        notifyHigh(title, body, s.optString("id", title) + ":" + outcome);
    }

    private void notifyUpdate(JSONObject app) {
        String version = app.optString("versionName", "new");
        String title = "SignalHub update available • v" + version;
        String body = "A newer APK is available. Open SignalHub to see the update notice. Server-side signal history is preserved.";
        Notification n = new Notification.Builder(this, CH_UPDATE)
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(openAppIntent())
                .build();
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(7100 + (int)(app.optLong("versionCode", 0) % 700), n);
    }

    private void notifyHigh(String title, String body, String key) {
        Notification n = new Notification.Builder(this, CH_SIGNAL)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(openAppIntent())
                .build();
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(Math.abs(key.hashCode()), n);
    }

    private String price(double v) {
        if (!Double.isFinite(v) || v == 0) return "—";
        if (Math.abs(v) >= 1000) return String.format(Locale.US, "%.2f", v);
        if (Math.abs(v) >= 100) return String.format(Locale.US, "%.3f", v);
        if (Math.abs(v) >= 10) return String.format(Locale.US, "%.4f", v);
        return String.format(Locale.US, "%.5f", v);
    }

    private void sleep(long ms) {
        try { Thread.sleep(ms); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    @Override public void onDestroy() {
        running = false;
        if (worker != null) worker.shutdownNow();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
