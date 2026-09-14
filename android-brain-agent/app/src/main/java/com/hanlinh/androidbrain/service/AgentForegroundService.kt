package com.hanlinh.androidbrain.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.hanlinh.androidbrain.MainActivity

class AgentForegroundService : Service() {
    companion object {
        const val CHANNEL_ID = "android_brain_agent"
        const val NOTIFICATION_ID = 1107
        const val ACTION_STOP = "com.hanlinh.androidbrain.STOP_AGENT"
        @Volatile var killSwitchActive: Boolean = false
            private set

        fun resetKillSwitch() { killSwitchActive = false }
    }

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            killSwitchActive = true
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        if (killSwitchActive) return START_NOT_STICKY
        startForeground(NOTIFICATION_ID, buildNotification())
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Android Brain Agent", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    private fun buildNotification(): android.app.Notification {
        val openIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopIntent = PendingIntent.getService(
            this, 1, Intent(this, AgentForegroundService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle("Android Brain Agent đang hoạt động")
            .setContentText("Nhấn Dừng để khóa thực thi tự động")
            .setContentIntent(openIntent)
            .setOngoing(true)
            .addAction(0, "Dừng", stopIntent)
            .build()
    }
}
