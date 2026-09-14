package com.hanlinh.androidbrain.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ConnectionCadenceTest {
    @Test
    fun fallback_poll_is_bounded_without_high_frequency_http_churn() {
        assertTrue(ConnectionCadence.FALLBACK_POLL_MS >= 3_000L)
        assertTrue(ConnectionCadence.FALLBACK_POLL_MS <= 10_000L)
    }

    @Test
    fun websocket_heartbeat_keeps_gateway_online_freshness_alive() {
        assertTrue(ConnectionCadence.HEARTBEAT_MS in 5_000L..12_000L)
    }

    @Test
    fun startup_allows_primary_websocket_connect_before_maintenance_fallback() {
        assertTrue(ConnectionCadence.INITIAL_MAINTENANCE_DELAY_MS > 0L)
        assertTrue(ConnectionCadence.INITIAL_MAINTENANCE_DELAY_MS >= ConnectionCadence.RECONNECT_MIN_MS)
    }

    @Test
    fun maintenance_does_not_restart_an_in_flight_websocket_handshake() {
        assertEquals(
            ConnectionMaintenanceAction.WAIT_CONNECTING,
            ConnectionMaintenancePolicy.action(socketConnected = false, socketPresent = true),
        )
    }

    @Test
    fun connected_socket_uses_heartbeat_and_disconnected_socket_uses_polling() {
        assertEquals(
            ConnectionMaintenanceAction.HEARTBEAT,
            ConnectionMaintenancePolicy.action(socketConnected = true, socketPresent = true),
        )
        assertEquals(
            ConnectionMaintenanceAction.FALLBACK_POLL,
            ConnectionMaintenancePolicy.action(socketConnected = false, socketPresent = false),
        )
    }

    @Test
    fun reconnect_starts_fast_and_caps_aggressively() {
        assertTrue(ConnectionCadence.RECONNECT_MIN_MS <= 500L)
        assertTrue(ConnectionCadence.RECONNECT_MAX_MS <= 5_000L)
    }
}
