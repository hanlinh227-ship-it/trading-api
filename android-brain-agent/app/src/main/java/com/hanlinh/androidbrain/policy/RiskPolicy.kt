package com.hanlinh.androidbrain.policy

import com.hanlinh.androidbrain.protocol.Action

enum class RiskClass { A, B, C, D }

data class UserPolicy(
    val classBEnabled: Boolean,
    val classCConfirmationEnabled: Boolean = true,
) {
    companion object {
        fun defaults() = UserPolicy(classBEnabled = false)
    }
}

sealed interface AuthorizationDecision {
    data object Allowed : AuthorizationDecision
    data object Denied : AuthorizationDecision
    data class NeedsConfirmation(val riskClass: RiskClass = RiskClass.C) : AuthorizationDecision
}

class RiskPolicy {
    fun authorize(
        action: Action,
        userPolicy: UserPolicy,
        confirmedClassC: Boolean = false,
        effectiveRiskClass: RiskClass = action.riskClass,
    ): AuthorizationDecision = when (effectiveRiskClass) {
        RiskClass.A -> AuthorizationDecision.Allowed
        RiskClass.B -> if (userPolicy.classBEnabled) AuthorizationDecision.Allowed else AuthorizationDecision.Denied
        RiskClass.C -> when {
            confirmedClassC -> AuthorizationDecision.Allowed
            userPolicy.classCConfirmationEnabled -> AuthorizationDecision.NeedsConfirmation()
            else -> AuthorizationDecision.Denied
        }
        RiskClass.D -> AuthorizationDecision.Denied
    }
}
