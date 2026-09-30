package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.mapping.AppMappingStore
import com.hanlinh.androidbrain.mapping.LocalMappingPlanner
import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.Action
import java.util.ArrayDeque

/**
 * Owns one persistent on-device task runtime. Cloud actions are seeds; after each
 * verified transition the same engine can continue from a local domain solver or
 * verified App Mapping data without another planning round trip.
 */
class UnifiedTaskRuntime(
    val taskId: String,
    private val session: PersistentOperatorSession,
    mappingStore: AppMappingStore,
    initialCloudActions: List<Action> = emptyList(),
    private val observationProvider: () -> UnifiedObservation?,
    private val actionExecutor: (Action, PersistentOperatorSession) -> Boolean,
    private val domainMode: Boolean = false,
    private val domainPlanProvider: (UnifiedObservation) -> MicroPlan? = { null },
) {
    private val cloudActions = ArrayDeque<Action>()
    private val mappingPlanner = LocalMappingPlanner(mappingStore)
    private val engine: UnifiedOperatorEngine

    init {
        require(taskId == session.taskId) { "runtime task mismatch" }
        enqueueCloudActions(initialCloudActions)
        engine = UnifiedOperatorEngine(
            initialSession = session,
            observationProvider = observationProvider,
            localPlanProvider = ::nextLocalPlan,
            signalProvider = ::signalsFor,
            actionExecutor = { action -> actionExecutor(action, session) },
            onVerifiedTransition = { before, action, after, latencyMs ->
                if (!domainMode) mappingPlanner.recordVerifiedTransition(before, action, after, latencyMs)
            },
        )
    }

    fun enqueueCloudActions(actions: List<Action>) {
        require(actions.size <= MAX_CLOUD_ACTIONS) { "cloud action batch exceeds bound" }
        actions.forEach(cloudActions::addLast)
    }

    fun runUntilEscalation(maxLocalActions: Int = MAX_LOCAL_ACTIONS): LocalLoopResult =
        engine.runUntilEscalation(maxLocalActions.coerceIn(0, MAX_LOCAL_ACTIONS))

    fun requestCancel() = engine.requestCancel()

    fun currentSession(): PersistentOperatorSession = engine.currentSession()

    fun verifiedLocalActions(): Long = engine.verifiedLocalActions()

    fun hasPendingCloudActions(): Boolean = cloudActions.isNotEmpty()

    private fun nextLocalPlan(observation: UnifiedObservation): MicroPlan? {
        if (cloudActions.isNotEmpty()) {
            return MicroPlan(
                actions = listOf(cloudActions.removeFirst()),
                reobserveAfter = emptySet(),
                confidence = CLOUD_ACTION_CONFIDENCE,
            )
        }
        if (domainMode) {
            domainPlanProvider(observation)?.let { return it }
        }
        return mappingPlanner.planFor(observation)
    }

    private fun signalsFor(observation: UnifiedObservation): InferenceSignals? {
        val pending = cloudActions.firstOrNull()
        if (pending != null) {
            return signals(
                observation = observation,
                confidence = CLOUD_ACTION_CONFIDENCE,
                knownScreen = 0.95,
                knownTransition = 0.95,
                riskClass = pending.riskClass,
                taskNovelty = 0.05,
            )
        }
        if (domainMode) {
            return signals(
                observation = observation,
                confidence = 0.98,
                knownScreen = 0.95,
                knownTransition = 0.95,
                riskClass = RiskClass.A,
                taskNovelty = 0.0,
            )
        }
        val mapped = mappingPlanner.planFor(observation) ?: return null
        val risk = mapped.actions.maxByOrNull { it.riskClass.ordinal }?.riskClass ?: RiskClass.A
        return signals(
            observation = observation,
            confidence = mapped.confidence,
            knownScreen = mapped.confidence,
            knownTransition = mapped.confidence,
            riskClass = risk,
            taskNovelty = 0.05,
        )
    }

    private fun signals(
        observation: UnifiedObservation,
        confidence: Double,
        knownScreen: Double,
        knownTransition: Double,
        riskClass: RiskClass,
        taskNovelty: Double,
    ): InferenceSignals {
        val semanticCompleteness = (observation.semanticNodeCount / 8.0).coerceIn(0.0, 1.0)
        val sparse = observation.semanticNodeCount <= 2
        return InferenceSignals(
            confidence = confidence.coerceIn(0.0, 1.0),
            knownScreen = knownScreen.coerceIn(0.0, 1.0),
            knownTransition = knownTransition.coerceIn(0.0, 1.0),
            semanticCompleteness = semanticCompleteness,
            visualAmbiguity = if (sparse) 0.8 else 0.05,
            riskClass = riskClass,
            reversible = riskClass.ordinal < RiskClass.C.ordinal,
            failureStreak = 0,
            taskNovelty = taskNovelty,
        )
    }

    private companion object {
        const val MAX_CLOUD_ACTIONS = 8
        const val MAX_LOCAL_ACTIONS = 64
        const val CLOUD_ACTION_CONFIDENCE = 0.99
    }
}