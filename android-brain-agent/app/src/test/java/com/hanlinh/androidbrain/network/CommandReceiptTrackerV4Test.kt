package com.hanlinh.androidbrain.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CommandReceiptTrackerV4Test {
    @Test
    fun `already receipted command returns cached result instead of being executed again`() {
        val tracker = CommandReceiptTracker(maxEntries = 2)
        val first = GatewayClient.TaskResult("c1", "COMPLETED", null)
        tracker.record(first)
        assertEquals(first, tracker.resultFor("c1"))
        assertNull(tracker.resultFor("missing"))
    }

    @Test
    fun `receipt tracker stays bounded`() {
        val tracker = CommandReceiptTracker(maxEntries = 2)
        tracker.record(GatewayClient.TaskResult("c1", "COMPLETED", null))
        tracker.record(GatewayClient.TaskResult("c2", "COMPLETED", null))
        tracker.record(GatewayClient.TaskResult("c3", "COMPLETED", null))
        assertNull(tracker.resultFor("c1"))
        assertEquals("c3", tracker.resultFor("c3")?.commandId)
    }
}
