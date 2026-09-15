package com.hanlinh.androidbrain.mapping

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AppMappingStoreTest {
    @Test
    fun failedTransition_isNeverPromoted() {
        val store = InMemoryAppMappingStore()
        store.recordTransition(candidateTransition(), verified = false)
        assertTrue(store.transitions("com.example").isEmpty())
    }

    @Test
    fun verifiedTransition_isStoredPerPackage() {
        val store = InMemoryAppMappingStore()
        store.recordTransition(candidateTransition(), verified = true)
        assertEquals(1, store.transitions("com.example").size)
        assertTrue(store.transitions("com.other").isEmpty())
    }

    private fun candidateTransition() = TransitionEdge(
        packageName = "com.example",
        fromScreenId = "home",
        actionKey = "click:settings",
        toScreenId = "settings",
        successCount = 1,
        failureCount = 0,
        medianLatencyMs = 80,
        confidence = 0.9,
        lastVerifiedAtMs = 1,
    )
}
