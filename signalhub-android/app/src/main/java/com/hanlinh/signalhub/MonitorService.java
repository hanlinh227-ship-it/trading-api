package com.hanlinh.signalhub;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
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
    private static final int FOREGROUND_ID = 7001;
    private static final long LOOP_MS = 5000L;
    private static final long RECENT_EVENT_SECONDS = 20 * 60L;

    private volatile boolean running;
    private ExecutorService worker;
    private long lastSummaryAt;

    @Override public void onCreate() {
        super.onCreate();
        createChannels();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        try {
            startForeground(FOREGROUND_ID, monitorNotification("Đang đồng bộ tín hiệu • Exness fill theo thời gian thực"));
        } catch (Throwable e) {
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
            long started = System.currentTimeMillis();
            syncSignals();
            syncBrokerEvent();
            if (started - lastSummaryAt >= 60000L) {
                updateForegroundSummary();
                lastSummaryAt = started;
            }
            long wait = Math.max(1000L, LOOP_MS - (System.currentTimeMillis() - started));
            sleep(wait);
        }
    }

    private void syncSignals() {
        try {
            JSONObject root = new JSONObject(ApiClient.get("/signals?limit=200"));
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
                boolean broker = s.optBoolean("brokerConfirmed", false);
                String currentState = status + ":" + outcome + ":" + orderType + ":" + broker;
                String key = "tracker_state_" + id;
                String previous = p.getString(key, null);
                if (previous == null) {
                    p.edit().putString(key, currentState).apply();
                    if (("PENDING".equals(status) || "OPEN".equals(status)) && isRecent(s.optString("issuedAt", ""))) notifyNewSignal(s);
                    else if ("CLOSED".equals(status) && isRecent(s.optString("closedAt", ""))) notifyOutcome(s);
                    continue;
                }
                if (!previous.equals(currentState)) {
                    p.edit().putString(key, currentState).apply();
                    boolean wasPending = previous.startsWith("PENDING:");
                    if (wasPending && "OPEN".equals(status)) notifyTriggered(s, broker);
                    else if ("CLOSED".equals(status)) notifyOutcome(s);
                }
            }
        } catch (Throwable ignored) {}
    }

    private void syncBrokerEvent() {
        try {
            JSONObject live = new JSONObject(ApiClient.get("/v3/forex/live"));
            JSONObject e = live.optJSONObject("lastEvent");
            if (e == null) return;
            String type=e.optString("event","");
            String signalId=e.optString("signalId","");
            String at=e.optString("receivedAt","");
            String fp=type+":"+signalId+":"+at+":"+e.optString("brokerSymbol","");
            if (type.isEmpty() || at.isEmpty()) return;
            SharedPreferences p=getSharedPreferences("signalhub",MODE_PRIVATE);
            if (fp.equals(p.getString("last_broker_event_fp",""))) return;
            p.edit().putString("last_broker_event_fp",fp).apply();
            if ("BROKER_FILL_CONFIRMED".equals(type)) {
                String symbol=e.optString("brokerSymbol","—");
                String body="Exness xác nhận deal thật tại "+price(e.optDouble("price",0))+" • Signal "+(signalId.isEmpty()?"—":signalId);
                notifyHigh("ĐÃ KHỚP • "+symbol,body,fp);
            }
        } catch(Throwable ignored) {}
    }

    private void updateForegroundSummary() {
        try {
            JSONObject p = new JSONObject(ApiClient.get("/performance")).optJSONObject("performance");
            JSONObject live;
            try { live=new JSONObject(ApiClient.get("/v3/forex/live")); } catch(Throwable e){ live=null; }
            String fx = live==null?"OFFLINE":live.optString("state","OFFLINE");
            String text;
            if (p != null) text=String.format(Locale.US,"Exness %s • Active %d • Pending %d • WR %.1f%% • Net %+.2fR",fx,p.optInt("active",p.optInt("open",0)),p.optInt("pending",0),p.optDouble("winRateResolved",0),p.optDouble("netRResolved",0));
            else text="Exness "+fx+" • đang theo dõi tín hiệu";
            NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
            if(nm!=null) nm.notify(FOREGROUND_ID,monitorNotification(text));
        } catch(Throwable ignored) {}
    }

    private boolean isRecent(String iso) {
        try { return Math.abs(Duration.between(Instant.parse(iso), Instant.now()).getSeconds()) <= RECENT_EVENT_SECONDS; }
        catch (Exception e) { return false; }
    }

    private void createChannels() {
        NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        if(nm==null)return;
        NotificationChannel monitor=new NotificationChannel(CH_MONITOR,"SignalHub live monitor",NotificationManager.IMPORTANCE_LOW);
        monitor.setDescription("Trạng thái kết nối SignalHub / Exness / Bybit"); nm.createNotificationChannel(monitor);
        NotificationChannel signal=new NotificationChannel(CH_SIGNAL,"SignalHub tín hiệu",NotificationManager.IMPORTANCE_HIGH);
        signal.setDescription("Tín hiệu mới, LIMIT/STOP đã khớp và kết quả TP/SL"); signal.enableVibration(true); nm.createNotificationChannel(signal);
    }

    private PendingIntent openAppIntent() {
        Intent open=new Intent(this,MainActivity.class); open.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification monitorNotification(String text) {
        return new Notification.Builder(this,CH_MONITOR).setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("SignalHub • LIVE").setContentText(text).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(openAppIntent()).build();
    }

    private void notifyNewSignal(JSONObject s) {
        String order=s.optString("orderType","MARKET"),status=s.optString("status","OPEN"),symbol=s.optString("symbol","—"),side=s.optString("side","—");
        String title=("PENDING".equals(status)?"LỆNH CHỜ ":"TÍN HIỆU ")+order+" • "+symbol+" • "+side;
        String body="Entry "+price(s.optDouble("entry",0))+" • TP "+price(s.optDouble("tp",0))+" • SL "+price(s.optDouble("sl",0));
        notifyHigh(title,body,s.optString("id",title)+":new");
    }

    private void notifyTriggered(JSONObject s,boolean broker) {
        String prefix=broker?"ĐÃ KHỚP EXNESS":"ĐÃ KÍCH HOẠT";
        String title=prefix+" • "+s.optString("symbol","—")+" • "+s.optString("side","—");
        String body="Entry "+price(s.optDouble("entry",0))+" • TP "+price(s.optDouble("tp",0))+" • SL "+price(s.optDouble("sl",0));
        notifyHigh(title,body,s.optString("id",title)+":triggered");
    }

    private void notifyOutcome(JSONObject s) {
        String out=s.optString("outcome","CLOSED"); int col=out.equals("TP")?1:out.equals("SL")?-1:0;
        String title=(col>0?"✓ ":col<0?"✕ ":"• ")+out+" • "+s.optString("symbol","—");
        Object rr=s.opt("resultR"); String result=rr==null||rr==JSONObject.NULL?"—":String.format(Locale.US,"%+.2fR",s.optDouble("resultR",0));
        notifyHigh(title,result+" • Exit "+price(s.optDouble("exitPrice",0)),s.optString("id",title)+":"+out);
    }

    private void notifyHigh(String title,String body,String key) {
        Notification n=new Notification.Builder(this,CH_SIGNAL).setSmallIcon(android.R.drawable.stat_sys_warning).setContentTitle(title).setContentText(body).setStyle(new Notification.BigTextStyle().bigText(body)).setAutoCancel(true).setContentIntent(openAppIntent()).build();
        NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE); if(nm!=null)nm.notify(Math.abs(key.hashCode()),n);
    }

    private String price(double v) {
        if(!Double.isFinite(v)||v==0)return "—";
        if(Math.abs(v)>=1000)return String.format(Locale.US,"%.2f",v);
        if(Math.abs(v)>=100)return String.format(Locale.US,"%.3f",v);
        if(Math.abs(v)>=10)return String.format(Locale.US,"%.4f",v);
        return String.format(Locale.US,"%.5f",v);
    }

    private void sleep(long ms){try{Thread.sleep(ms);}catch(InterruptedException e){Thread.currentThread().interrupt();}}
    @Override public void onDestroy(){running=false;if(worker!=null)worker.shutdownNow();super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
