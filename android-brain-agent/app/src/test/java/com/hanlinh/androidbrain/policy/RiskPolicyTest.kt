package com.hanlinh.androidbrain.policy

import com.hanlinh.androidbrain.protocol.DeleteData
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.SendMessage
import com.hanlinh.androidbrain.protocol.SetText
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

    @Test fun class_c_send_stops_for_confirmation() {
        assertTrue(policy.authorize(SendMessage("contact", "hello"), defaults) is AuthorizationDecision.NeedsConfirmation)
    }

    @Test fun class_c_runs_only_after_explicit_confirmation() {
        assertEquals(
            AuthorizationDecision.Allowed,
            policy.authorize(DeleteData(200), defaults, confirmedClassC = true),
        )
    }

    @Test fun class_b_requires_explicit_enablement() {
        assertEquals(
            AuthorizationDecision.Denied,
            policy.authorize(SetText("field", "hello"), defaults),
        )
        assertEquals(
            AuthorizationDecision.Allowed,
            policy.authorize(SetText("field", "hello"), UserPolicy(classBEnabled = true)),
        )
    }

    @Test fun class_a_is_autonomous() {
        assertEquals(AuthorizationDecision.Allowed, policy.authorize(LaunchApp("com.android.settings"), defaults))
    }
}
