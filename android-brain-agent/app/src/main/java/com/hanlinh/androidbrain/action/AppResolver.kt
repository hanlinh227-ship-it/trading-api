package com.hanlinh.androidbrain.action

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build

class AppResolver(private val context: Context) {
    fun findPackageByLabel(label: String): String? {
        val query = label.trim().lowercase()
        if (query.isBlank()) return null
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val packageManager = context.packageManager
        val apps = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            packageManager.queryIntentActivities(intent, PackageManager.ResolveInfoFlags.of(0L))
        } else {
            @Suppress("DEPRECATION")
            packageManager.queryIntentActivities(intent, 0)
        }
        return apps.firstOrNull {
            it.loadLabel(packageManager).toString().trim().lowercase() == query ||
                it.activityInfo.packageName.lowercase() == query
        }?.activityInfo?.packageName
    }
}
