package com.hanlinh.bybitmonitor.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hanlinh.bybitmonitor.model.*
import java.util.Locale

private val Cyan=Color(0xFF00E5FF)
private val Green=Color(0xFF70FFB1)
private val Red=Color(0xFFFF5C6C)
private val Amber=Color(0xFFFFCC66)
private val Muted=Color(0xFF78909C)
private val Panel=Color(0xFF080C10)
private val Panel2=Color(0xFF0D141A)
private val Border=Color(0xFF17303A)

private fun money(v:Double)=String.format(Locale.US,"$%,.2f",v)
private fun signed(v:Double)=String.format(Locale.US,"%+.2f",v)
private fun price(v:Double)=when{v==0.0->"—";v>=100->String.format(Locale.US,"%,.2f",v);v>=1->String.format(Locale.US,"%.4f",v);else->String.format(Locale.US,"%.6f",v)}
private fun pnlColor(v:Double)=when{v>0->Green;v<0->Red;else->Muted}
private fun statusColor(s:String)=when{val x=s.uppercase();x.contains("LIVE")||x.contains("HEALTHY")||x.contains("CONNECTED")->Green;x.contains("DEGRADED")||x.contains("STALE")||x.contains("CONNECTING")->Amber;else->Red}
private fun progress(p:PositionTelemetry):Float{val d=if(p.side=="Buy")p.tp-p.entryPrice else p.entryPrice-p.tp;if(d<=0)return 0f;val m=if(p.side=="Buy")p.markPrice-p.entryPrice else p.entryPrice-p.markPrice;return (m/d).coerceIn(0.0,1.0).toFloat()}

@Composable
fun MonitorScreen(state:MonitorUiState,onPair:(String,String)->Unit,onRefresh:()->Unit,onDisconnect:()->Unit,backgroundEnabled:Boolean,onBackground:(Boolean)->Unit){
    Surface(Modifier.fillMaxSize(),color=MaterialTheme.colorScheme.background){
        if(state.pairingRequired){PairScreen(state,onPair);return@Surface}
        val snapshot=state.snapshot
        if(snapshot==null){Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Column(horizontalAlignment=Alignment.CenterHorizontally){CircularProgressIndicator(color=Cyan);Spacer(Modifier.height(12.dp));Text("SYNCING TELEMETRY…",color=Muted);state.error?.let{Text(it,color=Red)}}};return@Surface}
        var tab by remember{mutableIntStateOf(0)}
        Scaffold(containerColor=MaterialTheme.colorScheme.background,bottomBar={TerminalNav(tab){tab=it}}){padding->
            Column(Modifier.padding(padding).fillMaxSize()){
                Header(snapshot,state.connection,onRefresh,onDisconnect)
                when(tab){0->Dashboard(snapshot,backgroundEnabled,onBackground);1->Positions(snapshot.positions);else->Scanner(snapshot.scanner)}
            }
        }
    }
}

@Composable private fun TerminalCard(modifier:Modifier=Modifier,content:@Composable ColumnScope.()->Unit){Card(modifier,shape=RoundedCornerShape(10.dp),colors=CardDefaults.cardColors(containerColor=Panel),border=BorderStroke(1.dp,Border)){Column(Modifier.fillMaxWidth().padding(14.dp),content=content)}}

@Composable private fun PairScreen(state:MonitorUiState,onPair:(String,String)->Unit){
    var code by remember{mutableStateOf("")};var name by remember{mutableStateOf("Hanlinh")}
    Box(Modifier.fillMaxSize().background(Color.Black).padding(20.dp),contentAlignment=Alignment.Center){TerminalCard(Modifier.widthIn(max=460.dp)){Text("BYBIT // ANDROID MONITOR",fontSize=22.sp,fontWeight=FontWeight.Bold,color=Cyan);Spacer(Modifier.height(6.dp));Text("READ-ONLY TELEMETRY TERMINAL",color=Muted,fontSize=12.sp);Text("NO BUY · NO SELL · NO CLOSE",color=Green,fontSize=11.sp);Spacer(Modifier.height(18.dp));OutlinedTextField(code,{code=it.uppercase()},label={Text("ONE-TIME PAIR CODE")},singleLine=true,modifier=Modifier.fillMaxWidth());Spacer(Modifier.height(10.dp));OutlinedTextField(name,{name=it},label={Text("DEVICE NAME")},singleLine=true,modifier=Modifier.fillMaxWidth());Spacer(Modifier.height(14.dp));Button(onClick={onPair(code,name)},enabled=!state.pairing&&code.isNotBlank(),modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.buttonColors(containerColor=Cyan,contentColor=Color.Black)){Text(if(state.pairing)"PAIRING…" else "CONNECT MONITOR",fontWeight=FontWeight.Bold)};state.error?.let{Spacer(Modifier.height(10.dp));Text(it.replace("PAIRING_CODE_INVALID","PAIR CODE INVALID / EXPIRED"),color=Red)}}}
}

