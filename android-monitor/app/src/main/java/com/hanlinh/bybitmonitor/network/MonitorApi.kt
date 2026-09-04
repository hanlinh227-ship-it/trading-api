package com.hanlinh.bybitmonitor.network

import com.hanlinh.bybitmonitor.model.MonitorSnapshot
import com.hanlinh.bybitmonitor.model.TelemetryParser
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class MonitorApi(private val baseUrl:String) {
    private val jsonType="application/json; charset=utf-8".toMediaType()
    val client=OkHttpClient.Builder().connectTimeout(15,TimeUnit.SECONDS).readTimeout(25,TimeUnit.SECONDS).writeTimeout(15,TimeUnit.SECONDS).pingInterval(20,TimeUnit.SECONDS).build()
    private fun url(path:String)=baseUrl.trimEnd('/')+path
    fun pair(pairingCode:String,deviceName:String):String {
        val body=JSONObject().put("pairingCode",pairingCode.trim().uppercase()).put("deviceName",deviceName.trim().ifBlank{"Android Monitor"}).toString().toRequestBody(jsonType)
        val req=Request.Builder().url(url("/bybit/monitor/pair")).post(body).build()
        client.newCall(req).execute().use{r->val text=r.body?.string().orEmpty();val j=runCatching{JSONObject(text)}.getOrNull();if(!r.isSuccessful||j?.optBoolean("ok")!=true)throw IllegalStateException(j?.optString("error")?:"PAIR_HTTP_${r.code}");return j.getString("token")}
    }
    fun snapshot(token:String):MonitorSnapshot {
        val req=Request.Builder().url(url("/bybit/monitor/snapshot")).header("Authorization","Bearer $token").get().build()
        client.newCall(req).execute().use{r->val text=r.body?.string().orEmpty();val j=runCatching{JSONObject(text)}.getOrNull();if(!r.isSuccessful||j?.optBoolean("ok")!=true)throw IllegalStateException(j?.optString("error")?:"SNAPSHOT_HTTP_${r.code}");return TelemetryParser.parse(j)}
    }
    fun webSocket(token:String,onSnapshot:(MonitorSnapshot)->Unit,onStatus:(String)->Unit,onTerminal:(Throwable?)->Unit):WebSocket {
        val wsBase=baseUrl.trimEnd('/').replaceFirst("https://","wss://").replaceFirst("http://","ws://")
        val req=Request.Builder().url("$wsBase/bybit/monitor/ws").header("Authorization","Bearer $token").build()
        return client.newWebSocket(req,object:WebSocketListener(){
            override fun onOpen(webSocket:WebSocket,response:Response){onStatus("CONNECTED");webSocket.send(JSONObject().put("type","subscribe").put("intervalMs",2000).toString())}
            override fun onMessage(webSocket:WebSocket,text:String){runCatching{val e=JSONObject(text);if(e.optString("type")=="snapshot")onSnapshot(TelemetryParser.parse(e.getJSONObject("data")))}.onFailure{onStatus("PARSE_ERROR")}}
            override fun onClosing(webSocket:WebSocket,code:Int,reason:String){onStatus("CLOSING");webSocket.close(code,reason)}
            override fun onClosed(webSocket:WebSocket,code:Int,reason:String){onStatus("DISCONNECTED");onTerminal(null)}
            override fun onFailure(webSocket:WebSocket,t:Throwable,response:Response?){onStatus("DISCONNECTED");onTerminal(t)}
        })
    }
}
