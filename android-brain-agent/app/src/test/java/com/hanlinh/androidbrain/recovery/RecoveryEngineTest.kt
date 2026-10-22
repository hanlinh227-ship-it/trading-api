package com.hanlinh.androidbrain.recovery

import org.junit.Assert.assertEquals
import org.junit.Test

class RecoveryEngineTest {
    @Test
    fun recovery_prefersVerifiedSelectorBeforeCloud() {
        val result = RecoveryEngine().next(RecoveryContext(hasVerifiedAlternateSelector = true))
        assertEquals(RecoveryDirective.USE_VERIFIED_SELECTOR, result)
    }

    @Test
    fun staleObservation_reobservesFirst() {
        val result = RecoveryEngine().next(RecoveryContext(observationStale = true, hasVerifiedAlternateSelector = true))
        assertEquals(RecoveryDirective.REOBSERVE, result)
    }

    @Test
    fun exhaustedStateBudget_pauses() {
        val result = RecoveryEngine(maxAttemptsPerState = 3).next(RecoveryContext(attemptsForState = 3))
        assertEquals(RecoveryDirective.PAUSE_OR_FAIL, result)
    }
}