@Composable private fun Header(s:MonitorSnapshot,connection:String,onRefresh:()->Unit,onDisconnect:()->Unit){
    Surface(color=Color.Black){Column(Modifier.fillMaxWidth().padding(horizontal=14.dp,vertical=10.dp)){Row(verticalAlignment=Alignment.CenterVertically){Box(Modifier.size(8.dp).clip(RoundedCornerShape(50)).background(statusColor(s.bot.status)));Spacer(Modifier.width(7.dp));Text("${s.bot.status} // ${s.bot.mode}",color=statusColor(s.bot.status),fontWeight=FontWeight.Bold,fontSize=12.sp);Spacer(Modifier.weight(1f));Text("WS ${s.connection.ws.status}",color=statusColor(s.connection.ws.status),fontSize=11.sp)};Spacer(Modifier.height(4.dp));Row(verticalAlignment=Alignment.CenterVertically){Text("BYBIT MONITOR",fontWeight=FontWeight.Bold,color=Color.White,modifier=Modifier.weight(1f));Text("AGE ${s.connection.overallMs}ms",color=if(s.connection.overallMs<3000)Green else Amber,fontSize=10.sp);TextButton(onClick=onRefresh){Text("SYNC",color=Cyan,fontSize=11.sp)};TextButton(onClick=onDisconnect){Text("UNPAIR",color=Muted,fontSize=11.sp)}};HorizontalDivider(color=Border)}}
}

@Composable private fun TerminalNav(tab:Int,onTab:(Int)->Unit){NavigationBar(containerColor=Color.Black,tonalElevation=0.dp){listOf("DASH","POSITIONS","SCANNER").forEachIndexed{i,t->NavigationBarItem(selected=tab==i,onClick={onTab(i)},icon={Text(if(i==0)"▣" else if(i==1)"◆" else "⌁",color=if(tab==i)Cyan else Muted)},label={Text(t,fontSize=10.sp)},colors=NavigationBarItemDefaults.colors(selectedTextColor=Cyan,unselectedTextColor=Muted,indicatorColor=Panel2))}}}

@Composable private fun Dashboard(s:MonitorSnapshot,backgroundEnabled:Boolean,onBackground:(Boolean)->Unit){LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
    item{TerminalCard{Text("EQUITY",color=Muted,fontSize=11.sp);Text(money(s.account.equity),fontSize=38.sp,lineHeight=42.sp,fontWeight=FontWeight.Bold,color=Color.White);Row{Text("UNREAL ${signed(s.account.unrealizedPnl)}",color=pnlColor(s.account.unrealizedPnl),fontWeight=FontWeight.Bold);Spacer(Modifier.weight(1f));Text("REAL24 ${signed(s.performance.h24.realizedPnl)}",color=pnlColor(s.performance.h24.realizedPnl),fontWeight=FontWeight.Bold)}}}
    item{MetricRow("BALANCE",money(s.account.balance),"AVAILABLE",money(s.account.availableBalance))}
    item{MetricRow("WIN RATE",String.format(Locale.US,"%.1f%%",s.performance.winRatePct),"OPEN","${s.positionsSummary.openCount}  L${s.positionsSummary.longCount}/S${s.positionsSummary.shortCount}")}
    item{TerminalCard{SectionTitle("BYBIT WS / REALTIME");Text("${s.connection.ws.connectedCount}/${s.connection.ws.symbolCount} CONNECTED   ${s.connection.ws.freshCount} FRESH",color=if(s.connection.ws.healthy)Green else Amber);Text("P50 ${s.connection.wsP50Ms?:0}ms   P95 ${s.connection.wsP95Ms?:0}ms   MAX ${s.connection.wsMaxMs?:0}ms",color=Muted,fontSize=11.sp);Text("WORKER→VPS ${String.format(Locale.US,"%.1f",s.connection.workerToVpsHealthMs)}ms   SNAP ${String.format(Locale.US,"%.1f",s.connection.snapshotBuildMs)}ms",color=Muted,fontSize=11.sp)}}
    item{TerminalCard{SectionTitle("PERFORMANCE 72H");Text("${s.performance.h72.wins}W / ${s.performance.h72.losses}L   PF ${String.format(Locale.US,"%.2f",s.performance.h72.profitFactor)}");Text("EXPECT ${signed(s.performance.h72.expectancy)}   REAL ${signed(s.performance.h72.realizedPnl)}",color=pnlColor(s.performance.h72.realizedPnl))}}
    item{TerminalCard{Row(verticalAlignment=Alignment.CenterVertically){Column(Modifier.weight(1f)){SectionTitle("BACKGROUND MONITOR");Text("position + WS alerts",color=Muted,fontSize=11.sp)};Switch(backgroundEnabled,onBackground,colors=SwitchDefaults.colors(checkedThumbColor=Color.Black,checkedTrackColor=Green))}}}
}}

@Composable private fun SectionTitle(x:String){Text(x,color=Cyan,fontWeight=FontWeight.Bold,fontSize=11.sp);Spacer(Modifier.height(6.dp))}
@Composable private fun MetricRow(l1:String,v1:String,l2:String,v2:String){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(9.dp)){Metric(l1,v1,Modifier.weight(1f));Metric(l2,v2,Modifier.weight(1f))}}
@Composable private fun Metric(label:String,value:String,modifier:Modifier=Modifier){TerminalCard(modifier){Text(label,color=Muted,fontSize=10.sp);Text(value,fontSize=18.sp,fontWeight=FontWeight.Bold,color=Color.White)}}

