package com.hanlinh.androidbrain.service

import android.content.Context

class AgentRunPreference(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun isEnabled(): Boolean = prefs.getBoolean(KEY_ENABLED, true)

    fun setEnabled(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_ENABLED, enabled).apply()
    }

    companion object {
        private const val PREFS = "android_brain_agent_run_state"
        private const val KEY_ENABLED = "enabled"
    }
}
