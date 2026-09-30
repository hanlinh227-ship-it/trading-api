package com.hanlinh.androidbrain.network

import com.hanlinh.androidbrain.agent.PersistencePolicy
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.ReadScreen
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class V5MicroPlanParserTest {
    @Test
    fun responseCarriesServerAuthorizedTaskContextAndTypedActions() {
        val json = JSONObject()
            .put("taskId", "t1")
            .put("mode", "cloud")
            .put("task", JSONObject()
                .put("taskId", "t1")
                .put("goal", "inspect app")
                .put("status", "PLANNING")
                .put("riskClass", "B")
                .put("capabilityScope", JSONArray(listOf("ui.navigate", "ui.write")))
                .put("allowedPackages", JSONArray(listOf("com.example")))
                .put("persistencePolicy", JSONArray(listOf("UNTIL_USER_STOP", "UNTIL_APP_SCOPE_EXIT"))))
            .put("actions", JSONArray().put(JSONObject().put("type", "read_screen")))

        val parsed = V5MicroPlanParser.parse(json)
        assertEquals("t1", parsed.task.taskId)
        assertEquals(RiskClass.B, parsed.task.riskCeiling)
        assertEquals(setOf("ui.navigate", "ui.write"), parsed.task.capabilityScope)
        assertEquals(setOf("com.example"), parsed.task.allowedPackages)
        assertEquals(setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT), parsed.task.persistence)
        assertEquals(ReadScreen, parsed.actions.single())
    }
}
