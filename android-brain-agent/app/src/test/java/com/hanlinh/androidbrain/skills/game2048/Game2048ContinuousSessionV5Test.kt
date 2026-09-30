package com.hanlinh.androidbrain.skills.game2048

import org.junit.Assert.assertTrue
import org.junit.Test

class Game2048ContinuousSessionV5Test {
    @Test
    fun gameOver_requestsRestartInsteadOfCompletingPersistentTask() {
        val terminal = Game2048Board(listOf(
            2, 4, 2, 4,
            4, 2, 4, 2,
            2, 4, 2, 4,
            4, 2, 4, 2,
        ))
        val session = Game2048Session()
        val decision = session.nextPersistent(
            board = terminal,
            fingerprint = "terminal",
            region = Game2048Region(0, 0, 1000, 1000),
            userStop = false,
        )
        assertTrue(decision is Game2048Decision.Restart)
    }

    @Test
    fun userStop_completesPersistentTaskWithoutRestart() {
        val terminal = Game2048Board(listOf(
            2, 4, 2, 4,
            4, 2, 4, 2,
            2, 4, 2, 4,
            4, 2, 4, 2,
        ))
        val decision = Game2048Session().nextPersistent(
            board = terminal,
            fingerprint = "terminal",
            region = Game2048Region(0, 0, 1000, 1000),
            userStop = true,
        )
        assertTrue(decision is Game2048Decision.Complete)
    }
}
