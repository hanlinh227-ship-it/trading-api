package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.policy.RiskClass
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskSessionEngineTest {
    private fun observation(packageName: String = "com.example", title: String = "screen") =
        AccessibilitySnapshot(packageName, title, emptyList())

    @Test
    fun `happy path observes then advances after a changed screen`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t1"))
        val first = engine.next(observation(title = "one"), previousResult = null, killSwitchActive = false)
        assertTrue(first is TaskLoopDecision.PlanNext)

        val second = engine.next(
            observation(title = "two"),
            previousResult = TaskStepResult(TaskStepOutcome.EXECUTED),
            killSwitchActive = false,
        )
        assertTrue(second is TaskLoopDecision.PlanNext)
        assertEquals(1, second.progress.stepCount)
        assertEquals(0, second.progress.recoveryCount)
    }

    @Test
    fun `repeated fingerprint after an action is treated as a no-op recovery`() {
        val same = observation(title = "same")
        val engine = TaskSessionEngine(TaskProgress(taskId = "t2"))
        engine.next(same, null, false)
        val decision = engine.next(same, TaskStepResult(TaskStepOutcome.EXECUTED), false)
        assertTrue(decision is TaskLoopDecision.Recover)
        assertEquals(1, decision.progress.recoveryCount)
        assertEquals("NO_OP", decision.code)
    }

    @Test
    fun `recoverable action failure enters recovery`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t3"))
        val decision = engine.next(
            observation(),
            TaskStepResult(TaskStepOutcome.RECOVERABLE_FAILURE, "NODE_MOVED"),
            false,
        )
        assertTrue(decision is TaskLoopDecision.Recover)
        assertEquals("NODE_MOVED", decision.code)
    }

    @Test
    fun `sixth consecutive recovery fails closed`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t4", recoveryCount = 5))
        val decision = engine.next(
            observation(),
            TaskStepResult(TaskStepOutcome.RECOVERABLE_FAILURE, "NO_OP"),
            false,
        )
        assertTrue(decision is TaskLoopDecision.Failed)
        assertEquals("RECOVERY_LIMIT", decision.code)
    }

    @Test
    fun `forty first action is rejected`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t5", stepCount = 40))
        val decision = engine.next(
            observation(),
            TaskStepResult(TaskStepOutcome.EXECUTED),
            false,
        )
        assertTrue(decision is TaskLoopDecision.Failed)
        assertEquals("STEP_LIMIT", decision.code)
    }

    @Test
    fun `kill switch halts before planning`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t6"))
        val decision = engine.next(observation(), null, killSwitchActive = true)
        assertTrue(decision is TaskLoopDecision.Failed)
        assertEquals("KILL_SWITCH", decision.code)
    }

    @Test
    fun `class C task without task-bound confirmation fails closed`() {
        val engine = TaskSessionEngine(
            TaskProgress(taskId = "t7", riskClass = RiskClass.C, confirmedRiskClassC = false)
        )
        val decision = engine.next(observation(), null, false)
        assertTrue(decision is TaskLoopDecision.Failed)
        assertEquals("CLASS_C_CONFIRMATION_REQUIRED", decision.code)
    }

    @Test
    fun `completion is terminal`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t8"))
        val decision = engine.next(
            observation(),
            TaskStepResult(TaskStepOutcome.TASK_COMPLETE),
            false,
        )
        assertTrue(decision is TaskLoopDecision.Completed)
        assertEquals(TaskLoopStatus.COMPLETED, decision.progress.status)
    }

    @Test
    fun `fatal failure is terminal`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "t9"))
        val decision = engine.next(
            observation(),
            TaskStepResult(TaskStepOutcome.FATAL_FAILURE, "SECURE_SURFACE"),
            false,
        )
        assertTrue(decision is TaskLoopDecision.Failed)
        assertEquals("SECURE_SURFACE", decision.code)
    }
}
