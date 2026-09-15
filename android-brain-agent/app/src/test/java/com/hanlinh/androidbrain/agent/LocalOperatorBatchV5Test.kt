package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.GlobalBack
import org.junit.Assert.assertEquals
import org.junit.Test

class LocalOperatorBatchV5Test {
    @Test
    fun cloudIssuedBatch_executesExactlyOnceLocallyWithoutPerActionCloud() {
        var observationCounter = 0
        var executed = 0
        val result = LocalOperatorBatchExecutor().execute(
            session = PersistentOperatorSession(
                taskId = "task-1",
                goal = "navigate familiar path",
                allowedPackages = setOf("com.example"),
                persistence = setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE),
                capabilityScope = setOf("ui.navigate"),
                riskCeiling = RiskClass.A,
            ),
            actions = listOf(GlobalBack, GlobalBack, GlobalBack),
            observationProvider = {
                observationCounter += 1
                UnifiedObservation(
                    timestampMs = observationCounter.toLong(),
                    packageName = "com.example",
                    orientation = "PORTRAIT",
                    screenWidth = 1080,
                    screenHeight = 2400,
                    semanticFingerprint = "sem-$observationCounter",
                    semanticNodeCount = 12,
                )
            },
            actionExecutor = {
                executed += 1
                true
            },
        )

        assertEquals(3, executed)
        assertEquals(3, result.executedLocalActions)
        assertEquals(0, result.cloudRequests)
        assertEquals("LOCAL_BATCH_VERIFIED", result.reason)
    }
}
