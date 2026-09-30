package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.SetText
import org.junit.Assert.assertEquals
import org.junit.Test

class LocalPolicyClampV5Test {
    @Test
    fun classBAction_withoutWriteScope_escalatesBeforeDispatch() {
        var dispatched = 0
        val engine = engine(
            session = session(
                capabilityScope = setOf("ui.navigate"),
                riskCeiling = RiskClass.B,
            ),
            onDispatch = { dispatched += 1 },
        )

        val result = engine.runUntilEscalation(1)
        assertEquals("LOCAL_POLICY_DENIED", result.reason)
        assertEquals(0, dispatched)
        assertEquals(1, result.cloudRequests)
    }

    @Test
    fun classBAction_withWriteScopeAndRiskCeiling_executesLocally() {
        var dispatched = 0
        val engine = engine(
            session = session(
                capabilityScope = setOf("ui.navigate", "ui.write"),
                riskCeiling = RiskClass.B,
            ),
            onDispatch = { dispatched += 1 },
        )

        val result = engine.runUntilEscalation(1)
        assertEquals("LOCAL_BUDGET_REACHED", result.reason)
        assertEquals(1, dispatched)
        assertEquals(0, result.cloudRequests)
    }

    private fun engine(
        session: PersistentOperatorSession,
        onDispatch: () -> Unit,
    ): UnifiedOperatorEngine {
        var n = 0
        return UnifiedOperatorEngine(
            initialSession = session,
            observationProvider = {
                n += 1
                observation("s$n")
            },
            localPlanProvider = { MicroPlan(listOf(SetText("n:1", "hello")), emptySet(), 0.99) },
            actionExecutor = {
                onDispatch()
                true
            },
        )
    }

    private fun session(
        capabilityScope: Set<String>,
        riskCeiling: RiskClass,
    ) = PersistentOperatorSession(
        taskId = "task-policy",
        goal = "edit text",
        allowedPackages = setOf("com.example"),
        persistence = setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE),
        capabilityScope = capabilityScope,
        riskCeiling = riskCeiling,
    )

    private fun observation(semantic: String) = UnifiedObservation(
        timestampMs = 1,
        packageName = "com.example",
        orientation = "PORTRAIT",
        screenWidth = 1080,
        screenHeight = 2400,
        semanticFingerprint = semantic,
        semanticNodeCount = 10,
    )
}
