package com.hanlinh.androidbrain.action

class ShizukuActions(
    private val availabilityProbe: () -> Boolean = {
        try {
            Class.forName("rikka.shizuku.Shizuku")
            true
        } catch (_: Throwable) {
            false
        }
    }
) {
    fun available(): Boolean = availabilityProbe()
}
