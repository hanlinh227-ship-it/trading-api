package com.hanlinh.androidbrain.skills.game2048

import com.hanlinh.androidbrain.protocol.Swipe
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class Game2048SessionTest {
    private val board = Game2048Board(listOf(
        2, 4, 8, 16,
        0, 2, 4, 8,
        0, 0, 2, 4,
        0, 0, 0, 2,
    ))

    @Test
    fun `session emits one bounded swipe then waits for a changed visual board`() {
        val session = Game2048Session(Game2048Solver(searchDepth = 1))
        val region = Game2048Region(100, 400, 980, 1280)
        val first = session.next(board, "frame-1", region)
        assertTrue(first is Game2048Decision.Act)
        val swipe = (first as Game2048Decision.Act).action
        assertTrue(swipe is Swipe)
        swipe as Swipe
        assertTrue(swipe.startX in region.left..region.right)
        assertTrue(swipe.endX in region.left..region.right)
        assertTrue(swipe.startY in region.top..region.bottom)
        assertTrue(swipe.endY in region.top..region.bottom)

        val unchanged = session.next(board, "frame-1", region)
        assertTrue(unchanged is Game2048Decision.AwaitBoardChange)
    }

    @Test
    fun `terminal board completes without a swipe`() {
        val terminal = Game2048Board(listOf(
            2, 4, 2, 4,
            4, 2, 4, 2,
            2, 4, 2, 4,
            4, 2, 4, 2,
        ))
        val decision = Game2048Session().next(terminal, "terminal", Game2048Region(0, 0, 1000, 1000))
        assertEquals(Game2048Decision.Complete, decision)
    }
}
