package com.hanlinh.androidbrain.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ConnectionCadenceTest {
    @Test
    fun fallback_poll_is_one_second() {
        assertEquals(1_000L, ConnectionCadence.FALLBACK_POLL_MS)
    }

    @Test
    fun reconnect_backoff_is_bounded() {
        assertTrue(ConnectionCadence.RECONNECT_MIN_MS >= 500L)
        assertTrue(ConnectionCadence.RECONNECT_MAX_MS <= 30_000L)
    }
}
