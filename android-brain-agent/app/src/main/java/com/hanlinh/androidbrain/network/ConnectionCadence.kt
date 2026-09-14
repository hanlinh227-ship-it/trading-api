package com.hanlinh.androidbrain.network

object ConnectionCadence {
    const val FALLBACK_POLL_MS = 7_500L
    const val HEARTBEAT_MS = 7_500L
    const val INITIAL_MAINTENANCE_DELAY_MS = 500L
    val MAINTENANCE_TICK_MS = minOf(FALLBACK_POLL_MS, HEARTBEAT_MS)
    const val RECONNECT_MIN_MS = 250L
    const val RECONNECT_MAX_MS = 5_000L
}
