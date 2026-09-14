package com.hanlinh.androidbrain.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.hanlinh.androidbrain.network.PairingRepository

class AgentBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action != Intent.ACTION_BOOT_COMPLETED && action != Intent.ACTION_MY_PACKAGE_REPLACED) return

        val hasPairing = PairingRepository(context).load() != null
        val killSwitch = !AgentRunPreference(context).isEnabled()
        if (AgentStartupPolicy.shouldStart(hasPairing, killSwitch)) {
            ContextCompat.startForegroundService(context, Intent(context, AgentForegroundService::class.java))
        }
    }
}
