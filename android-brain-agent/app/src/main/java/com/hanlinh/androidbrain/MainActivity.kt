package com.hanlinh.androidbrain

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.hanlinh.androidbrain.network.GatewayClient
import com.hanlinh.androidbrain.network.PairingRepository
import com.hanlinh.androidbrain.security.DeviceIdentity
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.AgentRunPreference
import com.hanlinh.androidbrain.service.AgentStartupPolicy
import com.hanlinh.androidbrain.service.BrainAccessibilityService
import com.hanlinh.androidbrain.service.BrainNotificationService

class MainActivity : ComponentActivity() {
    private var refreshTick by mutableStateOf(0)
    private var pairingStatus by mutableStateOf("Đang kiểm tra ghép nối…")
    private var gatewayStatus by mutableStateOf("Chưa kiểm tra")
    private var pairingBusy by mutableStateOf(false)
    private val deviceId: String by lazy { DeviceIdentity.deviceId() }
    private val pairingRepository: PairingRepository by lazy { PairingRepository(this) }
    private val runPreference: AgentRunPreference by lazy { AgentRunPreference(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pairing = pairingRepository.load()
        pairingStatus = if (pairing != null) "Đã ghép với Brain Gateway" else "Chưa ghép với gateway"

        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
        }

        setContent {
            refreshTick
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(
                        modifier = Modifier
                            .verticalScroll(rememberScrollState())
                            .padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("Android Brain Agent", style = MaterialTheme.typography.headlineMedium)
                        Text("Persistent Agent ${BuildConfig.VERSION_NAME}")
                        Text("Gateway: $gatewayStatus")
                        Text(pairingStatus)
                        Text("Device ID: $deviceId")
                        Button(onClick = { copyDeviceId() }) { Text("Sao chép Device ID") }

                        Text("Accessibility: ${if (isAccessibilityEnabled()) "BẬT" else "CHƯA BẬT"}")
                        Text("Notification Access: ${if (isNotificationAccessEnabled()) "BẬT" else "CHƯA BẬT"}")
                        Text("Agent: ${if (runPreference.isEnabled()) "TỰ ĐỘNG / SẴN SÀNG" else "ĐANG DỪNG"}")

                        Text("Nếu Android chặn quyền trợ năng do APK cài ngoài Store: mở App info → menu ⋮ → Cho phép cài đặt hạn chế.")
                        Button(onClick = { openAppInfo() }) { Text("Mở App info / Restricted Settings") }
                        Button(onClick = { openAccessibilitySettings() }) { Text("Bật Accessibility") }
                        Button(onClick = { openNotificationAccessSettings() }) { Text("Bật Notification Access") }
                        Button(onClick = { checkGateway() }) { Text("Kiểm tra Brain Gateway") }
                        Button(enabled = !pairingBusy, onClick = { pairGateway() }) {
                            Text(if (pairingBusy) "Đang ghép…" else "Ghép lại Brain Gateway")
                        }
                        Button(onClick = { startAgent() }) { Text("Khởi động / Bật lại Agent") }
                        Button(onClick = { stopAgent() }) { Text("Dừng / Kill switch") }
                        Spacer(Modifier.height(8.dp))
                        Text("Sau khi đã ghép, Agent tự khởi động khi mở app và sau khi máy khởi động lại.")
                        Text("Agent chỉ thực thi lệnh đã ký và vẫn tuân theo giới hạn bảo mật Android.")
                    }
                }
            }
        }

        if (pairing != null) {
            maybeStartAgent()
        } else {
            pairGateway()
        }
        checkGateway()
    }

    private fun copyDeviceId() {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("Android Brain Agent Device ID", deviceId))
    }

    private fun isAccessibilityEnabled(): Boolean {
        if (BrainAccessibilityService.current != null) return true
        val target = ComponentName(this, BrainAccessibilityService::class.java).flattenToString()
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
        return enabled.split(':').any { it.equals(target, ignoreCase = true) }
    }

    private fun isNotificationAccessEnabled(): Boolean =
        NotificationManagerCompat.getEnabledListenerPackages(this).contains(packageName)

    private fun openAppInfo() {
        startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
    }

    private fun openAccessibilitySettings() {
        startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
    }

    private fun openNotificationAccessSettings() {
        val component = ComponentName(this, BrainNotificationService::class.java)
        val detail = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Intent(Settings.ACTION_NOTIFICATION_LISTENER_DETAIL_SETTINGS)
                .putExtra(Settings.EXTRA_NOTIFICATION_LISTENER_COMPONENT_NAME, component.flattenToString())
        } else null
        if (detail != null && detail.resolveActivity(packageManager) != null) {
            startActivity(detail)
        } else {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }
    }

    private fun checkGateway() {
        gatewayStatus = "Đang kiểm tra…"
        Thread {
            try {
                val health = GatewayClient().health()
                val sha = health.optString("sourceSha", "unknown").take(8)
                runOnUiThread { gatewayStatus = if (health.optBoolean("ok")) "ONLINE ($sha)" else "Phản hồi không hợp lệ" }
            } catch (error: Throwable) {
                runOnUiThread { gatewayStatus = "LỖI: ${error.message?.take(160) ?: error.javaClass.simpleName}" }
            }
        }.start()
    }

    private fun pairGateway() {
        if (pairingBusy) return
        pairingBusy = true
        pairingStatus = "Đang kết nối gateway…"
        Thread {
            try {
                pairingRepository.pair()
                runOnUiThread {
                    pairingStatus = "Đã ghép với Brain Gateway"
                    pairingBusy = false
                    startAgent()
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    val message = when (error) {
                        is GatewayClient.GatewayException -> "HTTP ${error.statusCode}: ${error.message}"
                        else -> error.message ?: error.javaClass.simpleName
                    }
                    pairingStatus = "Pair thất bại: ${message.take(240)}"
                    pairingBusy = false
                }
            }
        }.start()
    }

    private fun maybeStartAgent() {
        val hasPairing = pairingRepository.load() != null
        val killSwitch = !runPreference.isEnabled()
        if (AgentStartupPolicy.shouldStart(hasPairing, killSwitch)) {
            ContextCompat.startForegroundService(this, Intent(this, AgentForegroundService::class.java))
        }
    }

    private fun startAgent() {
        AgentForegroundService.resetKillSwitch(this)
        ContextCompat.startForegroundService(this, Intent(this, AgentForegroundService::class.java))
        refreshTick++
    }

    private fun stopAgent() {
        runPreference.setEnabled(false)
        startService(Intent(this, AgentForegroundService::class.java).setAction(AgentForegroundService.ACTION_STOP))
        refreshTick++
    }

    override fun onResume() {
        super.onResume()
        refreshTick++
        maybeStartAgent()
    }
}
