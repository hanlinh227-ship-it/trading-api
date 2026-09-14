package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.AuthorizationDecision
import com.hanlinh.androidbrain.policy.RiskPolicy
import com.hanlinh.androidbrain.policy.UserPolicy
import com.hanlinh.androidbrain.protocol.Action

sealed interface AgentResult {
    data class Completed(val steps: Int) : AgentResult
    data class NeedsConfirmation(val action: Action) : AgentResult
    data class Failed(val code: String, val message: String? = null) : AgentResult
}

class AgentRuntime(
    private val riskPolicy: RiskPolicy,
    private val maxSteps: Int = 20,
) {
    fun run(
        goal: String,
        actions: List<Action>,
        userPolicy: UserPolicy,
    ): AgentResult {
        if (goal.isBlank()) return AgentResult.Failed("INVALID_GOAL")
        if (actions.size > maxSteps) return AgentResult.Failed("STEP_LIMIT")

        actions.forEach { action ->
            when (riskPolicy.authorize(action, userPolicy)) {
                AuthorizationDecision.Allowed -> Unit
                AuthorizationDecision.Denied -> return AgentResult.Failed("POLICY_DENIED")
                is AuthorizationDecision.NeedsConfirmation -> return AgentResult.NeedsConfirmation(action)
            }
        }
        return AgentResult.Completed(actions.size)
    }
}
