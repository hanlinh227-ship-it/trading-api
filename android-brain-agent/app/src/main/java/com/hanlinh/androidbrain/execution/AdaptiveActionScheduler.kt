package com.hanlinh.androidbrain.execution

import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.Swipe

class AdaptiveActionScheduler {
    fun timingFor(
        packageName: String,
        screenId: String,
        action: Action,
        profile: ActionTimingProfile?,
    ): ActionTiming {
        require(packageName.isNotBlank())
        require(screenId.isNotBlank())

        val gestureDuration = when (action) {
            is Swipe -> {
                val candidate = profile?.reliableSwipeDurationMs
                    ?: profile?.medianActionToEventMs
                    ?: DEFAULT_SWIPE_MS
                candidate.coerceIn(FAST_SWIPE_MIN_MS, FAST_SWIPE_MAX_MS)
            }
            else -> DEFAULT_TAP_GESTURE_MS
        }
        val settleMedian = profile?.medianActionToEventMs ?: DEFAULT_SETTLE_MS
        val settleP90 = profile?.p90ActionToEventMs ?: DEFAULT_MAX_SETTLE_MS
        return ActionTiming(
            gestureDurationMs = gestureDuration,
            minimumSettleMs = settleMedian.coerceIn(0, MAX_SETTLE_MS),
            maximumSettleMs = settleP90.coerceAtLeast(settleMedian).coerceIn(0, MAX_SETTLE_MS),
            eventDrivenCompletion = true,
        )
    }

    fun afterFailedDispatch(timing: ActionTiming): ActionTiming {
        val backedOff = maxOf(timing.gestureDurationMs + BACKOFF_INCREMENT_MS, (timing.gestureDurationMs * 3) / 2)
            .coerceAtMost(FALLBACK_SWIPE_MAX_MS)
        return timing.copy(
            gestureDurationMs = backedOff,
            maximumSettleMs = maxOf(timing.maximumSettleMs, backedOff + BACKOFF_SETTLE_MS).coerceAtMost(MAX_SETTLE_MS),
        )
    }

    fun applyTiming(action: Action, timing: ActionTiming): Action = when (action) {
        is Swipe -> action.copy(durationMs = timing.gestureDurationMs)
        else -> action
    }

    companion object {
        const val FAST_SWIPE_MIN_MS = 60L
        const val FAST_SWIPE_MAX_MS = 120L
        const val FALLBACK_SWIPE_MAX_MS = 220L
        private const val DEFAULT_SWIPE_MS = 90L
        private const val DEFAULT_TAP_GESTURE_MS = 60L
        private const val DEFAULT_SETTLE_MS = 60L
        private const val DEFAULT_MAX_SETTLE_MS = 250L
        private const val MAX_SETTLE_MS = 1_500L
        private const val BACKOFF_INCREMENT_MS = 30L
        private const val BACKOFF_SETTLE_MS = 120L
    }
}
