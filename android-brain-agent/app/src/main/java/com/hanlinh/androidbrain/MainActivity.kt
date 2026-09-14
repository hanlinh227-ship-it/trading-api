package com.hanlinh.androidbrain

import android.content.Intent
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
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService

class MainActivity : ComponentActivity() {
    private var refreshTick by mutableStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            refreshTick
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Column(
                        modifier = Modifier.padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text("Android Brain Agent", style = MaterialTheme.typography.headlineMedium)
                        Text("Gateway: ${BuildConfig.GATEWAY_BASE_URL}")
                        Text("Accessibility: ${if (BrainAccessibilityService.current != null) "BẬT" else "CHƯA BẬT"}")
                        Text("Shizuku: ${if (ShizukuActions().available()) "PHÁT HIỆN" else "KHÔNG CÓ / CHƯA BẬT"}")
                        Text("Kill switch: ${if (AgentForegroundService.killSwitchActive) "ĐANG KHÓA" else "SẴN SÀNG"}")

                        Button(onClick = { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }) {
                            Text("Bật Accessibility")
                        }
                        Button(onClick = { startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }) {
                            Text("Bật Notification Access")
                        }
                        Button(onClick = {
                            AgentForegroundService.resetKillSwitch()
                            ContextCompat.startForegroundService(
                                this@MainActivity,
                                Intent(this@MainActivity, AgentForegroundService::class.java)
                            )
                            refreshTick++
                        }) {
                            Text("Khởi động Agent")
                        }
                        Button(onClick = {
                            startService(Intent(this@MainActivity, AgentForegroundService::class.java).setAction(AgentForegroundService.ACTION_STOP))
                            refreshTick++
                        }) {
                            Text("Dừng / Kill switch")
                        }
                        Spacer(Modifier.height(8.dp))
                        Text("V1 không root. Screen Vision chỉ hoạt động sau khi bạn cấp consent cho từng phiên.")
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refreshTick++
    }
}
