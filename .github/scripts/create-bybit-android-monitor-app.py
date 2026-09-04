from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'android-monitor'
files={
'settings.gradle.kts':r'''pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "BybitAndroidMonitor"
include(":app")
''',
'build.gradle.kts':r'''plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}
''',
'gradle.properties':r'''org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
''',
'app/build.gradle.kts':r'''plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.hanlinh.bybitmonitor"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.hanlinh.bybitmonitor"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        buildConfigField("String", "DEFAULT_BASE_URL", "\"https://trading-v77-scanner.hanlinh227.workers.dev\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
''',
'app/proguard-rules.pro':r'''# No reflection-based serializers are used.
''',
'app/src/main/AndroidManifest.xml':r'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />

    <application
        android:allowBackup="false"
        android:icon="@drawable/ic_monitor"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.BybitMonitor"
        android:usesCleartextTraffic="false">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <service
            android:name=".service.MonitorForegroundService"
            android:exported="false"
            android:foregroundServiceType="dataSync" />
        <receiver
            android:name=".widget.MonitorWidgetProvider"
            android:exported="true">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
            </intent-filter>
            <meta-data
                android:name="android.appwidget.provider"
                android:resource="@xml/bybit_monitor_widget_info" />
        </receiver>
    </application>
</manifest>
''',
'app/src/main/res/values/strings.xml':r'''<resources>
    <string name="app_name">Bybit Monitor</string>
    <string name="widget_description">Theo dõi bot Bybit realtime</string>
</resources>
''',
'app/src/main/res/values/themes.xml':r'''<resources xmlns:tools="http://schemas.android.com/tools">
    <style name="Theme.BybitMonitor" parent="android:style/Theme.Material.Light.NoActionBar">
        <item name="android:fontFamily">sans</item>
        <item name="android:windowLightStatusBar">true</item>
        <item name="android:navigationBarColor">#F5F7FA</item>
        <item name="android:statusBarColor">#F5F7FA</item>
    </style>
</resources>
''',
'app/src/main/res/drawable/ic_monitor.xml':r'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="48dp" android:height="48dp" android:viewportWidth="48" android:viewportHeight="48">
    <path android:fillColor="#111827" android:pathData="M6,8h36v32h-36z" />
    <path android:fillColor="#FFFFFF" android:pathData="M10,29l7,-8 6,5 8,-12 7,6v5l-7,-5 -7,11 -7,-5 -7,8z" />
</vector>
''',
'app/src/main/res/drawable/widget_bg.xml':r'''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#F8FAFC" />
    <corners android:radius="20dp" />
    <stroke android:width="1dp" android:color="#DCE2EA" />
</shape>
''',
'app/src/main/res/layout/widget_monitor.xml':r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:orientation="vertical" android:padding="14dp" android:background="@drawable/widget_bg">
    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal">
        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="BYBIT MONITOR" android:textStyle="bold" android:textColor="#111827" android:textSize="12sp" />
        <TextView android:id="@+id/widget_status" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="OFFLINE" android:textStyle="bold" android:textColor="#6B7280" android:textSize="11sp" />
    </LinearLayout>
    <TextView android:id="@+id/widget_equity" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="$--" android:textColor="#111827" android:textStyle="bold" android:textSize="26sp" />
    <TextView android:id="@+id/widget_pnl" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="PnL --" android:textColor="#374151" android:textSize="13sp" />
    <TextView android:id="@+id/widget_ws" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="4dp" android:text="WS --" android:textColor="#6B7280" android:textSize="11sp" />
</LinearLayout>
''',
'app/src/main/res/xml/bybit_monitor_widget_info.xml':r'''<?xml version="1.0" encoding="utf-8"?>
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:minWidth="220dp" android:minHeight="110dp"
    android:updatePeriodMillis="0"
    android:initialLayout="@layout/widget_monitor"
    android:resizeMode="horizontal|vertical"
    android:widgetCategory="home_screen"
    android:description="@string/widget_description" />
''',
'app/src/main/java/com/hanlinh/bybitmonitor/model/Telemetry.kt':r'''package com.hanlinh.bybitmonitor.model

import org.json.JSONArray
import org.json.JSONObject

data class BotTelemetry(val status:String="OFFLINE",val ready:Boolean=false,val mode:String="",val version:String="",val lastCycleAt:String?=null,val lastCycleReason:String?=null)
data class AccountTelemetry(val equity:Double=0.0,val balance:Double=0.0,val availableBalance:Double=0.0,val unrealizedPnl:Double=0.0,val realizedPnl:Double=0.0,val realizedPnl72h:Double=0.0)
data class PerformanceWindow(val closedRecords:Int=0,val wins:Int=0,val losses:Int=0,val winRatePct:Double=0.0,val realizedPnl:Double=0.0,val profitFactor:Double=0.0,val expectancy:Double=0.0)
data class PerformanceTelemetry(val winRatePct:Double=0.0,val realizedPnl:Double=0.0,val h24:PerformanceWindow=PerformanceWindow(),val h72:PerformanceWindow=PerformanceWindow())
data class PositionTelemetry(val symbol:String="",val side:String="",val size:Double=0.0,val entryPrice:Double=0.0,val markPrice:Double=0.0,val unrealizedPnl:Double=0.0,val roePct:Double?=null,val leverage:Double=0.0,val tp:Double=0.0,val sl:Double=0.0,val liqPrice:Double=0.0,val positionValue:Double=0.0,val positionMargin:Double=0.0)
data class PositionsSummary(val openCount:Int=0,val longCount:Int=0,val shortCount:Int=0,val longNotional:Double=0.0,val shortNotional:Double=0.0,val totalUnrealizedPnl:Double=0.0)
data class ScannerItem(val symbol:String="",val classification:String="",val reason:String?=null,val eligible:Boolean=false,val lastPrice:Double=0.0,val score:Double=0.0,val spreadBps:Double=0.0,val turnover24h:Double=0.0,val change24hPct:Double=0.0,val openInterestValue:Double=0.0,val maxLeverage:Double?=null,val style:String="",val promotionPotential:Double?=null)
data class ScannerTelemetry(val total:Int=0,val confirmedTradeableCount:Int=0,val watchingCount:Int=0,val noTradeCount:Int=0,val confirmedTradeable:List<ScannerItem> = emptyList(),val watching:List<ScannerItem> = emptyList(),val noTrade:List<ScannerItem> = emptyList())
data class WsTelemetry(val status:String="DOWN",val healthy:Boolean=false,val connectedCount:Int=0,val readyCount:Int=0,val freshCount:Int=0,val symbolCount:Int=0,val maxWsSymbols:Int=0,val staleCount:Int=0)
data class ConnectionTelemetry(val ws:WsTelemetry=WsTelemetry(),val snapshotBuildMs:Double=0.0,val workerToVpsHealthMs:Double=0.0,val wsP50Ms:Long?=null,val wsP95Ms:Long?=null,val wsMaxMs:Long?=null,val accountMs:Long?=null,val scannerMs:Long?=null,val overallMs:Long=0)
data class MonitorSnapshot(val generatedAt:String="",val bot:BotTelemetry=BotTelemetry(),val account:AccountTelemetry=AccountTelemetry(),val performance:PerformanceTelemetry=PerformanceTelemetry(),val positionsSummary:PositionsSummary=PositionsSummary(),val positions:List<PositionTelemetry> = emptyList(),val scanner:ScannerTelemetry=ScannerTelemetry(),val connection:ConnectionTelemetry=ConnectionTelemetry())

object TelemetryParser {
    private fun JSONObject.d(k:String)=optDouble(k,0.0)
    private fun JSONObject.i(k:String)=optInt(k,0)
    private fun JSONObject.s(k:String)=optString(k,"")
    private fun JSONObject.nLong(k:String):Long?=if(has(k)&&!isNull(k))optLong(k) else null
    private fun JSONArray.objects():List<JSONObject>=(0 until length()).mapNotNull{optJSONObject(it)}
    private fun perf(o:JSONObject)=PerformanceWindow(o.i("closedRecords"),o.i("wins"),o.i("losses"),o.d("winRatePct"),o.d("realizedPnl"),o.d("profitFactor"),o.d("expectancy"))
    private fun pos(o:JSONObject)=PositionTelemetry(o.s("symbol"),o.s("side"),o.d("size"),o.d("entryPrice"),o.d("markPrice"),o.d("unrealizedPnl"),if(o.has("roePct")&&!o.isNull("roePct"))o.d("roePct") else null,o.d("leverage"),o.d("tp"),o.d("sl"),o.d("liqPrice"),o.d("positionValue"),o.d("positionMargin"))
    private fun scan(o:JSONObject)=ScannerItem(o.s("symbol"),o.s("classification"),o.optString("reason",null),o.optBoolean("eligible",false),o.d("lastPrice"),o.d("score"),o.d("spreadBps"),o.d("turnover24h"),o.d("change24hPct"),o.d("openInterestValue"),if(o.has("maxLeverage")&&!o.isNull("maxLeverage"))o.d("maxLeverage") else null,o.s("style"),if(o.has("promotionPotential")&&!o.isNull("promotionPotential"))o.d("promotionPotential") else null)
    fun parse(o:JSONObject):MonitorSnapshot {
        val b=o.optJSONObject("bot")?:JSONObject(); val a=o.optJSONObject("account")?:JSONObject(); val p=o.optJSONObject("performance")?:JSONObject(); val ps=o.optJSONObject("positionsSummary")?:JSONObject(); val sc=o.optJSONObject("scanner")?:JSONObject(); val c=o.optJSONObject("connection")?:JSONObject(); val ws=c.optJSONObject("bybitWs")?:JSONObject(); val lat=c.optJSONObject("latency")?:JSONObject(); val age=c.optJSONObject("dataAge")?:JSONObject()
        return MonitorSnapshot(
            o.s("generatedAt"),
            BotTelemetry(b.s("status"),b.optBoolean("ready",false),b.s("mode"),b.s("version"),b.optString("lastCycleAt",null),b.optString("lastCycleReason",null)),
            AccountTelemetry(a.d("equity"),a.d("balance"),a.d("availableBalance"),a.d("unrealizedPnl"),a.d("realizedPnl"),a.d("realizedPnl72h")),
            PerformanceTelemetry(p.d("winRatePct"),p.d("realizedPnl"),perf(p.optJSONObject("h24")?:JSONObject()),perf(p.optJSONObject("h72")?:JSONObject())),
            PositionsSummary(ps.i("openCount"),ps.i("longCount"),ps.i("shortCount"),ps.d("longNotional"),ps.d("shortNotional"),ps.d("totalUnrealizedPnl")),
            (o.optJSONArray("positions")?:JSONArray()).objects().map(::pos),
            ScannerTelemetry(sc.i("total"),sc.i("confirmedTradeableCount"),sc.i("watchingCount"),sc.i("noTradeCount"),(sc.optJSONArray("confirmedTradeable")?:JSONArray()).objects().map(::scan),(sc.optJSONArray("watching")?:JSONArray()).objects().map(::scan),(sc.optJSONArray("noTrade")?:JSONArray()).objects().map(::scan)),
            ConnectionTelemetry(WsTelemetry(ws.s("status"),ws.optBoolean("healthy",false),ws.i("connectedCount"),ws.i("readyCount"),ws.i("freshCount"),ws.i("symbolCount"),ws.i("maxWsSymbols"),(ws.optJSONArray("staleSymbols")?:JSONArray()).length()),lat.d("snapshotBuildMs"),lat.d("workerToVpsHealthMs"),age.nLong("wsP50Ms"),age.nLong("wsP95Ms"),age.nLong("wsMaxMs"),age.nLong("accountMs"),age.nLong("scannerMs"),age.optLong("overallMs",0))
        )
    }
}
''',
'app/src/main/java/com/hanlinh/bybitmonitor/security/SecureTokenStore.kt':r'''package com.hanlinh.bybitmonitor.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureTokenStore(context:Context) {
    private val prefs=context.applicationContext.getSharedPreferences("monitor_secure",Context.MODE_PRIVATE)
    private val alias="bybit_monitor_token_aes_v1"
    private val ks=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
    private fun key():SecretKey {
        (ks.getKey(alias,null) as? SecretKey)?.let{return it}
        val kg=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore")
        kg.init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build())
        return kg.generateKey()
    }
    fun save(token:String){val c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());val iv=Base64.encodeToString(c.iv,Base64.NO_WRAP);val ct=Base64.encodeToString(c.doFinal(token.toByteArray()),Base64.NO_WRAP);prefs.edit().putString("iv",iv).putString("ct",ct).apply()}
    fun load():String?=try{val iv=prefs.getString("iv",null)?:return null;val ct=prefs.getString("ct",null)?:return null;val c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(iv,Base64.NO_WRAP)));String(c.doFinal(Base64.decode(ct,Base64.NO_WRAP)))}catch(_:Exception){null}
    fun clear(){prefs.edit().clear().apply()}
}
''',
'app/src/main/java/com/hanlinh/bybitmonitor/network/MonitorApi.kt':r'''package com.hanlinh.bybitmonitor.network

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
''',
'app/src/main/java/com/hanlinh/bybitmonitor/data/MonitorRepository.kt':r'''package com.hanlinh.bybitmonitor.data

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
''',
'app/src/main/java/com/hanlinh/bybitmonitor/ui/MonitorViewModel.kt':r'''package com.hanlinh.bybitmonitor.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.hanlinh.bybitmonitor.data.MonitorRepository
import com.hanlinh.bybitmonitor.model.MonitorSnapshot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MonitorUiState(val pairingRequired:Boolean=true,val pairing:Boolean=false,val error:String?=null,val connection:String="DISCONNECTED",val snapshot:MonitorSnapshot?=null)
class MonitorViewModel(app:Application):AndroidViewModel(app){
    private val repo=MonitorRepository(app)
    private val _state=MutableStateFlow(MonitorUiState(pairingRequired=!repo.hasToken()))
    val state:StateFlow<MonitorUiState> = _state.asStateFlow()
    init{if(repo.hasToken())connect()}
    fun pair(code:String,name:String){if(code.isBlank())return;viewModelScope.launch{_state.value=_state.value.copy(pairing=true,error=null);runCatching{repo.pair(code,name)}.onSuccess{_state.value=_state.value.copy(pairingRequired=false,pairing=false,error=null);connect()}.onFailure{_state.value=_state.value.copy(pairing=true,pairingRequired=true,error=it.message?:"PAIR_FAILED").copy(pairing=false)}}}
    fun refresh(){viewModelScope.launch{runCatching{repo.fetchSnapshot()}.onSuccess{_state.value=_state.value.copy(snapshot=it,error=null)}.onFailure{_state.value=_state.value.copy(error=it.message)}}}
    private fun connect(){repo.stopRealtime();viewModelScope.launch{runCatching{repo.fetchSnapshot()}.onSuccess{_state.value=_state.value.copy(pairingRequired=false,snapshot=it,error=null)}};repo.startRealtime({_state.value=_state.value.copy(pairingRequired=false,snapshot=it,error=null)},{_state.value=_state.value.copy(connection=it)})}
    fun disconnect(){repo.clearToken();_state.value=MonitorUiState(pairingRequired=true)}
    override fun onCleared(){repo.stopRealtime();super.onCleared()}
}
''',
'app/src/main/java/com/hanlinh/bybitmonitor/widget/MonitorWidgetProvider.kt':r'''package com.hanlinh.bybitmonitor.widget

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
''',
'app/src/main/java/com/hanlinh/bybitmonitor/widget/WidgetRefreshWorker.kt':r'''package com.hanlinh.bybitmonitor.widget

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.hanlinh.bybitmonitor.data.MonitorRepository

