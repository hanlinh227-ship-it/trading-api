package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.Action

data class MicroPlan(
    val actions: List<Action>,
    val reobserveAfter: Set<Int>,
    val confidence: Double,
) {
    init {
        require(actions.size in 1..8) { "micro-plan must contain 1..8 actions" }
        require(confidence in 0.0..1.0)
        require(reobserveAfter.all { it in actions.indices })
    }

    fun isEligibleForSpeculativeExecution(): Boolean =
        actions.none { it.riskClass.ordinal >= RiskClass.C.ordinal }
}
