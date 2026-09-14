package com.hanlinh.androidbrain.action

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Telephony

class AppResolver(private val context: Context) {
    fun findPackageByLabel(label: String): String? {
        val query = normalize(label)
        if (query.isBlank()) return null

        if (query in MESSAGE_ALIASES) {
            Telephony.Sms.getDefaultSmsPackage(context)?.let { packageName ->
                if (isLaunchable(packageName)) return packageName
            }
            resolveSendToSmsPackage()?.let { packageName ->
                if (isLaunchable(packageName)) return packageName
            }
        }

        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val packageManager = context.packageManager
        return queryActivities(intent).firstOrNull {
            normalize(it.loadLabel(packageManager).toString()) == query ||
                normalize(it.activityInfo.packageName) == query
        }?.activityInfo?.packageName
    }

    fun labelForPackage(packageName: String): String? {
        val packageManager = context.packageManager
        return try {
            val info = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                packageManager.getApplicationInfo(packageName, PackageManager.ApplicationInfoFlags.of(0L))
            } else {
                @Suppress("DEPRECATION")
                packageManager.getApplicationInfo(packageName, 0)
            }
            packageManager.getApplicationLabel(info).toString().trim().ifBlank { null }
        } catch (_: Throwable) {
            null
        }
    }

    fun findHomePackage(): String? {
        val homeIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        val resolveInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.packageManager.resolveActivity(homeIntent, PackageManager.ResolveInfoFlags.of(PackageManager.MATCH_DEFAULT_ONLY.toLong()))
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.resolveActivity(homeIntent, PackageManager.MATCH_DEFAULT_ONLY)
        }
        return resolveInfo?.activityInfo?.packageName
            ?.takeUnless { it == "android" || it == "com.android.internal.app.ResolverActivity" }
    }

    private fun resolveSendToSmsPackage(): String? {
        val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:"))
        val resolveInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.packageManager.resolveActivity(intent, PackageManager.ResolveInfoFlags.of(PackageManager.MATCH_DEFAULT_ONLY.toLong()))
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
        }
        return resolveInfo?.activityInfo?.packageName
    }

    private fun isLaunchable(packageName: String): Boolean =
        context.packageManager.getLaunchIntentForPackage(packageName) != null

    private fun queryActivities(intent: Intent) = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        context.packageManager.queryIntentActivities(intent, PackageManager.ResolveInfoFlags.of(0L))
    } else {
        @Suppress("DEPRECATION")
        context.packageManager.queryIntentActivities(intent, 0)
    }

    private fun normalize(value: String): String =
        value.trim().lowercase().replace(Regex("\\s+"), " ")

    companion object {
        private val MESSAGE_ALIASES = setOf(
            "messages",
            "message",
            "sms",
            "messaging",
            "tin nhắn",
            "tin nhan",
            "nhắn tin",
            "nhan tin",
        )
    }
}
