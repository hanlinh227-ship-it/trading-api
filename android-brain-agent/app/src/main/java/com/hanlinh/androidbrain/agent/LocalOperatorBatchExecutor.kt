package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.protocol.Action
import java.util.ArrayDeque

/**
 * Executes one already-authorized cloud micro-plan entirely on-device.
 * The UnifiedOperatorEngine remains the policy/verifier authority; this adapter
 * only turns a finite cloud batch into local plans and never performs a cloud call.
 */
class LocalOperatorBatchExecutor {
    fun execute(
        session: PersistentOperatorSession,
        actions: List<Action>,
        observationProvider: () -> UnifiedObservation?,
        actionExecutor: (Action) -> Boolean,
    ): LocalLoopResult {
        require(actions.size <= MAX_ACTIONS) { "local action batch exceeds bound" }
        if (actions.isEmpty()) return LocalLoopResult(0, 0, "LOCAL_BATCH_VERIFIED")

        val queue = ArrayDeque(actions)
        val engine = UnifiedOperatorEngine(
            initialSession = session,
            observationProvider = observationProvider,
            localPlanProvider = {
                if (queue.isEmpty()) null
                else MicroPlan(
                    actions = listOf(queue.removeFirst()),
                    reobserveAfter = emptySet(),
                    confidence = 0.99,
                )
            },
            signalProvider = { null },
            actionExecutor = actionExecutor,
        )
        val result = engine.runUntilEscalation(actions.size)
        return if (result.executedLocalActions == actions.size && result.cloudRequests == 0) {
            result.copy(reason = "LOCAL_BATCH_VERIFIED")
        } else {
            result
        }
    }

    private companion object {
        const val MAX_ACTIONS = 8
    }
}
