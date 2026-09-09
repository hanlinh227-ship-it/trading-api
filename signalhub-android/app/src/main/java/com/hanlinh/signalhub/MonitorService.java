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
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MonitorService extends Service {
    private static final String CH_MONITOR="signalhub_monitor", CH_SIGNAL="signalhub_signal";
    private static final int FOREGROUND_ID=7001;
    private volatile boolean running; private ExecutorService worker;
    @Override public void onCreate(){super.onCreate();NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(n!=null){NotificationChannel a=new NotificationChannel(CH_MONITOR,"SignalHub live monitor",NotificationManager.IMPORTANCE_LOW);NotificationChannel b=new NotificationChannel(CH_SIGNAL,"SignalHub tín hiệu",NotificationManager.IMPORTANCE_HIGH);b.enableVibration(true);n.createNotificationChannel(a);n.createNotificationChannel(b);}}
    @Override public int onStartCommand(Intent intent,int flags,int startId){startForeground(FOREGROUND_ID,monitor("Đang theo dõi Forex + Crypto • Scalp + Swing"));if(!running){running=true;worker=Executors.newSingleThreadExecutor();worker.execute(this::loop);}return START_STICKY;}
    private void loop(){while(running){long t=System.currentTimeMillis();try{syncAll();}catch(Throwable ignored){}try{Thread.sleep(Math.max(1000,5000-(System.currentTimeMillis()-t)));}catch(InterruptedException e){Thread.currentThread().interrupt();break;}}}
    private void syncAll() throws Exception {int active=0;for(String m:new String[]{"FOREX","CRYPTO"})for(String s:new String[]{"SCALP","SWING"}){JSONObject root=new JSONObject(ApiClient.get("/v3/signals?market="+m+"&style="+s+"&status=active&limit=100"));JSONArray a=root.optJSONArray("signals");active+=a==null?0:a.length();if(a!=null)for(int i=0;i<a.length();i++){JSONObject x=a.optJSONObject(i);if(x!=null)process(m,s,x);}}NotificationManager n=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(n!=null)n.notify(FOREGROUND_ID,monitor("LIVE • "+active+" tín hiệu đang theo dõi"));}
    private void process(String market,String style,JSONObject s){String id=s.optString("id","");if(id.isEmpty())return;String state=s.optString("status","")+":"+s.optString("outcome","")+":"+s.optBoolean("brokerConfirmed",false);SharedPreferences p=getSharedPreferences("signalhub",MODE_PRIVATE);String key="v31_state_"+id,old=p.getString(key,null);if(old==null){p.edit().putString(key,state).apply();notifyHigh("TÍN HIỆU MỚI • "+s.optString("symbol","—"),market+" "+style+" • "+s.optString("side","—")+" "+s.optString("orderType","MARKET")+" • Entry "+price(s.optDouble("entry",0)),id+":new");return;}if(!old.equals(state)){p.edit().putString(key,state).apply();if(old.startsWith("PENDING")&&state.startsWith("OPEN"))notifyHigh(s.optBoolean("brokerConfirmed",false)?"ĐÃ KHỚP EXNESS":"ĐÃ KÍCH HOẠT",s.optString("symbol","—")+" • Entry "+price(s.optDouble("entry",0)),id+":fill");}}
    private Notification monitor(String text){return new Notification.Builder(this,CH_MONITOR).setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("SignalHub • LIVE").setContentText(text).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(open()).build();}
    private PendingIntent open(){Intent i=new Intent(this,MainActivity.class);return PendingIntent.getActivity(this,0,i,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
    private void notifyHigh(String title,String body,String key){Notification n=new Notification.Builder(this,CH_SIGNAL).setSmallIcon(android.R.drawable.stat_sys_warning).setContentTitle(title).setContentText(body).setAutoCancel(true).setContentIntent(open()).build();NotificationManager m=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);if(m!=null)m.notify(Math.abs(key.hashCode()),n);}
    private String price(double v){if(v<=0)return"—";if(v>=1000)return String.format(Locale.US,"%.2f",v);if(v>=100)return String.format(Locale.US,"%.3f",v);return String.format(Locale.US,"%.5f",v);}
    @Override public void onDestroy(){running=false;if(worker!=null)worker.shutdownNow();super.onDestroy();}
    @Override public IBinder onBind(Intent i){return null;}
}