class WidgetRefreshWorker(appContext:Context,params:WorkerParameters):CoroutineWorker(appContext,params){
    override suspend fun doWork():Result=try{val repo=MonitorRepository(applicationContext);if(!repo.hasToken())return Result.success();val s=repo.fetchSnapshot();WidgetStateStore.save(applicationContext,s);WidgetStateStore.updateAll(applicationContext);Result.success()}catch(_:Exception){Result.retry()}
}
''',
'app/src/main/java/com/hanlinh/bybitmonitor/service/MonitorForegroundService.kt':r'''package com.hanlinh.bybitmonitor.service

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
    private fun handle(s:MonitorSnapshot){WidgetStateStore.save(this,s);WidgetStateStore.updateAll(this);val text="Equity $${"%.2f".format(s.account.equity)} · PnL ${"%+.2f".format(s.account.unrealizedPnl)} · ${s.connection.ws.freshCount}/${s.connection.ws.symbolCount} fresh";getSystemService(NotificationManager::class.java).notify(ONGOING_ID,ongoing(text));val now=s.positions.map{it.symbol}.toSet();val health=s.bot.status+":"+s.connection.ws.status;if(seeded.getAndSet(true)){(now-previousSymbols).forEach{alert("Mở vị thế $it","Bot vừa ghi nhận vị thế mới")};(previousSymbols-now).forEach{alert("Đóng vị thế $it","Vị thế đã rời danh sách mở")};if(health!=previousHealth&&(s.bot.status.contains("DEGRADED")||s.connection.ws.status!="HEALTHY"))alert("Telemetry cần chú ý",health)};previousSymbols=now;previousHealth=health}
    private fun pending():PendingIntent=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    private fun ongoing(text:String)=NotificationCompat.Builder(this,CH_LIVE).setSmallIcon(R.drawable.ic_monitor).setContentTitle("Bybit Monitor · Read only").setContentText(text).setContentIntent(pending()).setOnlyAlertOnce(true).setOngoing(true).build()
    private fun alert(title:String,text:String){getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis()%100000).toInt()+200,NotificationCompat.Builder(this,CH_ALERT).setSmallIcon(R.drawable.ic_monitor).setContentTitle(title).setContentText(text).setContentIntent(pending()).setAutoCancel(true).build())}
    private fun createChannels(){val m=getSystemService(NotificationManager::class.java);m.createNotificationChannel(NotificationChannel(CH_LIVE,"Monitor realtime",NotificationManager.IMPORTANCE_LOW));m.createNotificationChannel(NotificationChannel(CH_ALERT,"Cảnh báo bot",NotificationManager.IMPORTANCE_DEFAULT))}
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int)=START_STICKY
    override fun onDestroy(){repo.stopRealtime();super.onDestroy()}
    override fun onBind(intent:Intent?):IBinder?=null
    companion object{const val CH_LIVE="bybit_monitor_live";const val CH_ALERT="bybit_monitor_alert";const val ONGOING_ID=101;fun setEnabled(c:Context,on:Boolean){c.getSharedPreferences("monitor_settings",Context.MODE_PRIVATE).edit().putBoolean("background",on).apply();if(on)androidx.core.content.ContextCompat.startForegroundService(c,Intent(c,MonitorForegroundService::class.java)) else c.stopService(Intent(c,MonitorForegroundService::class.java))};fun isEnabled(c:Context)=c.getSharedPreferences("monitor_settings",Context.MODE_PRIVATE).getBoolean("background",false)}
}
''',
'app/src/main/java/com/hanlinh/bybitmonitor/ui/MonitorScreen.kt':r'''package com.hanlinh.bybitmonitor.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.hanlinh.bybitmonitor.model.*
import java.util.Locale

