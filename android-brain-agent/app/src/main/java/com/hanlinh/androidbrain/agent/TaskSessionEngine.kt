package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.policy.RiskClass

class TaskSessionEngine(
    initialProgress: TaskProgress,
    private val maxSteps: Int = 40,
    private val maxRecoveries: Int = 5,
    private val epochActionLimit: Int = 50,
    private val maxEpochs: Int = 20,
) {
    private var progress: TaskProgress = initialProgress

    @Synchronized
    fun currentProgress(): TaskProgress = progress

    @Synchronized
    fun resume(checkpoint: TaskProgressCheckpoint): TaskProgress {
        if (checkpoint.stepCount < progress.stepCount) return progress
        val userStop = PersistencePolicy.UNTIL_USER_STOP in progress.persistencePolicies
        progress = progress.copy(
            stepCount = checkpoint.stepCount,
            epoch = if (userStop) checkpoint.epoch else checkpoint.epoch.coerceAtMost(maxEpochs),
            epochStepCount = checkpoint.epochStepCount.coerceIn(0, epochActionLimit - 1),
            checkpointCount = checkpoint.checkpointCount,
            recoveryCount = checkpoint.recoveryCount.coerceAtMost(maxRecoveries),
        )
        return progress
    }

    @Synchronized
    fun cancel(): TaskProgress {
        progress = progress.copy(cancelled = true, status = TaskLoopStatus.CANCELLED)
        return progress
    }

    @Synchronized
    fun next(
        observation: AccessibilitySnapshot,
        previousResult: TaskStepResult?,
        killSwitchActive: Boolean,
    ): TaskLoopDecision {
        if (killSwitchActive) return fail("KILL_SWITCH")
        if (progress.cancelled || progress.status == TaskLoopStatus.CANCELLED) {
            if (progress.status != TaskLoopStatus.CANCELLED) {
                progress = progress.copy(cancelled = true, status = TaskLoopStatus.CANCELLED)
            }
            return TaskLoopDecision.Failed(progress, "CANCELLED")
        }
        if (progress.status == TaskLoopStatus.COMPLETED) return TaskLoopDecision.Completed(progress)
        if (progress.status == TaskLoopStatus.FAILED) return TaskLoopDecision.Failed(progress, "TASK_TERMINAL")
        if (progress.riskClass == RiskClass.D) return fail("CLASS_D_DENIED")
        if (progress.riskClass == RiskClass.C && !progress.confirmedRiskClassC) {
            return fail("CLASS_C_CONFIRMATION_REQUIRED")
        }

        when (previousResult?.outcome) {
            TaskStepOutcome.TASK_COMPLETE -> {
                progress = progress.copy(status = TaskLoopStatus.COMPLETED)
                return TaskLoopDecision.Completed(progress)
            }
            TaskStepOutcome.NEEDS_CONFIRMATION -> return fail("CLASS_C_CONFIRMATION_REQUIRED")
            TaskStepOutcome.FATAL_FAILURE -> return fail(previousResult.code ?: "FATAL_FAILURE")
            else -> Unit
        }

        if (previousResult != null) {
            if (!canAdvance()) return fail("STEP_LIMIT")
            progress = advanceStep(progress).copy(status = TaskLoopStatus.VERIFYING)
        }

        val fingerprint = observation.fingerprint()

        if (previousResult?.outcome == TaskStepOutcome.RECOVERABLE_FAILURE) {
            return recover(previousResult.code ?: "RECOVERABLE_FAILURE", fingerprint)
        }

        if (
            previousResult?.outcome == TaskStepOutcome.EXECUTED &&
            progress.lastFingerprint != null &&
            progress.lastFingerprint == fingerprint
        ) {
            return recover("NO_OP", fingerprint)
        }

        progress = progress.copy(
            recoveryCount = 0,
            lastFingerprint = fingerprint,
            status = TaskLoopStatus.PLANNING,
        )
        return TaskLoopDecision.PlanNext(progress)
    }

    private fun canAdvance(): Boolean {
        if (PersistencePolicy.UNTIL_USER_STOP in progress.persistencePolicies) return true
        return when (progress.persistence) {
            TaskPersistence.ONE_SHOT -> progress.stepCount < maxSteps
            TaskPersistence.LONG_RUNNING,
            TaskPersistence.UNTIL_TERMINAL,
            -> progress.stepCount < epochActionLimit * maxEpochs && progress.epoch < maxEpochs
        }
    }

    private fun advanceStep(current: TaskProgress): TaskProgress {
        val stepCount = current.stepCount + 1
        if (current.persistence == TaskPersistence.ONE_SHOT && PersistencePolicy.UNTIL_USER_STOP !in current.persistencePolicies) {
            return current.copy(stepCount = stepCount)
        }

        val nextEpochStepCount = current.epochStepCount + 1
        return if (nextEpochStepCount >= epochActionLimit) {
            current.copy(
                stepCount = stepCount,
                epoch = current.epoch + 1,
                epochStepCount = 0,
                checkpointCount = current.checkpointCount + 1,
            )
        } else {
            current.copy(
                stepCount = stepCount,
                epochStepCount = nextEpochStepCount,
            )
        }
    }

    private fun recover(code: String, fingerprint: String): TaskLoopDecision {
        if (progress.recoveryCount >= maxRecoveries) return fail("RECOVERY_LIMIT")
        progress = progress.copy(
            recoveryCount = progress.recoveryCount + 1,
            lastFingerprint = fingerprint,
            status = TaskLoopStatus.RECOVERING,
        )
        return TaskLoopDecision.Recover(progress, code)
    }

    private fun fail(code: String): TaskLoopDecision.Failed {
        progress = progress.copy(status = TaskLoopStatus.FAILED)
        return TaskLoopDecision.Failed(progress, code)
    }
}
