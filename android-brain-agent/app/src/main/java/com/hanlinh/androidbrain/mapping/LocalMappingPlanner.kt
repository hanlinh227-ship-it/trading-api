package com.hanlinh.androidbrain.mapping

import com.hanlinh.androidbrain.agent.MicroPlan
import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.TypedActionCodec

class LocalMappingPlanner(
    private val store: AppMappingStore,
    private val minimumReplayConfidence: Double = 0.90,
) {
    init {
        require(minimumReplayConfidence in 0.0..1.0)
    }

    fun planFor(observation: UnifiedObservation): MicroPlan? {
        val knownScreen = store.screens(observation.packageName)
            .firstOrNull { it.screenId == observation.screenSignature }
            ?: return null
        if (knownScreen.confidence < minimumReplayConfidence) return null

        val edge = store.transitions(observation.packageName)
            .asSequence()
            .filter { it.fromScreenId == observation.screenSignature }
            .filter { it.confidence >= minimumReplayConfidence }
            .filter { it.successCount > it.failureCount }
            .sortedWith(
                compareByDescending<TransitionEdge> { it.confidence }
                    .thenByDescending { it.successCount - it.failureCount }
                    .thenByDescending { it.lastVerifiedAtMs },
            )
            .firstOrNull()
            ?: return null

        val action = runCatching { TypedActionCodec.decode(edge.actionKey) }.getOrNull() ?: return null
        return MicroPlan(
            actions = listOf(action),
            reobserveAfter = emptySet(),
            confidence = edge.confidence,
        )
    }

    fun recordVerifiedTransition(
        before: UnifiedObservation,
        action: Action,
        after: UnifiedObservation,
        latencyMs: Long,
    ) {
        if (before.packageName != after.packageName) return
        val verifiedAt = maxOf(before.timestampMs, after.timestampMs)
        store.recordScreen(before.toScreenState(verifiedAt), verified = true)
        store.recordScreen(after.toScreenState(verifiedAt), verified = true)

        val actionKey = TypedActionCodec.encode(action)
        val existing = store.transitions(before.packageName).firstOrNull {
            it.fromScreenId == before.screenSignature &&
                it.toScreenId == after.screenSignature &&
                it.actionKey == actionKey
        }
        val successCount = (existing?.successCount ?: 0) + 1
        val medianLatency = if (existing == null) {
            latencyMs.coerceAtLeast(0)
        } else {
            ((existing.medianLatencyMs + latencyMs.coerceAtLeast(0)) / 2L)
        }
        store.recordTransition(
            TransitionEdge(
                packageName = before.packageName,
                fromScreenId = before.screenSignature,
                actionKey = actionKey,
                toScreenId = after.screenSignature,
                successCount = successCount,
                failureCount = existing?.failureCount ?: 0,
                medianLatencyMs = medianLatency,
                confidence = ((existing?.confidence ?: INITIAL_VERIFIED_CONFIDENCE) + CONFIDENCE_GAIN)
                    .coerceAtMost(MAX_VERIFIED_CONFIDENCE),
                lastVerifiedAtMs = verifiedAt,
            ),
            verified = true,
        )
    }

    private fun UnifiedObservation.toScreenState(verifiedAt: Long) = ScreenState(
        screenId = screenSignature,
        packageName = packageName,
        activityHint = activityHint,
        semanticSignature = semanticFingerprint,
        visualSignature = perceptualHash ?: screenshotHash,
        lastVerifiedAppVersion = appVersionHint,
        confidence = SCREEN_VERIFIED_CONFIDENCE,
        firstSeenAtMs = timestampMs,
        lastVerifiedAtMs = verifiedAt,
    )

    private companion object {
        const val INITIAL_VERIFIED_CONFIDENCE = 0.91
        const val CONFIDENCE_GAIN = 0.02
        const val MAX_VERIFIED_CONFIDENCE = 0.99
        const val SCREEN_VERIFIED_CONFIDENCE = 0.95
    }
}
