package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.policy.RiskClass

enum class TaskLoopStatus {
    OBSERVING,
    PLANNING,
    ACTING,
    VERIFYING,
    RECOVERING,
    COMPLETED,
    CANCELLED,
    FAILED,
}

enum class TaskPersistence {
    ONE_SHOT,
    LONG_RUNNING,
    UNTIL_TERMINAL,
}

fun TaskPersistence.toV5Policies(): Set<PersistencePolicy> = when (this) {
    TaskPersistence.ONE_SHOT -> setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE)
    TaskPersistence.LONG_RUNNING -> setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE)
    TaskPersistence.UNTIL_TERMINAL -> setOf(PersistencePolicy.UNTIL_GOAL_COMPLETE)
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

data class TaskProgressCheckpoint(
    val stepCount: Int,
    val epoch: Int,
    val epochStepCount: Int,
    val checkpointCount: Int,
    val recoveryCount: Int,
) {
    init {
        require(stepCount >= 0)
        require(epoch >= 0)
        require(epochStepCount >= 0)
        require(checkpointCount >= 0)
        require(recoveryCount >= 0)
    }
}

data class TaskProgress(
    val taskId: String,
    val riskClass: RiskClass = RiskClass.A,
    val confirmedRiskClassC: Boolean = false,
    val persistence: TaskPersistence = TaskPersistence.ONE_SHOT,
    val persistencePolicies: Set<PersistencePolicy> = persistence.toV5Policies(),
    val stepCount: Int = 0,
    val epoch: Int = 0,
    val epochStepCount: Int = 0,
    val checkpointCount: Int = 0,
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
