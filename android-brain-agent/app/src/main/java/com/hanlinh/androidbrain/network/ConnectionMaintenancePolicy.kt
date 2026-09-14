package com.hanlinh.androidbrain.network

enum class ConnectionMaintenanceAction {
    HEARTBEAT,
    FALLBACK_POLL,
}

object ConnectionMaintenancePolicy {
    fun action(socketConnected: Boolean): ConnectionMaintenanceAction =
        if (socketConnected) ConnectionMaintenanceAction.HEARTBEAT
        else ConnectionMaintenanceAction.FALLBACK_POLL
}
