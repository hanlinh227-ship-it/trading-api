package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.execution.ActionTimingProfile
import com.hanlinh.androidbrain.execution.AdaptiveActionScheduler
import com.hanlinh.androidbrain.perception.UnifiedObservation
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.OpenUrl
import com.hanlinh.androidbrain.recovery.RecoveryEngine
import com.hanlinh.androidbrain.verification.UnifiedVerifier

data class LocalLoopResult(
    val executedLocalActions: Int,
    val cloudRequests: Int,
    val reason: String,
)

data class OperatorDecision(
    val code: String,
    val terminal: Boolean,
    val requiresCloud: Boolean = false,
)

class UnifiedOperatorEngine(
    initialSession: PersistentOperatorSession,
    private val inferenceBudget: DynamicInferenceBudget = DynamicInferenceBudget(),
    private val verifier: UnifiedVerifier = UnifiedVerifier(),
    private val scheduler: AdaptiveActionScheduler = AdaptiveActionScheduler(),
    @Suppress("unused") private val recoveryEngine: RecoveryEngine = RecoveryEngine(),
    private val observationProvider: () -> UnifiedObservation? = { null },
    private val localPlanProvider: (UnifiedObservation) -> MicroPlan? = { null },
    private val signalProvider: (UnifiedObservation) -> InferenceSignals? = { null },
    private val actionExecutor: (Action) -> Boolean = { false },
    private val timingProfileProvider: (String, String) -> ActionTimingProfile? = { _, _ -> null },
    private val onVerifiedTransition: (UnifiedObservation, Action, UnifiedObservation, Long) -> Unit = { _, _, _, _ -> },
) {
    private var session = initialSession
    private var userCancelled = false
    private var terminal = initialSession.terminal
    private var terminalCode: String? = if (terminal) "TASK_TERMINAL" else null
    private var verifiedLocalActionCount: Long = 0
    private var cloudRequestCount: Int = 0
    private var lastObservation: UnifiedObservation? = null

    @Synchronized
    fun currentSession(): PersistentOperatorSession = session.copy(terminal = terminal)

    @Synchronized
    fun verifiedLocalActions(): Long = verifiedLocalActionCount

    @Synchronized
    fun requestCancel() {
        userCancelled = true
        terminal = true
        terminalCode = "CANCELLED"
    }

    @Synchronized
    fun observePackage(packageName: String) {
        if (terminal) return
        if (session.shouldStop(packageName, userCancelled, hardSafetyBlock = false)) {
            terminal = true
            terminalCode = if (userCancelled) "CANCELLED" else "APP_SCOPE_EXIT"
        }
    }

    @Synchronized
    fun hardSafetyStop(code: String = "HARD_SAFETY_BLOCK") {
        terminal = true
        terminalCode = code
    }

    @Synchronized
    fun nextDecision(): OperatorDecision {
        if (userCancelled) return OperatorDecision("CANCELLED", terminal = true)
        if (terminal) return OperatorDecision(terminalCode ?: "TASK_TERMINAL", terminal = true)
        val observation = observationProvider() ?: return OperatorDecision("OBSERVATION_REQUIRED", terminal = false, requiresCloud = true)
        lastObservation = observation
        observePackage(observation.packageName)
        if (terminal) return OperatorDecision(terminalCode ?: "APP_SCOPE_EXIT", terminal = true)
        val signals = signalProvider(observation)
        if (signals != null) {
            return when (val directive = inferenceBudget.decide(signals)) {
                InferenceDirective.CLOUD_MICRO_PLAN,
                InferenceDirective.CLOUD_RECOVERY,
                -> OperatorDecision(directive.name, terminal = false, requiresCloud = true)
                else -> OperatorDecision(directive.name, terminal = false)
            }
        }
        return OperatorDecision("LOCAL_OR_REGROUND", terminal = false)
    }

    fun runUntilEscalation(maxLocalActions: Int): LocalLoopResult {
        require(maxLocalActions >= 0)
        var executedThisRun = 0
        while (executedThisRun < maxLocalActions) {
            val preDecision = nextDecision()
            if (preDecision.terminal) return LocalLoopResult(executedThisRun, cloudRequestCount, preDecision.code)
            if (preDecision.requiresCloud) {
                cloudRequestCount += 1
                return LocalLoopResult(executedThisRun, cloudRequestCount, preDecision.code)
            }
            var before = lastObservation ?: observationProvider()
                ?: return escalate(executedThisRun, "OBSERVATION_REQUIRED")
            val plan = localPlanProvider(before) ?: return escalate(executedThisRun, "LOCAL_PLAN_UNAVAILABLE")
            if (!plan.isEligibleForSpeculativeExecution()) return escalate(executedThisRun, "CONSEQUENTIAL_ACTION_REQUIRES_CLOUD")

            for ((index, rawAction) in plan.actions.withIndex()) {
                if (executedThisRun >= maxLocalActions) break
                synchronized(this) {
                    if (terminal || userCancelled) {
                        return LocalLoopResult(executedThisRun, cloudRequestCount, terminalCode ?: "CANCELLED")
                    }
                }
                if (!isLocalActionAuthorized(rawAction)) {
                    return escalate(executedThisRun, "LOCAL_POLICY_DENIED")
                }
                val profile = timingProfileProvider(before.packageName, before.screenSignature)
                val timing = scheduler.timingFor(before.packageName, before.screenSignature, rawAction, profile)
                val action = scheduler.applyTiming(rawAction, timing)
                val startedAt = System.nanoTime()
                if (!actionExecutor(action)) return escalate(executedThisRun, "LOCAL_ACTION_DISPATCH_FAILED")

                val after = observationProvider() ?: return escalate(executedThisRun, "POST_ACTION_OBSERVATION_REQUIRED")
                observePackage(after.packageName)
                if (currentSession().terminal) {
                    return LocalLoopResult(executedThisRun, cloudRequestCount, terminalCode ?: "APP_SCOPE_EXIT")
                }
                val verification = verifier.verifyTransition(before, after, expectedPackage = before.packageName)
                if (!verification.success) return escalate(executedThisRun, "LOCAL_POSTCONDITION_NOT_MET")

                val latencyMs = ((System.nanoTime() - startedAt) / 1_000_000L).coerceAtLeast(0)
                onVerifiedTransition(before, action, after, latencyMs)
                recordVerifiedLocalAction()
                executedThisRun += 1
                before = after
                lastObservation = after

                if (index in plan.reobserveAfter) {
                    lastObservation = observationProvider() ?: after
                    before = lastObservation ?: after
                }
            }
        }
        return LocalLoopResult(executedThisRun, cloudRequestCount, "LOCAL_BUDGET_REACHED")
    }

    @Synchronized
    fun recordVerifiedLocalAction() {
        if (!terminal) verifiedLocalActionCount += 1
    }

    private fun isLocalActionAuthorized(action: Action): Boolean {
        if (action.riskClass == RiskClass.D || action.riskClass == RiskClass.C) return false
        if (action.riskClass.ordinal > session.riskCeiling.ordinal) return false

        val requiredCapability = when (action) {
            is LaunchApp, is OpenUrl -> "apps.open"
            else -> if (action.riskClass == RiskClass.B) "ui.write" else "ui.navigate"
        }
        if (requiredCapability !in session.capabilityScope) return false

        if (action is LaunchApp && session.allowedPackages.isNotEmpty() && action.packageName !in session.allowedPackages) {
            return false
        }
        if (action is OpenUrl && session.allowedPackages.isNotEmpty()) {
            // A URL may hand control to a browser or another app. Re-ground through cloud
            // rather than silently widening the authorized package scope.
            return false
        }
        return true
    }

    @Synchronized
    private fun escalate(executed: Int, reason: String): LocalLoopResult {
        cloudRequestCount += 1
        return LocalLoopResult(executed, cloudRequestCount, reason)
    }
}
