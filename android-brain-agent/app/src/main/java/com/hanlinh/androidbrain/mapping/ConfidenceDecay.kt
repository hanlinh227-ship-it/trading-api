package com.hanlinh.androidbrain.mapping

class ConfidenceDecay {
    fun apply(
        confidence: Double,
        versionChanged: Boolean,
        anchorMismatch: Boolean,
        ageDays: Int,
        repeatedFailure: Boolean = false,
    ): Double {
        require(confidence in 0.0..1.0)
        require(ageDays >= 0)
        var value = confidence
        if (versionChanged) value *= 0.72
        if (anchorMismatch) value *= 0.55
        if (repeatedFailure) value *= 0.65
        val ageFactor = (1.0 - (ageDays.coerceAtMost(365) / 365.0) * 0.25).coerceAtLeast(0.75)
        value *= ageFactor
        return value.coerceIn(0.0, 1.0)
    }
}
