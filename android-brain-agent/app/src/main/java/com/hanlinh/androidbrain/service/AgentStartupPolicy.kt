package com.hanlinh.androidbrain.service

object AgentStartupPolicy {
    fun shouldStart(hasPairing: Boolean, killSwitchActive: Boolean): Boolean =
        hasPairing && !killSwitchActive
}
