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
import com.hanlinh.androidbrain.action.ShizukuActions
import com.hanlinh.androidbrain.network.GatewayClient
import com.hanlinh.androidbrain.network.PairingRepository
import com.hanlinh.androidbrain.security.DeviceIdentity
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService
import com.hanlinh.androidbrain.service.BrainNotificationService

class MainActivity : ComponentActivity() {
    private var refreshTick by mutableStateOf(0)
    private var pairingStatus by mutableStateOf("Chưa ghép với gateway")
    private var gatewayStatus by mutableStateOf("Chưa kiểm tra")
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
                        modifier = Modifier
                            .verticalScroll(rememberScrollState())
                            .padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("Android Brain Agent", style = MaterialTheme.typography.headlineMedium)
                        Text("V1.0.2 DNS fallback")
                        Text("Gateway: $gatewayStatus")
                        Text(pairingStatus)
                        Text("Device ID: $deviceId")
                        Button(onClick = { copyDeviceId() }) { Text("Sao chép Device ID cho GPT") }

                        Text("Accessibility: ${if (isAccessibilityEnabled()) "BẬT" else "CHƯA BẬT"}")
                        Text("Notification Access: ${if (isNotificationAccessEnabled()) "BẬT" else "CHƯA BẬT"}")
                        Text("Shizuku: ${if (ShizukuActions().available()) "PHÁT HIỆN" else "TÙY CHỌN / CHƯA BẬT"}")
                        Text("Kill switch: ${if (AgentForegroundService.killSwitchActive) "ĐANG KHÓA" else "SẴN SÀNG"}")

                        Text("0. Nếu APK được cài ngoài Play Store trên Android 13+: mở App info → menu ⋮ → Cho phép cài đặt hạn chế / Allow restricted settings. Android có thể chặn Accessibility và Notification Access cho đến khi bước này được cho phép.")
                        Button(onClick = { openAppInfo() }) { Text("0. Mở App info / Restricted Settings") }

                        Button(onClick = { openAccessibilitySettings() }) {
                            Text("1. Bật Accessibility")
                        }
                        Button(onClick = { openNotificationAccessSettings() }) {
                            Text("2. Bật Notification Access")
                        }
                        Button(onClick = { checkGateway() }) {
                            Text("Kiểm tra Brain Gateway")
                        }
                        Button(enabled = !pairingBusy, onClick = { pairGateway() }) {
                            Text(if (pairingBusy) "Đang ghép…" else "3. Pair / Khôi phục Pair với Brain Gateway")
                        }
                        Button(onClick = { startAgent() }) { Text("4. Khởi động Agent") }
                        Button(onClick = { stopAgent() }) { Text("Dừng / Kill switch") }
                        Spacer(Modifier.height(8.dp))
                        Text("V1.0.2 tự thử DNS hệ thống, Google DNS-over-HTTPS và Cloudflare DNS-over-HTTPS khi kết nối Gateway.")
                        Text("Sau khi bật quyền, quay lại app. Trạng thái sẽ tự cập nhật. Nếu Pair từng dở dang, nút Pair có thể khôi phục phiên bằng chữ ký khóa riêng của chính điện thoại.")
                        Text("Sau khi Pair thành công, sao chép Device ID và gửi cho GPT để chạy acceptance test.")
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
