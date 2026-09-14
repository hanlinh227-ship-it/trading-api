package com.hanlinh.androidbrain.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TaskContinuationLedgerV4Test {
    @Test
    fun `failed task-step transport can retain one idempotent continuation for retry`() {
        val ledger = TaskContinuationLedger(maxEntries = 2)
        val pending = TaskContinuationLedger.Pending("task-1", "command-1")
        ledger.record(pending)
        assertEquals(pending, ledger.pendingFor("task-1"))
        ledger.clear("task-1", "command-1")
        assertNull(ledger.pendingFor("task-1"))
    }

    @Test
    fun `stale clear cannot discard a newer task continuation`() {
        val ledger = TaskContinuationLedger(maxEntries = 2)
        ledger.record(TaskContinuationLedger.Pending("task-1", "command-old"))
        val latest = TaskContinuationLedger.Pending("task-1", "command-new")
        ledger.record(latest)
        ledger.clear("task-1", "command-old")
        assertEquals(latest, ledger.pendingFor("task-1"))
    }
}
