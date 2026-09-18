package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskClass

data class InferenceSignals(
    val confidence: Double,
    val knownScreen: Double,
    val knownTransition: Double,
    val semanticCompleteness: Double,
    val visualAmbiguity: Double,
    val riskClass: RiskClass,
    val reversible: Boolean,
    val failureStreak: Int,
    val taskNovelty: Double,
) {
    init {
        listOf(confidence, knownScreen, knownTransition, semanticCompleteness, visualAmbiguity, taskNovelty).forEach {
            require(it in 0.0..1.0)
        }
        require(failureStreak >= 0)
    }
}

enum class InferenceDirective {
    LOCAL_EXECUTE,
    LOCAL_REGROUND,
    LOCAL_DOMAIN_SOLVER,
    CAPTURE_VISUAL,
    CLOUD_MICRO_PLAN,
    CLOUD_RECOVERY,
}

class DynamicInferenceBudget {
    fun decide(signals: InferenceSignals): InferenceDirective {
        if (signals.riskClass.ordinal >= RiskClass.C.ordinal) return InferenceDirective.CLOUD_MICRO_PLAN
        if (signals.failureStreak >= 3) return InferenceDirective.CLOUD_RECOVERY
        if (signals.semanticCompleteness < 0.35 || signals.visualAmbiguity > 0.7) {
            return InferenceDirective.CAPTURE_VISUAL
        }
        if (
            signals.confidence >= 0.92 &&
            signals.knownScreen >= 0.85 &&
            signals.knownTransition >= 0.85 &&
            signals.semanticCompleteness >= 0.7 &&
            signals.visualAmbiguity <= 0.25 &&
            signals.reversible &&
            signals.taskNovelty <= 0.25 &&
            signals.failureStreak == 0
        ) return InferenceDirective.LOCAL_EXECUTE
        if (signals.knownScreen >= 0.8 && signals.knownTransition < 0.6) return InferenceDirective.LOCAL_REGROUND
        if (signals.confidence >= 0.8 && signals.reversible && signals.taskNovelty <= 0.4) {
            return InferenceDirective.LOCAL_DOMAIN_SOLVER
        }
        return InferenceDirective.CLOUD_MICRO_PLAN
    }
}
