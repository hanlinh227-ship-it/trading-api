package com.hanlinh.androidbrain.network

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OfflineContinuationPolicyTest {
    @Test fun locallyAuthorizedKnownPath_continuesDuringTemporaryCloudLoss() {
        val policy = OfflineContinuationPolicy()
        assertTrue(
            policy.mayContinue(
                alreadyAuthorized = true,
                withinAllowedPackage = true,
                localConfidence = 0.95,
                cloudReasoningRequired = false,
                confirmationPending = false,
            )
        )
    }

    @Test fun cloudReasoningRequired_pausesOffline() {
        val policy = OfflineContinuationPolicy()
        assertFalse(policy.mayContinue(true, true, 0.95, true, false))
    }

    @Test fun pendingConfirmation_pausesOffline() {
        val policy = OfflineContinuationPolicy()
        assertFalse(policy.mayContinue(true, true, 0.95, false, true))
    }

    @Test fun appScopeExit_pausesOffline() {
        val policy = OfflineContinuationPolicy()
        assertFalse(policy.mayContinue(true, false, 0.95, false, false))
    }
}
