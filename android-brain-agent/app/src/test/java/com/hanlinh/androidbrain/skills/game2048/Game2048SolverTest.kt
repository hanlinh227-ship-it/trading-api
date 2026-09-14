package com.hanlinh.androidbrain.skills.game2048

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Game2048SolverTest {
    @Test
    fun `left move merges each pair once and scores merges`() {
        val board = Game2048Board(listOf(
            2, 2, 4, 4,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
        ))
        val result = board.move(Direction.LEFT)
        assertTrue(result.moved)
        assertEquals(12, result.scoreGain)
        assertEquals(listOf(4, 8, 0, 0), result.board.row(0))
    }

    @Test
    fun `all four directions preserve tile sum`() {
        val board = Game2048Board(listOf(
            2, 0, 2, 4,
            4, 4, 8, 0,
            2, 2, 4, 4,
            0, 8, 8, 16,
        ))
        val sum = board.cells.sum()
        Direction.entries.forEach { direction ->
            assertEquals(sum, board.move(direction).board.cells.sum())
        }
    }

    @Test
    fun `solver returns only a legal move`() {
        val board = Game2048Board(listOf(
            2, 4, 8, 16,
            0, 2, 4, 8,
            0, 0, 2, 4,
            0, 0, 0, 2,
        ))
        val move = Game2048Solver().bestMove(board)
        assertTrue(move != null)
        assertTrue(board.move(move!!).moved)
    }

    @Test
    fun `terminal board has no best move`() {
        val board = Game2048Board(listOf(
            2, 4, 2, 4,
            4, 2, 4, 2,
            2, 4, 2, 4,
            4, 2, 4, 2,
        ))
        assertTrue(board.isTerminal())
        assertNull(Game2048Solver().bestMove(board))
    }

    @Test
    fun `seeded simulation never emits illegal moves`() {
        var board = Game2048Board(listOf(
            2, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 2,
        ))
        val solver = Game2048Solver(searchDepth = 2)
        var turns = 0
        while (!board.isTerminal() && turns < 250) {
            val direction = solver.bestMove(board) ?: break
            val move = board.move(direction)
            assertTrue(move.moved)
            board = move.board.spawnDeterministic(turns)
            turns += 1
        }
        assertTrue(turns > 20)
        assertFalse(board.cells.any { it < 0 })
        assertTrue(board.maxTile() >= 16)
    }
}
