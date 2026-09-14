package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VerifierTest {
    private val verifier = Verifier()

    @Test fun action_is_not_success_until_postcondition_matches() {
        val withoutSent = AccessibilitySnapshot("com.chat", "Chat", emptyList())
        assertFalse(verifier.verify(VerificationRule.NodeTextPresent("Sent"), withoutSent).satisfied)
    }

    @Test fun foreground_package_can_verify() {
        val snapshot = AccessibilitySnapshot("com.android.settings", "Settings", emptyList())
        assertTrue(verifier.verify(VerificationRule.ForegroundPackage("com.android.settings"), snapshot).satisfied)
    }
}
