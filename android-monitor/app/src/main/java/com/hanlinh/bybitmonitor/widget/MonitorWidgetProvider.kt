package com.hanlinh.bybitmonitor.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import androidx.work.*
import com.hanlinh.bybitmonitor.MainActivity
import com.hanlinh.bybitmonitor.R
import com.hanlinh.bybitmonitor.model.MonitorSnapshot
import java.util.concurrent.TimeUnit

object WidgetStateStore{
    private const val P="monitor_widget_state"
    fun save(c:Context,s:MonitorSnapshot){c.getSharedPreferences(P,Context.MODE_PRIVATE).edit().putFloat("equity",s.account.equity.toFloat()).putFloat("pnl",s.account.unrealizedPnl.toFloat()).putString("status",s.bot.status).putString("ws",s.connection.ws.status).putInt("fresh",s.connection.ws.freshCount).putInt("total",s.connection.ws.symbolCount).apply()}
    fun render(c:Context):RemoteViews{val p=c.getSharedPreferences(P,Context.MODE_PRIVATE);val equity=p.getFloat("equity",0f);val pnl=p.getFloat("pnl",0f);val status=p.getString("status","OFFLINE")?:"OFFLINE";val ws=p.getString("ws","DOWN")?:"DOWN";val fresh=p.getInt("fresh",0);val total=p.getInt("total",0);return RemoteViews(c.packageName,R.layout.widget_monitor).apply{setTextViewText(R.id.widget_equity,"$"+String.format("%.2f",equity));setTextViewText(R.id.widget_pnl,"PnL "+String.format("%+.2f",pnl));setTextViewText(R.id.widget_status,status);setTextViewText(R.id.widget_ws,"WS $ws · $fresh/$total fresh");val pi=PendingIntent.getActivity(c,0,Intent(c,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT);setOnClickPendingIntent(R.id.widget_equity,pi)}}
    fun updateAll(c:Context){val m=AppWidgetManager.getInstance(c);val cn=ComponentName(c,MonitorWidgetProvider::class.java);m.updateAppWidget(cn,render(c))}
}
class MonitorWidgetProvider:AppWidgetProvider(){
    override fun onUpdate(context:Context,manager:AppWidgetManager,ids:IntArray){ids.forEach{manager.updateAppWidget(it,WidgetStateStore.render(context))};WorkManager.getInstance(context).enqueue(OneTimeWorkRequestBuilder<WidgetRefreshWorker>().build())}
    override fun onEnabled(context:Context){val req=PeriodicWorkRequestBuilder<WidgetRefreshWorker>(15,TimeUnit.MINUTES).setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build();WorkManager.getInstance(context).enqueueUniquePeriodicWork("bybit-monitor-widget",ExistingPeriodicWorkPolicy.UPDATE,req)}
    override fun onDisabled(context:Context){WorkManager.getInstance(context).cancelUniqueWork("bybit-monitor-widget")}
}
