package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskClass
import org.junit.Assert.assertEquals
import org.junit.Test

class DynamicInferenceBudgetTest {
    @Test
    fun familiarLowRiskState_executesLocally() {
        val directive = DynamicInferenceBudget().decide(
            InferenceSignals(
                confidence = 0.97,
                knownScreen = 0.95,
                knownTransition = 0.94,
                semanticCompleteness = 0.95,
                visualAmbiguity = 0.05,
                riskClass = RiskClass.A,
                reversible = true,
                failureStreak = 0,
                taskNovelty = 0.05,
            )
        )
        assertEquals(InferenceDirective.LOCAL_EXECUTE, directive)
    }

    @Test
    fun repeatedFailure_escalatesRecovery() {
        val directive = DynamicInferenceBudget().decide(
            InferenceSignals(0.8, 0.8, 0.8, 0.8, 0.2, RiskClass.A, true, 3, 0.2)
        )
        assertEquals(InferenceDirective.CLOUD_RECOVERY, directive)
    }
}
