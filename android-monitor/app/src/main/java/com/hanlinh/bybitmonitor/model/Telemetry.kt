package com.hanlinh.bybitmonitor.model

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
    private fun JSONArray.objects():List<JSONObject> = (0 until length()).mapNotNull { optJSONObject(it) }
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