@Composable private fun PositionProgress(p:PositionTelemetry){val x=progress(p);val c=when{x>=.8f->Green;x>=.5f->Cyan;x>=.2f->Amber;else->Muted};Column{Row{Text("TP PROGRESS",color=Muted,fontSize=10.sp);Spacer(Modifier.weight(1f));Text("${(x*100).toInt()}%",color=c,fontSize=10.sp)};Spacer(Modifier.height(5.dp));BoxWithConstraints(Modifier.fillMaxWidth().height(10.dp)){Box(Modifier.fillMaxWidth().height(3.dp).align(Alignment.Center).clip(RoundedCornerShape(2.dp)).background(Color(0xFF122029)));Box(Modifier.fillMaxWidth(x).height(3.dp).align(Alignment.CenterStart).clip(RoundedCornerShape(2.dp)).background(c));val pinX=(maxWidth-8.dp)*x;Box(Modifier.offset(x=pinX).size(8.dp).align(Alignment.CenterStart).clip(RoundedCornerShape(50)).background(c))}}}

@Composable private fun Positions(rows:List<PositionTelemetry>){if(rows.isEmpty()){Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text("// NO OPEN POSITIONS",color=Muted)};return};LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(12.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){items(rows,key={it.symbol+it.side}){p->TerminalCard{Row{Text(p.symbol.replace("USDT","/USDT"),fontWeight=FontWeight.Bold,color=Color.White,modifier=Modifier.weight(1f));Text(if(p.side=="Buy")"LONG" else "SHORT",color=if(p.side=="Buy")Green else Red,fontWeight=FontWeight.Bold);Spacer(Modifier.width(10.dp));Text(signed(p.unrealizedPnl),color=pnlColor(p.unrealizedPnl),fontWeight=FontWeight.Bold)};Text("ROE ${p.roePct?.let{String.format(Locale.US,"%+.2f%%",it)}?:"—"}   LEV ${String.format(Locale.US,"%.1fx",p.leverage)}   SIZE ${p.size}",color=Muted,fontSize=11.sp);Spacer(Modifier.height(8.dp));PositionProgress(p);Spacer(Modifier.height(8.dp));Text("ENTRY ${price(p.entryPrice)}   MARK ${price(p.markPrice)}");Text("TP    ${price(p.tp)}   SL   ${price(p.sl)}",color=Color(0xFFB9C8D0));Text("LIQ   ${price(p.liqPrice)}   VALUE ${money(p.positionValue)}",color=Muted,fontSize=10.sp)}}}}

@Composable private fun Scanner(s:ScannerTelemetry){var group by remember{mutableIntStateOf(0)};var query by remember{mutableStateOf("")};val base=when(group){0->s.confirmedTradeable;1->s.watching;else->s.noTrade};val rows=remember(base,query){if(query.isBlank())base else base.filter{it.symbol.contains(query.trim(),true)}};Column(Modifier.fillMaxSize().padding(horizontal=10.dp)){Row(Modifier.fillMaxWidth().padding(top=9.dp),horizontalArrangement=Arrangement.spacedBy(5.dp)){FilterChip(group==0,{group=0},{Text("TRADE ${s.confirmedTradeableCount}",fontSize=10.sp)},modifier=Modifier.weight(1f));FilterChip(group==1,{group=1},{Text("WATCH ${s.watchingCount}",fontSize=10.sp)},modifier=Modifier.weight(1f));FilterChip(group==2,{group=2},{Text("NO ${s.noTradeCount}",fontSize=10.sp)},modifier=Modifier.weight(1f))};OutlinedTextField(query,{query=it.uppercase()},label={Text("SEARCH SYMBOL")},singleLine=true,modifier=Modifier.fillMaxWidth().padding(vertical=7.dp));LazyColumn(Modifier.fillMaxSize(),verticalArrangement=Arrangement.spacedBy(6.dp)){items(rows,key={it.symbol}){r->TerminalCard{Row{Text(r.symbol,fontWeight=FontWeight.Bold,color=Color.White,modifier=Modifier.weight(1f));Text(r.classification,color=if(r.eligible)Green else if(r.classification.contains("WATCH"))Amber else Red,fontSize=10.sp)};Text("PX ${price(r.lastPrice)}   SPR ${String.format(Locale.US,"%.2f",r.spreadBps)}bp   24H ${String.format(Locale.US,"%+.2f%%",r.change24hPct)}",fontSize=11.sp);Text("VOL ${money(r.turnover24h)}   OI ${money(r.openInterestValue)}   SCORE ${String.format(Locale.US,"%.3f",r.score)}",color=Muted,fontSize=10.sp);r.reason?.takeIf{it.isNotBlank()}?.let{Text(it,color=Muted,fontSize=9.sp)}}}}}}
