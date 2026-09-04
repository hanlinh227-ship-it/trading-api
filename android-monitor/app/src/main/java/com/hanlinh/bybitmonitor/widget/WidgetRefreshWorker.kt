package com.hanlinh.bybitmonitor.widget

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
