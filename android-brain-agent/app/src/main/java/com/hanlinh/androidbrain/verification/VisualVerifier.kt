package com.hanlinh.androidbrain.verification

import com.hanlinh.androidbrain.perception.UnifiedObservation

class VisualVerifier {
    fun changed(before: UnifiedObservation, after: UnifiedObservation): Boolean {
        val beforeHash = before.perceptualHash ?: before.screenshotHash
        val afterHash = after.perceptualHash ?: after.screenshotHash
        if (beforeHash.isNullOrBlank() || afterHash.isNullOrBlank()) return false
        return beforeHash != afterHash
    }
}
