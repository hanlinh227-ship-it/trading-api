package com.hanlinh.androidbrain.recovery

enum class RecoveryDirective {
    REOBSERVE,
    REGROUND,
    USE_VERIFIED_SELECTOR,
    CAPTURE_VISUAL,
    USE_VERIFIED_VISUAL_RECOVERY,
    USE_GRAPH_PATH,
    REQUEST_CLOUD_RECOVERY,
    PAUSE_OR_FAIL,
}

data class RecoveryContext(
    val attemptsForState: Int = 0,
    val observationStale: Boolean = false,
    val groundingInvalid: Boolean = false,
    val hasVerifiedAlternateSelector: Boolean = false,
    val visualAvailable: Boolean = false,
    val hasVerifiedVisualRecovery: Boolean = false,
    val hasVerifiedGraphPath: Boolean = false,
    val cloudAvailable: Boolean = true,
    val hardSafetyBlock: Boolean = false,
)

class RecoveryEngine(
    private val maxAttemptsPerState: Int = 7,
) {
    fun next(context: RecoveryContext): RecoveryDirective {
        if (context.hardSafetyBlock || context.attemptsForState >= maxAttemptsPerState) {
            return RecoveryDirective.PAUSE_OR_FAIL
        }
        if (context.observationStale || context.attemptsForState == 0) return RecoveryDirective.REOBSERVE
        if (context.groundingInvalid) return RecoveryDirective.REGROUND
        if (context.hasVerifiedAlternateSelector) return RecoveryDirective.USE_VERIFIED_SELECTOR
        if (!context.visualAvailable) return RecoveryDirective.CAPTURE_VISUAL
        if (context.hasVerifiedVisualRecovery) return RecoveryDirective.USE_VERIFIED_VISUAL_RECOVERY
        if (context.hasVerifiedGraphPath) return RecoveryDirective.USE_GRAPH_PATH
        if (context.cloudAvailable) return RecoveryDirective.REQUEST_CLOUD_RECOVERY
        return RecoveryDirective.PAUSE_OR_FAIL
    }
}