private fun money(v:Double)=String.format(Locale.US,"$%,.2f",v)
private fun signed(v:Double)=String.format(Locale.US,"%+.2f",v)
private fun price(v:Double)=when{v==0.0->"—";v>=100->String.format(Locale.US,"%,.2f",v);v>=1->String.format(Locale.US,"%.4f",v);else->String.format(Locale.US,"%.6f",v)}
@Composable fun MonitorScreen(state:MonitorUiState,onPair:(String,String)->Unit,onRefresh:()->Unit,onDisconnect:()->Unit,backgroundEnabled:Boolean,onBackground:(Boolean)->Unit){if(state.pairingRequired){PairScreen(state,onPair);return};val snap=state.snapshot;if(snap==null){Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Column(horizontalAlignment=Alignment.CenterHorizontally){CircularProgressIndicator();Spacer(Modifier.height(12.dp));Text("Đang lấy telemetry…");state.error?.let{Text(it,color=MaterialTheme.colorScheme.error)}}};return};var tab by remember{mutableIntStateOf(0)};Scaffold(bottomBar={NavigationBar{listOf("Tổng quan","Vị thế","Scanner").forEachIndexed{i,t->NavigationBarItem(selected=tab==i,onClick={tab=i},icon={Text(if(i==0)"●" else if(i==1)"◆" else "▦")},label={Text(t)})}}}){pad->Column(Modifier.padding(pad).fillMaxSize()){Header(snap,state.connection,onRefresh,onDisconnect);when(tab){0->Dashboard(snap,backgroundEnabled,onBackground);1->Positions(snap.positions);else->Scanner(snap.scanner)}}}}
@Composable private fun PairScreen(state:MonitorUiState,onPair:(String,String)->Unit){var code by remember{mutableStateOf("")};var name by remember{mutableStateOf("Điện thoại Android")};Box(Modifier.fillMaxSize().padding(24.dp),contentAlignment=Alignment.Center){Card{Column(Modifier.padding(22.dp).widthIn(max=440.dp)){Text("BYBIT ANDROID MONITOR",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold);Spacer(Modifier.height(8.dp));Text("Read-only · không có quyền đặt/đóng lệnh");Spacer(Modifier.height(18.dp));OutlinedTextField(value=code,onValueChange={code=it.uppercase()},label={Text("Mã ghép nối một lần")},singleLine=true,modifier=Modifier.fillMaxWidth());Spacer(Modifier.height(10.dp));OutlinedTextField(value=name,onValueChange={name=it},label={Text("Tên thiết bị")},singleLine=true,modifier=Modifier.fillMaxWidth());Spacer(Modifier.height(16.dp));Button(onClick={onPair(code,name)},enabled=!state.pairing&&code.isNotBlank(),modifier=Modifier.fillMaxWidth()){Text(if(state.pairing)"Đang ghép nối…" else "Kết nối Monitor")};state.error?.let{Spacer(Modifier.height(10.dp));Text(it,color=MaterialTheme.colorScheme.error)}}}}
@Composable private fun Header(s:MonitorSnapshot,connection:String,onRefresh:()->Unit,onDisconnect:()->Unit){Surface(tonalElevation=2.dp){Row(Modifier.fillMaxWidth().padding(14.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text("Bybit Monitor",fontWeight=FontWeight.Bold);Text("${s.bot.status} · WS ${s.connection.ws.status} · $connection",style=MaterialTheme.typography.bodySmall)};TextButton(onClick=onRefresh){Text("Làm mới")};TextButton(onClick=onDisconnect){Text("Ngắt")}}}}
@Composable private fun Dashboard(s:MonitorSnapshot,bg:Boolean,onBg:(Boolean)->Unit){LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){item{Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){Metric("Equity",money(s.account.equity),Modifier.weight(1f));Metric("Balance",money(s.account.balance),Modifier.weight(1f))}};item{Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){Metric("Available",money(s.account.availableBalance),Modifier.weight(1f));Metric("Unrealized",signed(s.account.unrealizedPnl),Modifier.weight(1f))}};item{Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)){Metric("Realized 24h",signed(s.performance.h24.realizedPnl),Modifier.weight(1f));Metric("Win rate",String.format(Locale.US,"%.1f%%",s.performance.winRatePct),Modifier.weight(1f))}};item{Card{Column(Modifier.fillMaxWidth().padding(14.dp)){Text("Exposure",fontWeight=FontWeight.Bold);Text("Long ${s.positionsSummary.longCount} · Short ${s.positionsSummary.shortCount} · Open ${s.positionsSummary.openCount}");Text("Long ${money(s.positionsSummary.longNotional)} · Short ${money(s.positionsSummary.shortNotional)}")}}};item{Card{Column(Modifier.fillMaxWidth().padding(14.dp)){Text("Bybit WebSocket",fontWeight=FontWeight.Bold);Text("${s.connection.ws.connectedCount}/${s.connection.ws.symbolCount} connected · ${s.connection.ws.freshCount} fresh · ${s.connection.ws.staleCount} stale");Text("Age P50 ${s.connection.wsP50Ms?:0} ms · P95 ${s.connection.wsP95Ms?:0} ms");Text("Worker→VPS ${String.format(Locale.US,"%.1f",s.connection.workerToVpsHealthMs)} ms · Snapshot ${String.format(Locale.US,"%.1f",s.connection.snapshotBuildMs)} ms")}}};item{Card{Row(Modifier.fillMaxWidth().padding(14.dp),verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){Text("Theo dõi nền",fontWeight=FontWeight.Bold);Text("Thông báo vị thế và trạng thái WS",style=MaterialTheme.typography.bodySmall)};Switch(checked=bg,onCheckedChange=onBg)}}};item{Card{Column(Modifier.fillMaxWidth().padding(14.dp)){Text("Performance 72h",fontWeight=FontWeight.Bold);Text("${s.performance.h72.wins} thắng / ${s.performance.h72.losses} thua · PF ${String.format(Locale.US,"%.2f",s.performance.h72.profitFactor)}");Text("Expectancy ${signed(s.performance.h72.expectancy)} · Realized ${signed(s.performance.h72.realizedPnl)}")}}}}
@Composable private fun Metric(label:String,value:String,modifier:Modifier=Modifier){Card(modifier){Column(Modifier.padding(14.dp)){Text(label,style=MaterialTheme.typography.labelMedium);Text(value,style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)}}}
@Composable private fun Positions(rows:List<PositionTelemetry>){if(rows.isEmpty()){Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text("Không có vị thế mở")};return};LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){items(rows,key={it.symbol+it.side}){p->Card{Column(Modifier.fillMaxWidth().padding(14.dp)){Row(Modifier.fillMaxWidth()){Text("${p.symbol} · ${if(p.side=="Buy")"LONG" else "SHORT"}",fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text("${signed(p.unrealizedPnl)} · ${p.roePct?.let{String.format(Locale.US,"%+.2f%%",it)}?:"—"}",fontWeight=FontWeight.Bold)};Text("Size ${p.size} · ${String.format(Locale.US,"%.1fx",p.leverage)}");Text("Entry ${price(p.entryPrice)}  →  Mark ${price(p.markPrice)}");Text("TP ${price(p.tp)} · SL ${price(p.sl)} · Liq ${price(p.liqPrice)}");Text("Value ${money(p.positionValue)} · Margin ${money(p.positionMargin)}",style=MaterialTheme.typography.bodySmall)}}}}}
@Composable private fun Scanner(s:ScannerTelemetry){var group by remember{mutableIntStateOf(0)};var q by remember{mutableStateOf("")};val base=when(group){0->s.confirmedTradeable;1->s.watching;else->s.noTrade};val rows=remember(base,q){if(q.isBlank())base else base.filter{it.symbol.contains(q.trim(),true)}};Column(Modifier.fillMaxSize().padding(horizontal=12.dp)){SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().padding(top=10.dp)){listOf("Trade ${s.confirmedTradeableCount}","Watch ${s.watchingCount}","No Trade ${s.noTradeCount}").forEachIndexed{i,t->SegmentedButton(selected=group==i,onClick={group=i},shape=SegmentedButtonDefaults.itemShape(i,3),label={Text(t)})}};OutlinedTextField(value=q,onValueChange={q=it.uppercase()},label={Text("Tìm symbol")},singleLine=true,modifier=Modifier.fillMaxWidth().padding(vertical=8.dp));LazyColumn(Modifier.fillMaxSize(),verticalArrangement=Arrangement.spacedBy(8.dp)){items(rows,key={it.symbol}){r->Card{Column(Modifier.fillMaxWidth().padding(12.dp)){Row(Modifier.fillMaxWidth()){Text(r.symbol,fontWeight=FontWeight.Bold,modifier=Modifier.weight(1f));Text(r.classification)};Text("Price ${price(r.lastPrice)} · Spread ${String.format(Locale.US,"%.2f",r.spreadBps)} bps · 24h ${String.format(Locale.US,"%+.2f%%",r.change24hPct)}");Text("Turnover ${money(r.turnover24h)} · OI ${money(r.openInterestValue)} · Score ${String.format(Locale.US,"%.3f",r.score)}",style=MaterialTheme.typography.bodySmall);r.reason?.takeIf{it.isNotBlank()}?.let{Text(it,style=MaterialTheme.typography.bodySmall)}}}}}}}
''',
'app/src/main/java/com/hanlinh/bybitmonitor/MainActivity.kt':r'''package com.hanlinh.bybitmonitor

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hanlinh.bybitmonitor.service.MonitorForegroundService
import com.hanlinh.bybitmonitor.ui.MonitorScreen
import com.hanlinh.bybitmonitor.ui.MonitorViewModel

