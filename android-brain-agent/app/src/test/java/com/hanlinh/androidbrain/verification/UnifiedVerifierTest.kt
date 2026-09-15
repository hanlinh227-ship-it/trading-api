package com.hanlinh.androidbrain.verification

import com.hanlinh.androidbrain.perception.UnifiedObservation
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UnifiedVerifierTest {
    @Test
    fun unchangedAccessibility_butChangedVisual_isProgress() {
        val before = observation(semantic = "same", visual = "aaa")
        val after = observation(semantic = "same", visual = "bbb")
        val result = UnifiedVerifier().verifyTransition(before, after)
        assertTrue(result.changed)
        assertTrue(result.success)
    }

    @Test
    fun unchangedSemanticAndVisual_isNoOp() {
        val before = observation(semantic = "same", visual = "aaa")
        val result = UnifiedVerifier().verifyTransition(before, before)
        assertFalse(result.changed)
        assertFalse(result.success)
    }

    @Test
    fun domainStateChange_provesProgressWithoutSemanticChange() {
        val before = observation("same", "aaa", "board-1")
        val after = observation("same", "aaa", "board-2")
        assertTrue(UnifiedVerifier().verifyTransition(before, after).success)
    }

    private fun observation(semantic: String, visual: String?, domain: String? = null) = UnifiedObservation(
        timestampMs = 1,
        packageName = "com.example",
        orientation = "PORTRAIT",
        screenWidth = 1080,
        screenHeight = 2400,
        semanticFingerprint = semantic,
        perceptualHash = visual,
        semanticNodeCount = 10,
        skillSpecificState = domain,
    )
}
