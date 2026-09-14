package com.hanlinh.androidbrain.action

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager

class AppResolver(private val context: Context) {
    fun findPackageByLabel(label: String): String? {
        val query = label.trim().lowercase()
        if (query.isBlank()) return null
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val flags = if (android.os.Build.VERSION.SDK_INT >= 33) {
            PackageManager.ResolveInfoFlags.of(0)
        } else null
        @Suppress("DEPRECATION")
        val apps = if (flags != null) {
            context.packageManager.queryIntentActivities(intent, flags)
        } else {
            context.packageManager.queryIntentActivities(intent, 0)
        }
        return apps.firstOrNull {
            it.loadLabel(context.packageManager).toString().trim().lowercase() == query ||
                it.activityInfo.packageName.lowercase() == query
        }?.activityInfo?.packageName
    }
}
