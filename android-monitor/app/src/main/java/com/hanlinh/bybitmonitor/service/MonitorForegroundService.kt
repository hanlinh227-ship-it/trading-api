package com.hanlinh.bybitmonitor.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.hanlinh.bybitmonitor.MainActivity
import com.hanlinh.bybitmonitor.R
import com.hanlinh.bybitmonitor.data.MonitorRepository
import com.hanlinh.bybitmonitor.model.MonitorSnapshot
import com.hanlinh.bybitmonitor.widget.WidgetStateStore
import java.util.concurrent.atomic.AtomicBoolean

class MonitorForegroundService:Service(){
    private lateinit var repo:MonitorRepository
    private val seeded=AtomicBoolean(false)
    private var previousSymbols=emptySet<String>()
    private var previousHealth=""
    override fun onCreate(){super.onCreate();createChannels();repo=MonitorRepository(this);startForeground(ONGOING_ID,ongoing("Đang kết nối telemetry…"));if(repo.hasToken())repo.startRealtime(::handle,{}) else stopSelf()}
    private fun handle(s:MonitorSnapshot){WidgetStateStore.save(this,s);WidgetStateStore.updateAll(this);val text="Equity $" + "%.2f".format(s.account.equity) + " · PnL " + "%+.2f".format(s.account.unrealizedPnl) + " · ${s.connection.ws.freshCount}/${s.connection.ws.symbolCount} fresh";getSystemService(NotificationManager::class.java).notify(ONGOING_ID,ongoing(text));val now=s.positions.map{it.symbol}.toSet();val health=s.bot.status+":"+s.connection.ws.status;if(seeded.getAndSet(true)){(now-previousSymbols).forEach{alert("Mở vị thế $it","Bot vừa ghi nhận vị thế mới")};(previousSymbols-now).forEach{alert("Đóng vị thế $it","Vị thế đã rời danh sách mở")};if(health!=previousHealth&&(s.bot.status.contains("DEGRADED")||s.connection.ws.status!="HEALTHY"))alert("Telemetry cần chú ý",health)};previousSymbols=now;previousHealth=health}
    private fun pending():PendingIntent=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    private fun ongoing(text:String)=NotificationCompat.Builder(this,CH_LIVE).setSmallIcon(R.drawable.ic_monitor).setContentTitle("Bybit Monitor · Read only").setContentText(text).setContentIntent(pending()).setOnlyAlertOnce(true).setOngoing(true).build()
    private fun alert(title:String,text:String){getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis()%100000).toInt()+200,NotificationCompat.Builder(this,CH_ALERT).setSmallIcon(R.drawable.ic_monitor).setContentTitle(title).setContentText(text).setContentIntent(pending()).setAutoCancel(true).build())}
    private fun createChannels(){val m=getSystemService(NotificationManager::class.java);m.createNotificationChannel(NotificationChannel(CH_LIVE,"Monitor realtime",NotificationManager.IMPORTANCE_LOW));m.createNotificationChannel(NotificationChannel(CH_ALERT,"Cảnh báo bot",NotificationManager.IMPORTANCE_DEFAULT))}
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int)=START_STICKY
    override fun onDestroy(){repo.stopRealtime();super.onDestroy()}
    override fun onBind(intent:Intent?):IBinder?=null
    companion object{const val CH_LIVE="bybit_monitor_live";const val CH_ALERT="bybit_monitor_alert";const val ONGOING_ID=101;fun setEnabled(c:Context,on:Boolean){c.getSharedPreferences("monitor_settings",Context.MODE_PRIVATE).edit().putBoolean("background",on).apply();if(on)androidx.core.content.ContextCompat.startForegroundService(c,Intent(c,MonitorForegroundService::class.java)) else c.stopService(Intent(c,MonitorForegroundService::class.java))};fun isEnabled(c:Context)=c.getSharedPreferences("monitor_settings",Context.MODE_PRIVATE).getBoolean("background",false)}
}
