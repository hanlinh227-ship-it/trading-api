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

import java.time.Instant;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MonitorService extends Service {
    private static final String CH_MONITOR="signalhub_monitor_v33", CH_SIGNAL="signalhub_signal_v33";
    private static final int FOREGROUND_ID=7201;
    private static final long LOOP_MS=2000L;
    private static final long RECENT_NEW_MS=10*60*1000L;
    private volatile boolean running;
    private ExecutorService worker;

    @Override public void onCreate(){
        super.onCreate();
        NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        if(n!=null){
            NotificationChannel a=new NotificationChannel(CH_MONITOR,"SignalHub live monitor",NotificationManager.IMPORTANCE_LOW);
            NotificationChannel b=new NotificationChannel(CH_SIGNAL,"SignalHub tín hiệu",NotificationManager.IMPORTANCE_HIGH);
            b.enableVibration(true);
            n.createNotificationChannel(a);n.createNotificationChannel(b);
        }
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId){
        startForeground(FOREGROUND_ID,monitor("Đang đồng bộ 4 luồng FOREX/CRYPTO • SCALP/SWING"));
        if(!running){running=true;worker=Executors.newSingleThreadExecutor();worker.execute(this::loop);}
        return START_STICKY;
    }

    private void loop(){
        while(running){
            long t=System.currentTimeMillis();
            try{syncAll();}catch(Throwable ignored){}
            try{Thread.sleep(Math.max(1000,LOOP_MS-(System.currentTimeMillis()-t)));}
            catch(InterruptedException e){Thread.currentThread().interrupt();break;}
        }
    }

    private void syncAll(){
        try{ApiClient.getLive("/v3/crypto/tickers?limit=1000");}catch(Throwable ignored){}
        int active=0,failed=0;
        for(String market:new String[]{"FOREX","CRYPTO"}){
            for(String style:new String[]{"SCALP","SWING"}){
                try{
                    JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market="+market+"&style="+style+"&status=all&limit=120"));
                    JSONArray a=root.optJSONArray("signals");
                    String dataState="";
                    JSONObject health=root.optJSONObject("dataHealth");
                    if(health!=null)dataState=health.optString("state","");
                    if(a!=null)for(int i=0;i<a.length();i++){
                        JSONObject s=a.optJSONObject(i);if(s==null)continue;
                        String st=s.optString("status","");
                        if("PENDING".equals(st)||"OPEN".equals(st))active++;
                        process(market,style,s,dataState);
                    }
                }catch(Throwable e){failed++;}
            }
        }
        NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        if(n!=null){
            String text=failed==0?"LIVE • "+active+" tín hiệu đang theo dõi":"DEGRADED • "+failed+"/4 luồng đang nối lại • "+active+" active";
            n.notify(FOREGROUND_ID,monitor(text));
        }
    }

    private void process(String market,String style,JSONObject s,String dataState){
        String id=s.optString("signalId",s.optString("id",""));if(id.isEmpty())return;
        String state=s.optString("status","")+":"+s.optString("outcome","")+":"+s.optBoolean("brokerConfirmed",false);
        SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);
        String key="state_"+id,old=p.getString(key,null);
        if(old==null){
            p.edit().putString(key,state).apply();
            if(isRecent(s.optString("issuedAt","")))notifySignal("MỚI",market,style,s,dataState,id+":new");
            return;
        }
        if(old.equals(state))return;
        p.edit().putString(key,state).apply();
        String status=s.optString("status","");
        String outcome=s.optString("outcome","");
        if("OPEN".equals(status))notifySignal(s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP EXNESS":"ACTIVE",market,style,s,dataState,id+":open");
        else if("CLOSED".equals(status)&&"TP".equals(outcome))notifySignal("TP ĐẠT",market,style,s,dataState,id+":tp");
        else if("CLOSED".equals(status)&&"SL".equals(outcome))notifySignal("SL CHẠM",market,style,s,dataState,id+":sl");
        else if("CANCELLED".equals(status))notifySignal("ĐÃ HỦY / SETUP MẤT HIỆU LỰC",market,style,s,dataState,id+":cancel");
    }

    private void notifySignal(String event,String market,String style,JSONObject s,String dataState,String key){
        String side=sideVi(s.optString("side","—")),symbol=s.optString("symbol","—");
        String title=style+" • "+symbol+" • "+side+" • "+event;
        StringBuilder b=new StringBuilder();
        b.append("ENTRY ").append(price(s.optDouble("entry",0))).append("  |  SL ").append(price(s.optDouble("sl",0)));
        double tp1=s.optDouble("tp1",0),tp2=s.optDouble("tp2",0),tp3=s.optDouble("tp3",s.optDouble("tp",0));
        if(tp1>0)b.append("\nTP1 ").append(price(tp1));
        if(tp2>0)b.append("  |  TP2 ").append(price(tp2));
        if(tp3>0)b.append("  |  TP3 ").append(price(tp3));
        b.append("\n").append(market).append(" • ").append(s.optString("orderType","MARKET"));
        if(!dataState.isEmpty())b.append(" • ").append(dataState);
        String regime=s.optString("marketRegime","").replace('_',' ');if(!regime.isEmpty())b.append(" • ").append(regime);
        appendHistory(title,b.toString());
        notifyHigh(title,b.toString(),key);
    }


    private void appendHistory(String title,String body){
        try{
            SharedPreferences p=getSharedPreferences("signalhub_v32",MODE_PRIVATE);
            JSONArray old=new JSONArray(p.getString("alert_history_v33","[]"));
            JSONArray out=new JSONArray();
            JSONObject now=new JSONObject();now.put("ts",System.currentTimeMillis());now.put("title",title);now.put("body",body);out.put(now);
            for(int i=0;i<old.length()&&i<49;i++)out.put(old.opt(i));
            p.edit().putString("alert_history_v33",out.toString()).apply();
        }catch(Throwable ignored){}
    }

    private Notification monitor(String text){
        return new Notification.Builder(this,CH_MONITOR)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("SignalHub V3.9 • CLEAN STORY LIVE")
                .setContentText(text).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(open()).build();
    }

    private PendingIntent open(){
        Intent i=new Intent(this,MainActivity.class);
        return PendingIntent.getActivity(this,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }

    private void notifyHigh(String title,String body,String key){
        Notification n=new Notification.Builder(this,CH_SIGNAL)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setAutoCancel(true).setContentIntent(open()).build();
        NotificationManager m=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        if(m!=null)m.notify(Math.abs(key.hashCode()),n);
    }

    private boolean isRecent(String iso){
        try{return Math.abs(System.currentTimeMillis()-Instant.parse(iso).toEpochMilli())<=RECENT_NEW_MS;}
        catch(Exception e){return false;}
    }
    private String sideVi(String s){String x=s.toUpperCase(Locale.US);return (x.equals("LONG")||x.equals("BUY"))?"BUY":(x.equals("SHORT")||x.equals("SELL"))?"SELL":x;}
    private String price(double v){if(v<=0)return"—";if(v>=1000)return String.format(Locale.US,"%.2f",v);if(v>=100)return String.format(Locale.US,"%.3f",v);if(v>=10)return String.format(Locale.US,"%.4f",v);return String.format(Locale.US,"%.5f",v);}
    @Override public void onDestroy(){running=false;if(worker!=null)worker.shutdownNow();super.onDestroy();}
    @Override public IBinder onBind(Intent i){return null;}
}
