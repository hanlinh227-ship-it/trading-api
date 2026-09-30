package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.verification.UnifiedVerifier

sealed interface VerificationRule {
    data class NodeTextPresent(val text: String) : VerificationRule
    data class NodeTextAbsent(val text: String) : VerificationRule
    data class ForegroundPackage(val packageName: String) : VerificationRule
}

data class VerificationResult(val satisfied: Boolean, val reason: String? = null)

class Verifier(
    private val unifiedVerifier: UnifiedVerifier = UnifiedVerifier(),
) {
    fun verify(rule: VerificationRule, snapshot: AccessibilitySnapshot): VerificationResult {
        val satisfied = when (rule) {
            is VerificationRule.NodeTextPresent -> snapshot.nodes.any {
                it.text == rule.text || it.contentDescription == rule.text
            }
            is VerificationRule.NodeTextAbsent -> snapshot.nodes.none {
                it.text == rule.text || it.contentDescription == rule.text
            }
            is VerificationRule.ForegroundPackage -> snapshot.packageName == rule.packageName
        }
        return VerificationResult(satisfied, if (satisfied) null else "POSTCONDITION_NOT_MET")
    }

    fun verifyTransition(
        before: UnifiedObservation,
        after: UnifiedObservation,
        expectedPackage: String? = before.packageName,
        expectedScreenSignature: String? = null,
    ): com.hanlinh.androidbrain.verification.VerificationResult =
        unifiedVerifier.verifyTransition(before, after, expectedPackage, expectedScreenSignature)
}
