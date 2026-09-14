package com.hanlinh.androidbrain.service

import com.hanlinh.androidbrain.network.PairingData

object AgentConnectionRefreshPolicy {
    fun shouldRefresh(current: PairingData?, latest: PairingData?): Boolean = current != latest
}
