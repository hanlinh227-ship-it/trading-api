package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.protocol.LaunchApp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppLaunchCoordinatorTest {
    @Test
    fun `direct launch is accepted only after foreground verification`() {
        var fallbackCalled = false
        val coordinator = AppLaunchCoordinator(
            directLaunch = { true },
            verifyForeground = { true },
            accessibilityFallback = { fallbackCalled = true; true },
        )

        val result = coordinator.launch(LaunchApp("com.example.messages"))

        assertEquals(AppLaunchResult.VERIFIED_DIRECT, result)
        assertFalse(fallbackCalled)
    }

    @Test
    fun `blocked direct launch falls back to accessibility and verifies target`() {
        var verificationCalls = 0
        var fallbackCalled = false
        val coordinator = AppLaunchCoordinator(
            directLaunch = { true },
            verifyForeground = {
                verificationCalls += 1
                verificationCalls >= 2
            },
            accessibilityFallback = { fallbackCalled = true; true },
        )

        val result = coordinator.launch(LaunchApp("com.example.messages"))

        assertEquals(AppLaunchResult.VERIFIED_ACCESSIBILITY_FALLBACK, result)
        assertTrue(fallbackCalled)
        assertEquals(2, verificationCalls)
    }

    @Test
    fun `launch never reports success when neither path reaches target foreground`() {
        val coordinator = AppLaunchCoordinator(
            directLaunch = { true },
            verifyForeground = { false },
            accessibilityFallback = { true },
        )

        assertEquals(
            AppLaunchResult.FAILED_POSTCONDITION,
            coordinator.launch(LaunchApp("com.example.messages")),
        )
    }
}
