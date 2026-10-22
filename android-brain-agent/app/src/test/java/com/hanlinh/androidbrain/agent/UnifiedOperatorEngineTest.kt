package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.GlobalBack
import org.junit.Assert.assertEquals
import org.junit.Test

class UnifiedOperatorEngineTest {
    @Test
    fun familiarVerifiedPath_executesMultipleLocalStepsWithoutCloudPerStep() {
        var observationCounter = 0
        val engine = UnifiedOperatorEngine(
            initialSession = PersistentOperatorSession(
                taskId = "t1",
                goal = "navigate familiar flow",
                allowedPackages = setOf("com.example"),
                persistence = setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE),
            ),
            observationProvider = {
                observationCounter += 1
                observation("sem-$observationCounter")
            },
            localPlanProvider = { MicroPlan(listOf(GlobalBack), emptySet(), 0.98) },
            signalProvider = {
                InferenceSignals(0.98, 0.95, 0.95, 0.95, 0.05, RiskClass.A, true, 0, 0.05)
            },
            actionExecutor = { true },
        )
        val result = engine.runUntilEscalation(maxLocalActions = 3)
        assertEquals(3, result.executedLocalActions)
        assertEquals(0, result.cloudRequests)
    }

    private fun observation(semantic: String) = UnifiedObservation(
        timestampMs = 1,
        packageName = "com.example",
        orientation = "PORTRAIT",
        screenWidth = 1080,
        screenHeight = 2400,
        semanticFingerprint = semantic,
        semanticNodeCount = 20,
    )
}
