package com.hanlinh.androidbrain.policy

import com.hanlinh.androidbrain.protocol.DeleteData
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.SendMessage
import com.hanlinh.androidbrain.protocol.WalletSign
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RiskPolicyTest {
    private val policy = RiskPolicy()
    private val defaults = UserPolicy.defaults()

    @Test fun class_d_has_no_unattended_route() {
        assertEquals(AuthorizationDecision.Denied, policy.authorize(WalletSign("payload"), defaults))
    }

    @Test fun class_c_stops_for_confirmation() {
        assertTrue(policy.authorize(DeleteData(200), defaults) is AuthorizationDecision.NeedsConfirmation)
    }

    @Test fun class_b_requires_explicit_enablement() {
        assertEquals(AuthorizationDecision.Denied, policy.authorize(SendMessage("contact", "hello"), defaults))
    }

    @Test fun class_a_is_autonomous() {
        assertEquals(AuthorizationDecision.Allowed, policy.authorize(LaunchApp("com.android.settings"), defaults))
    }
}
