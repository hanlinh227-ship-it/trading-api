package com.hanlinh.androidbrain.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.hanlinh.androidbrain.MainActivity
import com.hanlinh.androidbrain.network.AgentConnectionManager
import com.hanlinh.androidbrain.network.PairingRepository

class AgentForegroundService : Service() {
    companion object {
        const val CHANNEL_ID = "android_brain_agent"
        const val NOTIFICATION_ID = 1107
        const val ACTION_STOP = "com.hanlinh.androidbrain.STOP_AGENT"

        @Volatile
        var killSwitchActive: Boolean = false
            private set

        fun resetKillSwitch(context: android.content.Context) {
            AgentRunPreference(context).setEnabled(true)
            killSwitchActive = false
        }
    }

    private var connectionManager: AgentConnectionManager? = null

    override fun onCreate() {
        super.onCreate()
        killSwitchActive = !AgentRunPreference(this).isEnabled()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            AgentRunPreference(this).setEnabled(false)
            killSwitchActive = true
            connectionManager?.stop()
            connectionManager = null
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }

        if (!AgentRunPreference(this).isEnabled()) {
            killSwitchActive = true
            stopSelf()
            return START_NOT_STICKY
        }

        killSwitchActive = false
        startAsForeground()
        if (connectionManager == null) {
            PairingRepository(this).load()?.let { pairing ->
                connectionManager = AgentConnectionManager(this, pairing).also { it.start() }
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        connectionManager?.stop()
        connectionManager = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startAsForeground() {
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
        } else {
            0
        }
        ServiceCompat.startForeground(this, NOTIFICATION_ID, buildNotification(), type)
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Android Brain Agent", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    private fun buildNotification(): android.app.Notification {
        val openIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, AgentForegroundService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle("Android Brain Agent đang hoạt động")
            .setContentText("Kết nối Brain Gateway qua Internet. Nhấn Dừng để khóa thực thi.")
            .setContentIntent(openIntent)
            .setOngoing(true)
            .addAction(0, "Dừng", stopIntent)
            .build()
    }
}
