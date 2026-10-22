package com.hanlinh.androidbrain.network

class OfflineContinuationPolicy(
    private val minimumLocalConfidence: Double = 0.85,
) {
    fun mayContinue(
        alreadyAuthorized: Boolean,
        withinAllowedPackage: Boolean,
        localConfidence: Double,
        cloudReasoningRequired: Boolean,
        confirmationPending: Boolean,
    ): Boolean {
        require(localConfidence in 0.0..1.0)
        return alreadyAuthorized &&
            withinAllowedPackage &&
            localConfidence >= minimumLocalConfidence &&
            !cloudReasoningRequired &&
            !confirmationPending
    }
}
