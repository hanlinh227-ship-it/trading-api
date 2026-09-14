package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.policy.RiskClass

class TaskSessionEngine(
    initialProgress: TaskProgress,
    private val maxSteps: Int = 40,
    private val maxRecoveries: Int = 5,
) {
    private var progress: TaskProgress = initialProgress

    @Synchronized
    fun currentProgress(): TaskProgress = progress

    @Synchronized
    fun cancel(): TaskProgress {
        progress = progress.copy(cancelled = true, status = TaskLoopStatus.FAILED)
        return progress
    }

    @Synchronized
    fun next(
        observation: AccessibilitySnapshot,
        previousResult: TaskStepResult?,
        killSwitchActive: Boolean,
    ): TaskLoopDecision {
        if (killSwitchActive) return fail("KILL_SWITCH")
        if (progress.cancelled) return fail("CANCELLED")
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
            if (progress.stepCount >= maxSteps) return fail("STEP_LIMIT")
            progress = progress.copy(stepCount = progress.stepCount + 1, status = TaskLoopStatus.VERIFYING)
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
