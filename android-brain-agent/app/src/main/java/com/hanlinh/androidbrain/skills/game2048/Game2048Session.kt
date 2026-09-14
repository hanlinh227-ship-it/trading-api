package com.hanlinh.androidbrain.skills.game2048

import com.hanlinh.androidbrain.protocol.Swipe

data class Game2048Region(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
) {
    init {
        require(right > left) { "right must be greater than left" }
        require(bottom > top) { "bottom must be greater than top" }
    }

    val centerX: Int get() = left + (right - left) / 2
    val centerY: Int get() = top + (bottom - top) / 2
}

sealed interface Game2048Decision {
    data class Act(val action: Swipe) : Game2048Decision
    data object AwaitBoardChange : Game2048Decision
    data object Complete : Game2048Decision
}

class Game2048Session(
    private val solver: Game2048Solver = Game2048Solver(),
) {
    private var lastActedFingerprint: String? = null

    fun next(
        board: Game2048Board,
        fingerprint: String,
        region: Game2048Region,
    ): Game2048Decision {
        if (board.isTerminal()) return Game2048Decision.Complete
        if (fingerprint.isNotBlank() && fingerprint == lastActedFingerprint) {
            return Game2048Decision.AwaitBoardChange
        }

        val direction = solver.bestMove(board) ?: return Game2048Decision.Complete
        val horizontalDistance = ((region.right - region.left) * SWIPE_FRACTION).toInt().coerceAtLeast(1)
        val verticalDistance = ((region.bottom - region.top) * SWIPE_FRACTION).toInt().coerceAtLeast(1)
        val action = when (direction) {
            Direction.LEFT -> Swipe(
                startX = (region.centerX + horizontalDistance / 2).coerceAtMost(region.right),
                startY = region.centerY,
                endX = (region.centerX - horizontalDistance / 2).coerceAtLeast(region.left),
                endY = region.centerY,
                durationMs = SWIPE_DURATION_MS,
            )
            Direction.RIGHT -> Swipe(
                startX = (region.centerX - horizontalDistance / 2).coerceAtLeast(region.left),
                startY = region.centerY,
                endX = (region.centerX + horizontalDistance / 2).coerceAtMost(region.right),
                endY = region.centerY,
                durationMs = SWIPE_DURATION_MS,
            )
            Direction.UP -> Swipe(
                startX = region.centerX,
                startY = (region.centerY + verticalDistance / 2).coerceAtMost(region.bottom),
                endX = region.centerX,
                endY = (region.centerY - verticalDistance / 2).coerceAtLeast(region.top),
                durationMs = SWIPE_DURATION_MS,
            )
            Direction.DOWN -> Swipe(
                startX = region.centerX,
                startY = (region.centerY - verticalDistance / 2).coerceAtLeast(region.top),
                endX = region.centerX,
                endY = (region.centerY + verticalDistance / 2).coerceAtMost(region.bottom),
                durationMs = SWIPE_DURATION_MS,
            )
        }
        lastActedFingerprint = fingerprint
        return Game2048Decision.Act(action)
    }

    private companion object {
        const val SWIPE_FRACTION = 0.55
        const val SWIPE_DURATION_MS = 220L
    }
}
