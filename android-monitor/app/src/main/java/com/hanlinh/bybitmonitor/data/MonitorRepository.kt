package com.hanlinh.bybitmonitor.data

import android.content.Context
import com.hanlinh.bybitmonitor.BuildConfig
import com.hanlinh.bybitmonitor.model.MonitorSnapshot
import com.hanlinh.bybitmonitor.network.MonitorApi
import com.hanlinh.bybitmonitor.security.SecureTokenStore
import kotlinx.coroutines.*
import okhttp3.WebSocket

class MonitorRepository(context:Context) {
    private val app=context.applicationContext
    private val tokenStore=SecureTokenStore(app)
    private val api=MonitorApi(BuildConfig.DEFAULT_BASE_URL)
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    private var ws:WebSocket?=null
    private var stopped=true
    private var attempt=0
    private var snapshotCb:((MonitorSnapshot)->Unit)?=null
    private var statusCb:((String)->Unit)?=null
    fun hasToken()=!tokenStore.load().isNullOrBlank()
    suspend fun pair(code:String,deviceName:String)=withContext(Dispatchers.IO){val token=api.pair(code,deviceName);tokenStore.save(token)}
    suspend fun fetchSnapshot():MonitorSnapshot=withContext(Dispatchers.IO){api.snapshot(tokenStore.load()?:throw IllegalStateException("MONITOR_TOKEN_MISSING"))}
    fun clearToken(){stopRealtime();tokenStore.clear()}
    fun startRealtime(onSnapshot:(MonitorSnapshot)->Unit,onStatus:(String)->Unit){snapshotCb=onSnapshot;statusCb=onStatus;stopped=false;attempt=0;connect()}
    private fun connect(){if(stopped)return;val token=tokenStore.load()?:return;statusCb?.invoke("CONNECTING");ws=api.webSocket(token,{attempt=0;snapshotCb?.invoke(it)},{statusCb?.invoke(it)}){if(!stopped){attempt=(attempt+1).coerceAtMost(6);val delayMs=(1000L shl attempt.coerceAtMost(4)).coerceAtMost(15000L);scope.launch{delay(delayMs);connect()}}}}
    fun stopRealtime(){stopped=true;ws?.close(1000,"client stop");ws=null}
}
