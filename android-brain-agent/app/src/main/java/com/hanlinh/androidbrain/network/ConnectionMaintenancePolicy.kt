package com.hanlinh.androidbrain.network

enum class ConnectionMaintenanceAction {
    HEARTBEAT,
    WAIT_CONNECTING,
    FALLBACK_POLL,
}

object ConnectionMaintenancePolicy {
    fun action(socketConnected: Boolean, socketPresent: Boolean): ConnectionMaintenanceAction = when {
        socketConnected -> ConnectionMaintenanceAction.HEARTBEAT
        socketPresent -> ConnectionMaintenanceAction.WAIT_CONNECTING
        else -> ConnectionMaintenanceAction.FALLBACK_POLL
    }
}
