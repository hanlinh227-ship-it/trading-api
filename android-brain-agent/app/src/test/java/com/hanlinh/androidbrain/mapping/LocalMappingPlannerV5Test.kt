package com.hanlinh.androidbrain.mapping

import com.hanlinh.androidbrain.agent.MicroPlan
import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.protocol.GlobalBack
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalMappingPlannerV5Test {
    @Test
    fun exactVerifiedScreen_reusesTypedActionLocally() {
        val store = InMemoryAppMappingStore()
        val planner = LocalMappingPlanner(store)
        val before = observation("before")
        val after = observation("after")
        planner.recordVerifiedTransition(before, GlobalBack, after, latencyMs = 75)

        val plan = planner.planFor(before)
        assertTrue(plan is MicroPlan)
        assertEquals(GlobalBack, plan!!.actions.single())
    }

    @Test
    fun changedScreen_doesNotBlindlyReplayOldTransition() {
        val store = InMemoryAppMappingStore()
        val planner = LocalMappingPlanner(store)
        planner.recordVerifiedTransition(observation("before"), GlobalBack, observation("after"), latencyMs = 75)

        assertNull(planner.planFor(observation("different")))
    }

    private fun observation(semantic: String) = UnifiedObservation(
        timestampMs = 100,
        packageName = "com.example",
        appVersionHint = "5.0",
        orientation = "PORTRAIT",
        screenWidth = 1080,
        screenHeight = 2400,
        semanticFingerprint = semantic,
        semanticNodeCount = 20,
    )
}
