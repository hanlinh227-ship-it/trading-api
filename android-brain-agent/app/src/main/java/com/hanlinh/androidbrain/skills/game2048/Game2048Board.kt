package com.hanlinh.androidbrain.skills.game2048

enum class Direction { UP, DOWN, LEFT, RIGHT }

data class MoveResult(
    val board: Game2048Board,
    val moved: Boolean,
    val scoreGain: Int,
)

data class Game2048Board(val cells: List<Int>) {
    init {
        require(cells.size == SIZE * SIZE) { "2048 board must contain exactly 16 cells" }
        require(cells.all { it >= 0 }) { "2048 cells must be non-negative" }
    }

    fun row(index: Int): List<Int> {
        require(index in 0 until SIZE)
        val start = index * SIZE
        return cells.subList(start, start + SIZE)
    }

    fun maxTile(): Int = cells.maxOrNull() ?: 0

    fun emptyIndices(): List<Int> = cells.indices.filter { cells[it] == 0 }

    fun withCell(index: Int, value: Int): Game2048Board {
        require(index in cells.indices)
        require(value >= 0)
        val next = cells.toMutableList()
        next[index] = value
        return Game2048Board(next)
    }

    fun spawnDeterministic(seed: Int): Game2048Board {
        val empty = emptyIndices()
        if (empty.isEmpty()) return this
        val normalizedSeed = seed.toLong() and 0x7fffffffL
        val target = empty[(normalizedSeed % empty.size).toInt()]
        val value = if (normalizedSeed % 10L == 0L) 4 else 2
        return withCell(target, value)
    }

    fun isTerminal(): Boolean = Direction.entries.none { move(it).moved }

    fun move(direction: Direction): MoveResult {
        val next = cells.toMutableList()
        var scoreGain = 0

        for (lineIndex in 0 until SIZE) {
            val indices = lineIndices(direction, lineIndex)
            val line = indices.map { cells[it] }
            val merged = mergeLine(line)
            scoreGain += merged.scoreGain
            indices.forEachIndexed { offset, cellIndex ->
                next[cellIndex] = merged.values[offset]
            }
        }

        val board = Game2048Board(next)
        return MoveResult(board, board.cells != cells, scoreGain)
    }

    private fun lineIndices(direction: Direction, lineIndex: Int): List<Int> = when (direction) {
        Direction.LEFT -> (0 until SIZE).map { column -> lineIndex * SIZE + column }
        Direction.RIGHT -> (SIZE - 1 downTo 0).map { column -> lineIndex * SIZE + column }
        Direction.UP -> (0 until SIZE).map { row -> row * SIZE + lineIndex }
        Direction.DOWN -> (SIZE - 1 downTo 0).map { row -> row * SIZE + lineIndex }
    }

    private data class MergedLine(val values: List<Int>, val scoreGain: Int)

    private fun mergeLine(values: List<Int>): MergedLine {
        val compact = values.filter { it != 0 }
        val output = ArrayList<Int>(SIZE)
        var score = 0
        var index = 0

        while (index < compact.size) {
            val current = compact[index]
            if (index + 1 < compact.size && compact[index + 1] == current) {
                val merged = current * 2
                output += merged
                score += merged
                index += 2
            } else {
                output += current
                index += 1
            }
        }

        while (output.size < SIZE) output += 0
        return MergedLine(output, score)
    }

    companion object {
        const val SIZE = 4
    }
}
