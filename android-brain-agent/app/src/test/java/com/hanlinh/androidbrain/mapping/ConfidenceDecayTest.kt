package com.hanlinh.androidbrain.mapping

import org.junit.Assert.assertTrue
import org.junit.Test

class ConfidenceDecayTest {
    @Test
    fun versionChange_reducesConfidence() {
        val decay = ConfidenceDecay()
        assertTrue(decay.apply(0.95, versionChanged = true, anchorMismatch = false, ageDays = 1) < 0.95)
    }

    @Test
    fun anchorMismatch_decaysMoreThanAgeAlone() {
        val decay = ConfidenceDecay()
        val ageOnly = decay.apply(0.9, versionChanged = false, anchorMismatch = false, ageDays = 30)
        val mismatch = decay.apply(0.9, versionChanged = false, anchorMismatch = true, ageDays = 30)
        assertTrue(mismatch < ageOnly)
    }
}
