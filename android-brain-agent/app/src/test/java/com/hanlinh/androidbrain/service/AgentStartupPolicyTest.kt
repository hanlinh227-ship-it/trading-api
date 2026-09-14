package com.hanlinh.androidbrain.service

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentStartupPolicyTest {
    @Test
    fun `paired agent auto starts when kill switch is inactive`() {
        assertTrue(AgentStartupPolicy.shouldStart(hasPairing = true, killSwitchActive = false))
    }

    @Test
    fun `unpaired agent does not auto start`() {
        assertFalse(AgentStartupPolicy.shouldStart(hasPairing = false, killSwitchActive = false))
    }

    @Test
    fun `explicit kill switch prevents automatic restart`() {
        assertFalse(AgentStartupPolicy.shouldStart(hasPairing = true, killSwitchActive = true))
    }
}
