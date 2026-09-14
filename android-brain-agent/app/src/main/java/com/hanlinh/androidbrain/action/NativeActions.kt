package com.hanlinh.androidbrain.action

import android.content.Context
import android.content.Intent
import android.net.Uri
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.OpenUrl

class NativeActions(private val context: Context) {
    fun launch(action: LaunchApp): Boolean {
        val intent = context.packageManager.getLaunchIntentForPackage(action.packageName) ?: return false
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            true
        } catch (_: Throwable) {
            false
        }
    }

    fun openUrl(action: OpenUrl): Boolean {
        val uri = try { Uri.parse(action.url) } catch (_: Throwable) { return false }
        if (uri.scheme !in setOf("https", "http")) return false
        val intent = Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            true
        } catch (_: Throwable) {
            false
        }
    }
}
