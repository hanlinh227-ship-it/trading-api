package com.hanlinh.androidbrain.agent

import org.junit.Assert.assertEquals
import org.junit.Test

class TaskResumeV4Test {
    @Test
    fun `remote checkpoint resumes local long task without replaying old step count`() {
        val engine = TaskSessionEngine(
            TaskProgress(taskId = "resume", persistence = TaskPersistence.LONG_RUNNING),
        )
        engine.resume(
            TaskProgressCheckpoint(
                stepCount = 125,
                epoch = 2,
                epochStepCount = 25,
                checkpointCount = 2,
                recoveryCount = 0,
            )
        )

        val progress = engine.currentProgress()
        assertEquals(125, progress.stepCount)
        assertEquals(2, progress.epoch)
        assertEquals(25, progress.epochStepCount)
        assertEquals(2, progress.checkpointCount)
    }
}
