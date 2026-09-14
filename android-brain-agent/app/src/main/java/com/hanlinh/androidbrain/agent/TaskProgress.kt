package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskClass

enum class TaskLoopStatus {
    OBSERVING,
    PLANNING,
    ACTING,
    VERIFYING,
    RECOVERING,
    COMPLETED,
    FAILED,
}

enum class TaskStepOutcome {
    EXECUTED,
    RECOVERABLE_FAILURE,
    FATAL_FAILURE,
    TASK_COMPLETE,
    NEEDS_CONFIRMATION,
}

data class TaskStepResult(
    val outcome: TaskStepOutcome,
    val code: String? = null,
)

data class TaskProgress(
    val taskId: String,
    val riskClass: RiskClass = RiskClass.A,
    val confirmedRiskClassC: Boolean = false,
    val stepCount: Int = 0,
    val recoveryCount: Int = 0,
    val lastFingerprint: String? = null,
    val status: TaskLoopStatus = TaskLoopStatus.OBSERVING,
    val cancelled: Boolean = false,
)

sealed interface TaskLoopDecision {
    val progress: TaskProgress
    val code: String?

    data class PlanNext(override val progress: TaskProgress) : TaskLoopDecision {
        override val code: String? = null
    }

    data class Recover(
        override val progress: TaskProgress,
        override val code: String,
    ) : TaskLoopDecision

    data class Completed(override val progress: TaskProgress) : TaskLoopDecision {
        override val code: String? = null
    }

    data class Failed(
        override val progress: TaskProgress,
        override val code: String,
    ) : TaskLoopDecision
}
