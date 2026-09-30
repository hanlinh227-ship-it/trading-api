package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.SendMessage
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MicroPlanTest {
    @Test
    fun classC_neverSpeculates() {
        val plan = MicroPlan(
            actions = listOf(SendMessage("contact", "hello")),
            reobserveAfter = emptySet(),
            confidence = 0.99,
        )
        assertFalse(plan.isEligibleForSpeculativeExecution())
    }

    @Test
    fun lowRiskPlan_canRunLocally() {
        val plan = MicroPlan(listOf(GlobalBack), setOf(0), 0.95)
        assertTrue(plan.isEligibleForSpeculativeExecution())
    }
}
