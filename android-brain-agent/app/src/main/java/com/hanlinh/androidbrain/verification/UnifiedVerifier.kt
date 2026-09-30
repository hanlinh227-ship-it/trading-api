package com.hanlinh.androidbrain.verification

import com.hanlinh.androidbrain.perception.UnifiedObservation

data class VerificationResult(
    val success: Boolean,
    val changed: Boolean,
    val confidence: Double,
    val reason: String,
)

class UnifiedVerifier(
    private val semanticVerifier: SemanticVerifier = SemanticVerifier(),
    private val visualVerifier: VisualVerifier = VisualVerifier(),
) {
    fun verifyTransition(
        before: UnifiedObservation,
        after: UnifiedObservation,
        expectedPackage: String? = before.packageName,
        expectedScreenSignature: String? = null,
    ): VerificationResult {
        val packageSatisfied = semanticVerifier.expectedPackageSatisfied(after, expectedPackage)
        if (!packageSatisfied) {
            return VerificationResult(false, true, 0.99, "UNEXPECTED_FOREGROUND_PACKAGE")
        }

        val semanticChanged = semanticVerifier.changed(before, after)
        val visualChanged = visualVerifier.changed(before, after)
        val domainChanged = before.skillSpecificState != after.skillSpecificState &&
            (before.skillSpecificState != null || after.skillSpecificState != null)
        val changed = semanticChanged || visualChanged || domainChanged

        if (expectedScreenSignature != null) {
            val reached = after.screenSignature == expectedScreenSignature
            return VerificationResult(
                success = reached,
                changed = changed,
                confidence = if (reached) 0.99 else if (changed) 0.55 else 0.2,
                reason = if (reached) "EXPECTED_SCREEN_REACHED" else "EXPECTED_SCREEN_NOT_REACHED",
            )
        }

        return VerificationResult(
            success = changed,
            changed = changed,
            confidence = when {
                domainChanged -> 0.99
                semanticChanged && visualChanged -> 0.98
                semanticChanged -> 0.9
                visualChanged -> 0.88
                else -> 0.15
            },
            reason = when {
                domainChanged -> "DOMAIN_STATE_CHANGED"
                semanticChanged && visualChanged -> "SEMANTIC_AND_VISUAL_CHANGED"
                semanticChanged -> "SEMANTIC_CHANGED"
                visualChanged -> "VISUAL_CHANGED"
                else -> "NO_OBSERVED_CHANGE"
            },
        )
    }
}
