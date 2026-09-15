package com.hanlinh.androidbrain.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CommandSocketProtocolV5Test {
    @Test fun commandAvailable_remainsBackwardCompatible() {
        val event = CommandSocketProtocol.parseEvent("{\"type\":\"command_available\",\"commandId\":\"c1\"}")
        assertEquals(CommandSocketEvent.CommandAvailable, event)
        assertTrue(CommandSocketProtocol.isCommandAvailable("{\"type\":\"command_available\"}"))
    }

    @Test fun taskCancelled_exposesExactTaskId() {
        val event = CommandSocketProtocol.parseEvent("{\"type\":\"task_cancelled\",\"taskId\":\"task-123\"}")
        assertEquals(CommandSocketEvent.TaskCancelled("task-123"), event)
    }

    @Test fun malformedOrUnknownEvent_failsClosed() {
        assertNull(CommandSocketProtocol.parseEvent("{\"type\":\"task_cancelled\",\"taskId\":\"\"}"))
        assertNull(CommandSocketProtocol.parseEvent("{\"type\":\"unknown\"}"))
        assertNull(CommandSocketProtocol.parseEvent("not-json"))
    }
}
