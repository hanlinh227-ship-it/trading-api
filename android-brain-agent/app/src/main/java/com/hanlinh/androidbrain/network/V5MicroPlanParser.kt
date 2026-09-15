package com.hanlinh.androidbrain.network

import com.hanlinh.androidbrain.agent.PersistencePolicy
import com.hanlinh.androidbrain.agent.PersistentOperatorSession
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.TypedActionCodec
import org.json.JSONArray
import org.json.JSONObject

data class V5MicroPlanResponse(
    val task: PersistentOperatorSession,
    val actions: List<Action>,
    val mode: String,
)

/** Parses a V5 micro-plan without widening authority beyond the server-returned task context. */
object V5MicroPlanParser {
    private const val MAX_ACTIONS = 8

    fun parse(json: JSONObject): V5MicroPlanResponse {
        val taskJson = json.getJSONObject("task")
        val rootTaskId = json.getString("taskId")
        val taskId = taskJson.optString("taskId", rootTaskId)
        require(taskId == rootTaskId) { "micro-plan task mismatch" }

        val actionsJson = json.optJSONArray("actions") ?: JSONArray()
        require(actionsJson.length() <= MAX_ACTIONS) { "micro-plan exceeds local action bound" }

        val task = PersistentOperatorSession(
            taskId = taskId,
            goal = taskJson.getString("goal"),
            allowedPackages = taskJson.stringSet("allowedPackages"),
            persistence = taskJson.persistenceSet(),
            capabilityScope = taskJson.stringSet("capabilityScope"),
            riskCeiling = RiskClass.valueOf(taskJson.getString("riskClass")),
            terminal = taskJson.optString("status") in TERMINAL_STATUSES,
        )
        val actions = buildList {
            for (index in 0 until actionsJson.length()) {
                add(TypedActionCodec.decode(actionsJson.getJSONObject(index).toString()))
            }
        }
        return V5MicroPlanResponse(
            task = task,
            actions = actions,
            mode = json.optString("mode", "cloud").ifBlank { "cloud" },
        )
    }

    private fun JSONObject.stringSet(name: String): Set<String> {
        val values = optJSONArray(name) ?: JSONArray()
        return buildSet {
            for (index in 0 until values.length()) {
                val value = values.getString(index)
                require(value.isNotBlank()) { "$name contains blank value" }
                add(value)
            }
        }
    }

    private fun JSONObject.persistenceSet(): Set<PersistencePolicy> {
        val values = optJSONArray("persistencePolicy") ?: JSONArray().put("UNTIL_GOAL_COMPLETE")
        return buildSet {
            for (index in 0 until values.length()) {
                add(PersistencePolicy.valueOf(values.getString(index)))
            }
        }.ifEmpty { setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE) }
    }

    private val TERMINAL_STATUSES = setOf("COMPLETED", "FAILED", "CANCELLED")
}
