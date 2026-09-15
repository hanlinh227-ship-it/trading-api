package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskClass

enum class PersistencePolicy {
    UNTIL_GOAL_COMPLETE,
    UNTIL_USER_STOP,
    UNTIL_APP_SCOPE_EXIT,
}

data class PersistentOperatorSession(
    val taskId: String,
    val goal: String,
    val allowedPackages: Set<String>,
    val persistence: Set<PersistencePolicy>,
    val capabilityScope: Set<String> = setOf("ui.navigate"),
    val riskCeiling: RiskClass = RiskClass.A,
    val terminal: Boolean = false,
) {
    init {
        require(taskId.isNotBlank())
        require(goal.isNotBlank())
        require(allowedPackages.none { it.isBlank() })
        require(capabilityScope.none { it.isBlank() })
    }

    fun shouldStop(
        foregroundPackage: String,
        userCancelled: Boolean,
        hardSafetyBlock: Boolean,
    ): Boolean {
        if (terminal || userCancelled || hardSafetyBlock) return true
        if (PersistencePolicy.UNTIL_APP_SCOPE_EXIT in persistence && allowedPackages.isNotEmpty()) {
            return foregroundPackage !in allowedPackages
        }
        return false
    }
}
