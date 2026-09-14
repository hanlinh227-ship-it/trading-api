package com.hanlinh.androidbrain.service

import com.hanlinh.androidbrain.network.PairingData
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentConnectionRefreshPolicyTest {
    @Test
    fun changed_pairing_token_requires_connection_refresh() {
        val current = PairingData("device", "old-token", "gateway-key")
        val latest = PairingData("device", "new-token", "gateway-key")

        assertTrue(AgentConnectionRefreshPolicy.shouldRefresh(current, latest))
    }

    @Test
    fun identical_pairing_does_not_require_connection_refresh() {
        val current = PairingData("device", "same-token", "gateway-key")
        val latest = PairingData("device", "same-token", "gateway-key")

        assertFalse(AgentConnectionRefreshPolicy.shouldRefresh(current, latest))
    }
}
