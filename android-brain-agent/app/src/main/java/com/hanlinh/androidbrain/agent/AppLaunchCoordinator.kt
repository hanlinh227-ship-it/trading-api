package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.protocol.LaunchApp

enum class AppLaunchResult {
    VERIFIED_DIRECT,
    VERIFIED_ACCESSIBILITY_FALLBACK,
    FAILED_POSTCONDITION,
}

class AppLaunchCoordinator(
    private val directLaunch: (LaunchApp) -> Boolean,
    private val verifyForeground: (String) -> Boolean,
    private val accessibilityFallback: (LaunchApp) -> Boolean,
) {
    fun launch(action: LaunchApp): AppLaunchResult {
        val directDispatched = directLaunch(action)
        if (directDispatched && verifyForeground(action.packageName)) {
            return AppLaunchResult.VERIFIED_DIRECT
        }

        val fallbackDispatched = accessibilityFallback(action)
        if (fallbackDispatched && verifyForeground(action.packageName)) {
            return AppLaunchResult.VERIFIED_ACCESSIBILITY_FALLBACK
        }

        return AppLaunchResult.FAILED_POSTCONDITION
    }
}
