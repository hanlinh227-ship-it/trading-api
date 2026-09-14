package com.hanlinh.androidbrain.skills.game2048

import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max

class Game2048Solver(
    private val searchDepth: Int = 2,
) {
    init {
        require(searchDepth >= 1)
    }

    fun bestMove(board: Game2048Board): Direction? {
        var bestDirection: Direction? = null
        var bestScore = Double.NEGATIVE_INFINITY

        for (direction in DIRECTION_PRIORITY) {
            val move = board.move(direction)
            if (!move.moved) continue
            val score = move.scoreGain * MERGE_WEIGHT + chanceValue(move.board, searchDepth - 1)
            if (score > bestScore) {
                bestScore = score
                bestDirection = direction
            }
        }

        return bestDirection
    }

    private fun playerValue(board: Game2048Board, depth: Int): Double {
        if (depth <= 0 || board.isTerminal()) return evaluate(board)

        var best = Double.NEGATIVE_INFINITY
        for (direction in DIRECTION_PRIORITY) {
            val move = board.move(direction)
            if (!move.moved) continue
            best = max(best, move.scoreGain * MERGE_WEIGHT + chanceValue(move.board, depth - 1))
        }
        return if (best.isFinite()) best else evaluate(board)
    }

    private fun chanceValue(board: Game2048Board, depth: Int): Double {
        val empty = board.emptyIndices()
        if (empty.isEmpty()) return playerValue(board, depth)

        var total = 0.0
        for (index in empty) {
            total += SPAWN_TWO_PROBABILITY * playerValue(board.withCell(index, 2), depth)
            total += SPAWN_FOUR_PROBABILITY * playerValue(board.withCell(index, 4), depth)
        }
        return total / empty.size
    }

    private fun evaluate(board: Game2048Board): Double {
        val emptyScore = board.emptyIndices().size * EMPTY_WEIGHT
        val maxTile = board.maxTile().coerceAtLeast(2)
        val maxTileScore = log2(maxTile) * MAX_TILE_WEIGHT
        val cornerScore = if (maxTileInCorner(board)) maxTile * CORNER_WEIGHT else 0.0
        val mergeScore = mergePotential(board) * MERGE_POTENTIAL_WEIGHT
        val smoothnessScore = smoothness(board) * SMOOTHNESS_WEIGHT
        val monotonicityScore = monotonicity(board) * MONOTONICITY_WEIGHT
        return emptyScore + maxTileScore + cornerScore + mergeScore + smoothnessScore + monotonicityScore
    }

    private fun maxTileInCorner(board: Game2048Board): Boolean {
        val maxTile = board.maxTile()
        return listOf(0, 3, 12, 15).any { board.cells[it] == maxTile }
    }

    private fun mergePotential(board: Game2048Board): Int {
        var count = 0
        for (row in 0 until Game2048Board.SIZE) {
            for (column in 0 until Game2048Board.SIZE) {
                val index = row * Game2048Board.SIZE + column
                val value = board.cells[index]
                if (value == 0) continue
                if (column + 1 < Game2048Board.SIZE && board.cells[index + 1] == value) count += 1
                if (row + 1 < Game2048Board.SIZE && board.cells[index + Game2048Board.SIZE] == value) count += 1
            }
        }
        return count
    }

    private fun smoothness(board: Game2048Board): Double {
        var penalty = 0.0
        for (row in 0 until Game2048Board.SIZE) {
            for (column in 0 until Game2048Board.SIZE) {
                val index = row * Game2048Board.SIZE + column
                val value = board.cells[index]
                if (value == 0) continue
                val valueLog = log2(value)
                if (column + 1 < Game2048Board.SIZE) {
                    val right = board.cells[index + 1]
                    if (right != 0) penalty -= abs(valueLog - log2(right))
                }
                if (row + 1 < Game2048Board.SIZE) {
                    val down = board.cells[index + Game2048Board.SIZE]
                    if (down != 0) penalty -= abs(valueLog - log2(down))
                }
            }
        }
        return penalty
    }

    private fun monotonicity(board: Game2048Board): Double {
        var score = 0.0
        for (row in 0 until Game2048Board.SIZE) {
            score += monotonicLine(board.row(row))
        }
        for (column in 0 until Game2048Board.SIZE) {
            val values = (0 until Game2048Board.SIZE).map { row ->
                board.cells[row * Game2048Board.SIZE + column]
            }
            score += monotonicLine(values)
        }
        return score
    }

    private fun monotonicLine(values: List<Int>): Double {
        var increasing = 0.0
        var decreasing = 0.0
        for (index in 0 until values.lastIndex) {
            val current = if (values[index] == 0) 0.0 else log2(values[index])
            val next = if (values[index + 1] == 0) 0.0 else log2(values[index + 1])
            if (current > next) decreasing += next - current else increasing += current - next
        }
        return max(increasing, decreasing)
    }

    private fun log2(value: Int): Double = ln(value.toDouble()) / ln(2.0)

    private companion object {
        val DIRECTION_PRIORITY = listOf(Direction.LEFT, Direction.DOWN, Direction.RIGHT, Direction.UP)
        const val SPAWN_TWO_PROBABILITY = 0.9
        const val SPAWN_FOUR_PROBABILITY = 0.1
        const val MERGE_WEIGHT = 12.0
        const val EMPTY_WEIGHT = 300.0
        const val MAX_TILE_WEIGHT = 60.0
        const val CORNER_WEIGHT = 2.0
        const val MERGE_POTENTIAL_WEIGHT = 45.0
        const val SMOOTHNESS_WEIGHT = 12.0
        const val MONOTONICITY_WEIGHT = 18.0
    }
}
