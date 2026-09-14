package com.hanlinh.androidbrain

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.hanlinh.androidbrain.action.ShizukuActions
import com.hanlinh.androidbrain.network.PairingRepository
import com.hanlinh.androidbrain.security.DeviceIdentity
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService

class MainActivity : ComponentActivity() {
    private var refreshTick by mutableStateOf(0)
    private var pairingStatus by mutableStateOf("Chưa ghép với gateway")
    private var pairingBusy by mutableStateOf(false)
    private val deviceId: String by lazy { DeviceIdentity.deviceId() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pairingStatus = PairingRepository(this).load()?.let { "Đã ghép với Brain Gateway" } ?: "Chưa ghép với gateway"
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
        }
        setContent {
            refreshTick
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(
                        modifier = Modifier.padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("Android Brain Agent", style = MaterialTheme.typography.headlineMedium)
                        Text(pairingStatus)
                        Text("Device ID: $deviceId")
                        Button(onClick = { copyDeviceId() }) { Text("Sao chép Device ID cho GPT") }
                        Text("Accessibility: ${if (BrainAccessibilityService.current != null) "BẬT" else "CHƯA BẬT"}")
                        Text("Shizuku: ${if (ShizukuActions().available()) "PHÁT HIỆN" else "TÙY CHỌN / CHƯA BẬT"}")
                        Text("Kill switch: ${if (AgentForegroundService.killSwitchActive) "ĐANG KHÓA" else "SẴN SÀNG"}")

                        Button(onClick = { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }) {
                            Text("1. Bật Accessibility")
                        }
                        Button(onClick = { startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }) {
                            Text("2. Bật Notification Access")
                        }
                        Button(enabled = !pairingBusy, onClick = { pairGateway() }) {
                            Text(if (pairingBusy) "Đang ghép…" else "3. Pair với Brain Gateway")
                        }
                        Button(onClick = { startAgent() }) { Text("4. Khởi động Agent") }
                        Button(onClick = { stopAgent() }) { Text("Dừng / Kill switch") }
                        Spacer(Modifier.height(8.dp))
                        Text("Sau khi Pair, sao chép Device ID và gửi một lần cho GPT để ra lệnh từ chat.")
                        Text("V1 không root. Agent chỉ thực thi command đã ký; Class D bị chặn. Vision cần consent riêng khi được dùng.")
                    }
                }
            }
        }
    }

    private fun copyDeviceId() {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("Android Brain Agent Device ID", deviceId))
    }

    private fun pairGateway() {
        pairingBusy = true
        pairingStatus = "Đang kết nối gateway…"
        Thread {
            try {
                PairingRepository(this).pair()
                runOnUiThread {
                    pairingStatus = "Đã ghép với Brain Gateway"
                    pairingBusy = false
                    startAgent()
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    pairingStatus = "Pair thất bại: ${error.message?.take(120) ?: error.javaClass.simpleName}"
                    pairingBusy = false
                }
            }
        }.start()
    }

    private fun startAgent() {
        AgentForegroundService.resetKillSwitch()
        ContextCompat.startForegroundService(this, Intent(this, AgentForegroundService::class.java))
        refreshTick++
    }

    private fun stopAgent() {
        startService(Intent(this, AgentForegroundService::class.java).setAction(AgentForegroundService.ACTION_STOP))
        refreshTick++
    }

    override fun onResume() {
        super.onResume()
        refreshTick++
    }
}
