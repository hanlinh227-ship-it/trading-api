package com.hanlinh.androidbrain.execution

import com.hanlinh.androidbrain.protocol.Swipe
import org.junit.Assert.assertTrue
import org.junit.Test

class AdaptiveActionSchedulerTest {
    @Test
    fun knownFastScreen_usesFastSwipeEnvelope() {
        val scheduler = AdaptiveActionScheduler()
        val timing = scheduler.timingFor(
            "com.example",
            "screenA",
            swipeAction(),
            profile(medianMs = 70),
        )
        assertTrue(timing.gestureDurationMs in 60L..120L)
    }

    @Test
    fun repeatedMisses_backOffGestureDuration() {
        val scheduler = AdaptiveActionScheduler()
        val first = scheduler.timingFor("com.example", "screenA", swipeAction(), profile(medianMs = 70))
        val retry = scheduler.afterFailedDispatch(first)
        assertTrue(retry.gestureDurationMs > first.gestureDurationMs)
        assertTrue(retry.gestureDurationMs <= 220L)
    }

    private fun swipeAction() = Swipe(900, 1200, 200, 1200, 300)
    private fun profile(medianMs: Long) = ActionTimingProfile(
        packageName = "com.example",
        screenId = "screenA",
        medianActionToEventMs = medianMs,
        p90ActionToEventMs = medianMs + 40,
        reliableSwipeDurationMs = medianMs,
    )
}
