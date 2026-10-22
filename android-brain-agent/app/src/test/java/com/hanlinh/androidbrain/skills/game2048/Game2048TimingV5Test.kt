package com.hanlinh.androidbrain.skills.game2048

import org.junit.Assert.assertTrue
import org.junit.Test

class Game2048TimingV5Test {
    @Test
    fun localSwipe_usesAdaptiveFastDuration() {
        val board = Game2048Board(listOf(
            2, 4, 8, 16,
            0, 2, 4, 8,
            0, 0, 2, 4,
            0, 0, 0, 2,
        ))
        val decision = Game2048Session(Game2048Solver(searchDepth = 1))
            .next(board, "frame-1", Game2048Region(0, 0, 1000, 1000))
        assertTrue(decision is Game2048Decision.Act)
        val action = (decision as Game2048Decision.Act).action
        assertTrue(action.durationMs in 60L..120L)
    }
}
