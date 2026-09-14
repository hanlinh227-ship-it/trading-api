package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskPolicy
import com.hanlinh.androidbrain.policy.UserPolicy
import com.hanlinh.androidbrain.protocol.LaunchApp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentRuntimeTest {
    @Test fun runtime_enforces_step_limit() {
        val runtime = AgentRuntime(RiskPolicy(), maxSteps = 2)
        val result = runtime.run(
            goal = "open repeatedly",
            actions = listOf(
                LaunchApp("a"),
                LaunchApp("b"),
                LaunchApp("c")
            ),
            userPolicy = UserPolicy.defaults()
        )
        assertTrue(result is AgentResult.Failed)
        assertEquals("STEP_LIMIT", (result as AgentResult.Failed).code)
    }

    @Test fun class_c_stops_runtime_for_confirmation() {
        val runtime = AgentRuntime(RiskPolicy())
        val result = runtime.run(
            goal = "delete data",
            actions = listOf(com.hanlinh.androidbrain.protocol.DeleteData(100)),
            userPolicy = UserPolicy.defaults()
        )
        assertTrue(result is AgentResult.NeedsConfirmation)
    }
}
