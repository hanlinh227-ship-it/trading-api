package com.hanlinh.androidbrain.verification

import com.hanlinh.androidbrain.perception.UnifiedObservation

class SemanticVerifier {
    fun changed(before: UnifiedObservation, after: UnifiedObservation): Boolean =
        before.packageName != after.packageName ||
            before.semanticFingerprint != after.semanticFingerprint ||
            before.screenSignature != after.screenSignature

    fun expectedPackageSatisfied(after: UnifiedObservation, expectedPackage: String?): Boolean =
        expectedPackage == null || after.packageName == expectedPackage
}