class MainActivity:ComponentActivity(){
    override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);setContent{val vm:MonitorViewModel=viewModel();val state by vm.state.collectAsState();var bg by remember{mutableStateOf(MonitorForegroundService.isEnabled(this))};val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){};LaunchedEffect(Unit){if(Build.VERSION.SDK_INT>=33)permission.launch(Manifest.permission.POST_NOTIFICATIONS)};MaterialTheme(colorScheme=lightColorScheme(primary=Color(0xFF111827),secondary=Color(0xFF2563EB),background=Color(0xFFF5F7FA),surface=Color.White)){MonitorScreen(state,vm::pair,vm::refresh,vm::disconnect,bg){on->bg=on;MonitorForegroundService.setEnabled(this,on)}}}}
}
''',
'README.md':r'''# Bybit Android Monitor V1

Read-only Android client for the production Bybit multi-asset bot.

## Security
- No Bybit API key/secret in the APK.
- No trading endpoints are called by the app.
- First pairing uses a one-time pairing code.
- The returned monitor token is encrypted with Android Keystore (AES-GCM).
- REST and WebSocket use `Authorization: Bearer <monitor-token>`.

## Screens
- Dashboard: Equity, Balance, Available, Unrealized/Realized PnL, Win Rate, Long/Short, WS health, latency, data age.
- Positions: all open positions with Entry, Mark, PnL, ROE, leverage, TP, SL, liquidation price.
- Scanner: Confirmed Tradeable / Watching / No Trade with search.

## Background
Optional foreground realtime monitor posts position/connection notifications. The home-screen widget is refreshed from the foreground stream and by WorkManager.

## Backend
Default endpoint: `https://trading-v77-scanner.hanlinh227.workers.dev`.
Schema: `BYBIT_ANDROID_MONITOR_V1`.
'''
}
for rel,content in files.items():
    p=BASE/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
print(f'ANDROID_MONITOR_APP_GENERATED files={len(files)} root={BASE}')
