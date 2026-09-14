package com.hanlinh.androidbrain.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CommandSocketProtocolTest {
    @Test
    fun converts_https_gateway_to_authenticated_websocket_path() {
        assertEquals(
            "wss://android-brain-agent-gateway.hanlinh227.workers.dev/v1/device/device%201/socket",
            CommandSocketProtocol.socketUrl(
                "https://android-brain-agent-gateway.hanlinh227.workers.dev/",
                "device 1",
            ),
        )
    }

    @Test
    fun recognizes_only_command_available_push_messages() {
        assertTrue(CommandSocketProtocol.isCommandAvailable("{\"type\":\"command_available\",\"commandId\":\"c1\"}"))
        assertFalse(CommandSocketProtocol.isCommandAvailable("pong"))
        assertFalse(CommandSocketProtocol.isCommandAvailable("{\"type\":\"connected\"}"))
        assertFalse(CommandSocketProtocol.isCommandAvailable("not-json"))
    }
}
