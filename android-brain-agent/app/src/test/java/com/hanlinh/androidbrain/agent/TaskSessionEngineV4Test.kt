package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskSessionEngineV4Test {
    private fun observation(index: Int) = AccessibilitySnapshot("com.example", "screen-$index", emptyList())

    @Test
    fun `long horizon advances beyond one hundred actions through checkpoints`() {
        val engine = TaskSessionEngine(
            TaskProgress(taskId = "long", persistence = TaskPersistence.LONG_RUNNING),
        )
        engine.next(observation(0), null, false)
        var decision: TaskLoopDecision = TaskLoopDecision.PlanNext(engine.currentProgress())
        for (i in 1..125) {
            decision = engine.next(observation(i), TaskStepResult(TaskStepOutcome.EXECUTED), false)
            assertTrue(decision is TaskLoopDecision.PlanNext)
        }
        assertEquals(125, decision.progress.stepCount)
        assertEquals(2, decision.progress.epoch)
        assertEquals(25, decision.progress.epochStepCount)
        assertEquals(2, decision.progress.checkpointCount)
    }

    @Test
    fun `fiftieth action creates a checkpoint rather than failing`() {
        val engine = TaskSessionEngine(
            TaskProgress(
                taskId = "checkpoint",
                persistence = TaskPersistence.LONG_RUNNING,
                stepCount = 49,
                epochStepCount = 49,
            ),
        )
        engine.next(observation(0), null, false)
        val decision = engine.next(observation(1), TaskStepResult(TaskStepOutcome.EXECUTED), false)
        assertTrue(decision is TaskLoopDecision.PlanNext)
        assertEquals(1, decision.progress.epoch)
        assertEquals(1, decision.progress.checkpointCount)
        assertEquals(0, decision.progress.epochStepCount)
    }

    @Test
    fun `cancel preserves cancelled terminal state`() {
        val engine = TaskSessionEngine(TaskProgress(taskId = "cancel", persistence = TaskPersistence.LONG_RUNNING))
        val cancelled = engine.cancel()
        assertEquals(TaskLoopStatus.CANCELLED, cancelled.status)
        val decision = engine.next(observation(0), null, false)
        assertTrue(decision is TaskLoopDecision.Failed)
        assertEquals("CANCELLED", decision.code)
        assertEquals(TaskLoopStatus.CANCELLED, decision.progress.status)
    }
}
