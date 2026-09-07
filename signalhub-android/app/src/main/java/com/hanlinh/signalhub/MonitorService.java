package com.hanlinh.signalhub;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.IBinder;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MonitorService extends Service {
    private static final String CH_MONITOR = "signalhub_monitor";
    private static final String CH_SIGNAL = "signalhub_signal";
    private static final int FOREGROUND_ID = 7001;
    private volatile boolean running;
    private ExecutorService worker;

    @Override public void onCreate() { super.onCreate(); createChannels(); }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        try { startForeground(FOREGROUND_ID, monitorNotification("Live scan • Forex / Metal / Brent Oil")); }
        catch (Throwable e) {
            getSharedPreferences("signalhub", MODE_PRIVATE).edit().putBoolean("monitoring", false).apply();
            stopSelf(); return START_NOT_STICKY;
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
            scanGroup("forex"); sleep(20000); if (!running) break;
            scanGroup("metal"); sleep(20000); if (!running) break;
            scanGroup("energy"); sleep(260000);
        }
    }

    private void scanGroup(String group) {
        try {
            String raw = ApiClient.get("/run-now?group=" + group);
            SignalFormatter.Hit hit = SignalFormatter.bestHit(group, raw);
            if (hit == null) return;
            SharedPreferences p = getSharedPreferences("signalhub", MODE_PRIVATE);
            String last = p.getString("last_hit_" + group, "");
            if (hit.key().equals(last)) return;
            p.edit().putString("last_hit_" + group, hit.key()).apply();
            notifyHit(hit);
        } catch (Throwable ignored) {
            // Fail closed: no stale signal and no service crash.
        }
    }

    private void createChannels() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;
        NotificationChannel monitor = new NotificationChannel(CH_MONITOR, "SignalHub monitor", NotificationManager.IMPORTANCE_LOW);
        monitor.setDescription("Persistent status for Forex/metal/oil signal scanning"); nm.createNotificationChannel(monitor);
        NotificationChannel signal = new NotificationChannel(CH_SIGNAL, "Trading signals", NotificationManager.IMPORTANCE_HIGH);
        signal.setDescription("Fresh MARKET_SIGNAL alerts"); signal.enableVibration(true); nm.createNotificationChannel(signal);
    }

    private PendingIntent openAppIntent() {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification monitorNotification(String text) {
        return new Notification.Builder(this, CH_MONITOR)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("SignalHub FX • LIVE")
                .setContentText(text).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(openAppIntent()).build();
    }

    private void notifyHit(SignalFormatter.Hit h) {
        Notification n = new Notification.Builder(this, CH_SIGNAL)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle(h.title()).setContentText(h.text())
                .setStyle(new Notification.BigTextStyle().bigText(h.group.toUpperCase() + " • " + h.text()))
                .setAutoCancel(true).setContentIntent(openAppIntent()).build();
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(Math.abs(h.key().hashCode()), n);
    }

    private void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } }
    @Override public void onDestroy() { running = false; if (worker != null) worker.shutdownNow(); super.onDestroy(); }
    @Override public IBinder onBind(Intent intent) { return null; }
}
