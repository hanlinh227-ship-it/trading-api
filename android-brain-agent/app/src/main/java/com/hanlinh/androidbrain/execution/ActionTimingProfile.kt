package com.hanlinh.androidbrain.execution

data class ActionTimingProfile(
    val packageName: String,
    val screenId: String,
    val medianActionToEventMs: Long,
    val p90ActionToEventMs: Long,
    val reliableSwipeDurationMs: Long? = null,
    val reliableTapSettleMs: Long? = null,
) {
    init {
        require(packageName.isNotBlank())
        require(screenId.isNotBlank())
        require(medianActionToEventMs >= 0)
        require(p90ActionToEventMs >= medianActionToEventMs)
        require(reliableSwipeDurationMs == null || reliableSwipeDurationMs > 0)
        require(reliableTapSettleMs == null || reliableTapSettleMs >= 0)
    }
}

data class ActionTiming(
    val gestureDurationMs: Long,
    val minimumSettleMs: Long,
    val maximumSettleMs: Long,
    val eventDrivenCompletion: Boolean,
) {
    init {
        require(gestureDurationMs > 0)
        require(minimumSettleMs >= 0)
        require(maximumSettleMs >= minimumSettleMs)
    }
}
