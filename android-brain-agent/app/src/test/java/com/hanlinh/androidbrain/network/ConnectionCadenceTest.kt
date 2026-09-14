package com.hanlinh.androidbrain.network

import org.junit.Assert.assertTrue
import org.junit.Test

class ConnectionCadenceTest {
    @Test
    fun fallback_poll_stays_below_half_second() {
        assertTrue(ConnectionCadence.FALLBACK_POLL_MS <= 500L)
    }

    @Test
    fun reconnect_starts_fast_and_caps_aggressively() {
        assertTrue(ConnectionCadence.RECONNECT_MIN_MS <= 500L)
        assertTrue(ConnectionCadence.RECONNECT_MAX_MS <= 5_000L)
    }
}
