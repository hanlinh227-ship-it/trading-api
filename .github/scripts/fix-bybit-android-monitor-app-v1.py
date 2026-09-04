from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'android-monitor/app/src/main/java/com/hanlinh/bybitmonitor'

p=BASE/'model/Telemetry.kt'
s=p.read_text().replace('private fun JSONArray.objects():List<JSONObject>=(0 until length()).mapNotNull{optJSONObject(it)}','private fun JSONArray.objects():List<JSONObject> = (0 until length()).mapNotNull { optJSONObject(it) }')
p.write_text(s)

(BASE/'widget/WidgetRefreshWorker.kt').write_text(r'''package com.hanlinh.bybitmonitor.widget

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.hanlinh.bybitmonitor.data.MonitorRepository

class WidgetRefreshWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        return try {
            val repo = MonitorRepository(applicationContext)
            if (!repo.hasToken()) {
                Result.success()
            } else {
                val snapshot = repo.fetchSnapshot()
                WidgetStateStore.save(applicationContext, snapshot)
                WidgetStateStore.updateAll(applicationContext)
                Result.success()
            }
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
''')

(BASE/'ui/MonitorScreen.kt').write_text(r'''package com.hanlinh.bybitmonitor.ui

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

private fun money(v: Double) = String.format(Locale.US, "$%,.2f", v)
private fun signed(v: Double) = String.format(Locale.US, "%+.2f", v)
private fun price(v: Double) = when {
    v == 0.0 -> "—"
    v >= 100 -> String.format(Locale.US, "%,.2f", v)
    v >= 1 -> String.format(Locale.US, "%.4f", v)
    else -> String.format(Locale.US, "%.6f", v)
}

@Composable
fun MonitorScreen(
    state: MonitorUiState,
    onPair: (String, String) -> Unit,
    onRefresh: () -> Unit,
    onDisconnect: () -> Unit,
    backgroundEnabled: Boolean,
    onBackground: (Boolean) -> Unit
) {
    if (state.pairingRequired) {
        PairScreen(state, onPair)
        return
    }
    val snapshot = state.snapshot
    if (snapshot == null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
                Spacer(Modifier.height(12.dp))
                Text("Đang lấy telemetry…")
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        }
        return
    }
    var tab by remember { mutableIntStateOf(0) }
    Scaffold(
        bottomBar = {
            NavigationBar {
                listOf("Tổng quan", "Vị thế", "Scanner").forEachIndexed { i, title ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i },
                        icon = { Text(if (i == 0) "●" else if (i == 1) "◆" else "▦") },
                        label = { Text(title) }
                    )
                }
            }
        }
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            Header(snapshot, state.connection, onRefresh, onDisconnect)
            when (tab) {
                0 -> Dashboard(snapshot, backgroundEnabled, onBackground)
                1 -> Positions(snapshot.positions)
                else -> Scanner(snapshot.scanner)
            }
        }
    }
}

@Composable
private fun PairScreen(state: MonitorUiState, onPair: (String, String) -> Unit) {
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("Điện thoại Android") }
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Card {
            Column(Modifier.padding(22.dp).widthIn(max = 440.dp)) {
                Text("BYBIT ANDROID MONITOR", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Text("Read-only · không có quyền đặt/đóng lệnh")
                Spacer(Modifier.height(18.dp))
                OutlinedTextField(code, { code = it.uppercase() }, label = { Text("Mã ghép nối một lần") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(name, { name = it }, label = { Text("Tên thiết bị") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(16.dp))
                Button(onClick = { onPair(code, name) }, enabled = !state.pairing && code.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.pairing) "Đang ghép nối…" else "Kết nối Monitor")
                }
                state.error?.let { Spacer(Modifier.height(10.dp)); Text(it, color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun Header(s: MonitorSnapshot, connection: String, onRefresh: () -> Unit, onDisconnect: () -> Unit) {
    Surface(tonalElevation = 2.dp) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Bybit Monitor", fontWeight = FontWeight.Bold)
                Text("${s.bot.status} · WS ${s.connection.ws.status} · $connection", style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = onRefresh) { Text("Làm mới") }
            TextButton(onClick = onDisconnect) { Text("Ngắt") }
        }
    }
}

@Composable
private fun Dashboard(s: MonitorSnapshot, backgroundEnabled: Boolean, onBackground: (Boolean) -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { MetricRow("Equity", money(s.account.equity), "Balance", money(s.account.balance)) }
        item { MetricRow("Available", money(s.account.availableBalance), "Unrealized", signed(s.account.unrealizedPnl)) }
        item { MetricRow("Realized 24h", signed(s.performance.h24.realizedPnl), "Win rate", String.format(Locale.US, "%.1f%%", s.performance.winRatePct)) }
        item {
            Card { Column(Modifier.fillMaxWidth().padding(14.dp)) {
                Text("Exposure", fontWeight = FontWeight.Bold)
                Text("Long ${s.positionsSummary.longCount} · Short ${s.positionsSummary.shortCount} · Open ${s.positionsSummary.openCount}")
                Text("Long ${money(s.positionsSummary.longNotional)} · Short ${money(s.positionsSummary.shortNotional)}")
            } }
        }
        item {
            Card { Column(Modifier.fillMaxWidth().padding(14.dp)) {
                Text("Bybit WebSocket", fontWeight = FontWeight.Bold)
                Text("${s.connection.ws.connectedCount}/${s.connection.ws.symbolCount} connected · ${s.connection.ws.freshCount} fresh · ${s.connection.ws.staleCount} stale")
                Text("Age P50 ${s.connection.wsP50Ms ?: 0} ms · P95 ${s.connection.wsP95Ms ?: 0} ms")
                Text("Worker→VPS ${String.format(Locale.US, "%.1f", s.connection.workerToVpsHealthMs)} ms · Snapshot ${String.format(Locale.US, "%.1f", s.connection.snapshotBuildMs)} ms")
            } }
        }
        item {
            Card { Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Theo dõi nền", fontWeight = FontWeight.Bold)
                    Text("Thông báo vị thế và trạng thái WS", style = MaterialTheme.typography.bodySmall)
                }
                Switch(backgroundEnabled, onBackground)
            } }
        }
        item {
            Card { Column(Modifier.fillMaxWidth().padding(14.dp)) {
                Text("Performance 72h", fontWeight = FontWeight.Bold)
                Text("${s.performance.h72.wins} thắng / ${s.performance.h72.losses} thua · PF ${String.format(Locale.US, "%.2f", s.performance.h72.profitFactor)}")
                Text("Expectancy ${signed(s.performance.h72.expectancy)} · Realized ${signed(s.performance.h72.realizedPnl)}")
            } }
        }
    }
}

@Composable
private fun MetricRow(l1: String, v1: String, l2: String, v2: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Metric(l1, v1, Modifier.weight(1f))
        Metric(l2, v2, Modifier.weight(1f))
    }
}

@Composable
private fun Metric(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier) { Column(Modifier.padding(14.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium)
        Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
    } }
}

@Composable
private fun Positions(rows: List<PositionTelemetry>) {
    if (rows.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Không có vị thế mở") }
        return
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items(rows, key = { it.symbol + it.side }) { p ->
            Card { Column(Modifier.fillMaxWidth().padding(14.dp)) {
                Row(Modifier.fillMaxWidth()) {
                    Text("${p.symbol} · ${if (p.side == "Buy") "LONG" else "SHORT"}", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Text("${signed(p.unrealizedPnl)} · ${p.roePct?.let { String.format(Locale.US, "%+.2f%%", it) } ?: "—"}", fontWeight = FontWeight.Bold)
                }
                Text("Size ${p.size} · ${String.format(Locale.US, "%.1fx", p.leverage)}")
                Text("Entry ${price(p.entryPrice)} → Mark ${price(p.markPrice)}")
                Text("TP ${price(p.tp)} · SL ${price(p.sl)} · Liq ${price(p.liqPrice)}")
                Text("Value ${money(p.positionValue)} · Margin ${money(p.positionMargin)}", style = MaterialTheme.typography.bodySmall)
            } }
        }
    }
}

@Composable
private fun Scanner(s: ScannerTelemetry) {
    var group by remember { mutableIntStateOf(0) }
    var query by remember { mutableStateOf("") }
    val base = when (group) { 0 -> s.confirmedTradeable; 1 -> s.watching; else -> s.noTrade }
    val rows = remember(base, query) { if (query.isBlank()) base else base.filter { it.symbol.contains(query.trim(), true) } }
    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            FilterChip(group == 0, { group = 0 }, { Text("Trade ${s.confirmedTradeableCount}") }, modifier = Modifier.weight(1f))
            FilterChip(group == 1, { group = 1 }, { Text("Watch ${s.watchingCount}") }, modifier = Modifier.weight(1f))
            FilterChip(group == 2, { group = 2 }, { Text("No ${s.noTradeCount}") }, modifier = Modifier.weight(1f))
        }
        OutlinedTextField(query, { query = it.uppercase() }, label = { Text("Tìm symbol") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp))
        LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(rows, key = { it.symbol }) { r ->
                Card { Column(Modifier.fillMaxWidth().padding(12.dp)) {
                    Row(Modifier.fillMaxWidth()) { Text(r.symbol, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f)); Text(r.classification) }
                    Text("Price ${price(r.lastPrice)} · Spread ${String.format(Locale.US, "%.2f", r.spreadBps)} bps · 24h ${String.format(Locale.US, "%+.2f%%", r.change24hPct)}")
                    Text("Turnover ${money(r.turnover24h)} · OI ${money(r.openInterestValue)} · Score ${String.format(Locale.US, "%.3f", r.score)}", style = MaterialTheme.typography.bodySmall)
                    r.reason?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                } }
            }
        }
    }
}
''')

p=BASE/'service/MonitorForegroundService.kt'
s=p.read_text()
s=s.replace('val text="Equity $${"%.2f".format(s.account.equity)} · PnL ${"%+.2f".format(s.account.unrealizedPnl)} · ${s.connection.ws.freshCount}/${s.connection.ws.symbolCount} fresh"','val text="Equity $" + "%.2f".format(s.account.equity) + " · PnL " + "%+.2f".format(s.account.unrealizedPnl) + " · ${s.connection.ws.freshCount}/${s.connection.ws.symbolCount} fresh"')
p.write_text(s)
print('ANDROID_MONITOR_COMPILE_FIXES_APPLIED')
