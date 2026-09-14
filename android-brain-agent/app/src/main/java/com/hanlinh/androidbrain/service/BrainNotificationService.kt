package com.hanlinh.androidbrain.service

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.hanlinh.androidbrain.perception.NotificationSnapshot
import java.util.concurrent.CopyOnWriteArrayList

class BrainNotificationService : NotificationListenerService() {
    companion object {
        private val snapshots = CopyOnWriteArrayList<NotificationSnapshot>()
        fun recent(limit: Int = 50): List<NotificationSnapshot> = snapshots.takeLast(limit.coerceIn(1, 100))
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        sbn ?: return
        val extras = sbn.notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
        snapshots += NotificationSnapshot(
            packageName = sbn.packageName,
            title = title?.take(500),
            text = text?.take(2000),
            postedAtMs = sbn.postTime,
        )
        while (snapshots.size > 100) snapshots.removeAt(0)
    }
}
