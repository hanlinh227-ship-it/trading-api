package com.hanlinh.androidbrain.skills.game2048

import com.hanlinh.androidbrain.execution.AdaptiveActionScheduler
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
    data class Restart(
        val acceptedLabels: Set<String> = setOf("Try Again", "New Game"),
        val requiresSamePackage: Boolean = true,
        val requiresFreshBoardObservation: Boolean = true,
    ) : Game2048Decision
}

class Game2048Session(
    private val solver: Game2048Solver = Game2048Solver(),
    private val scheduler: AdaptiveActionScheduler = AdaptiveActionScheduler(),
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
        val rawAction = swipeFor(direction, region)
        val timing = scheduler.timingFor(
            packageName = LOCAL_GAME_PACKAGE,
            screenId = BOARD_SCREEN_ID,
            action = rawAction,
            profile = null,
        )
        val action = scheduler.applyTiming(rawAction, timing) as Swipe
        lastActedFingerprint = fingerprint
        return Game2048Decision.Act(action)
    }

    fun nextPersistent(
        board: Game2048Board,
        fingerprint: String,
        region: Game2048Region,
        userStop: Boolean,
    ): Game2048Decision {
        if (userStop) return Game2048Decision.Complete
        if (board.isTerminal()) {
            lastActedFingerprint = null
            return Game2048Decision.Restart()
        }
        return next(board, fingerprint, region)
    }

    private fun swipeFor(direction: Direction, region: Game2048Region): Swipe {
        val horizontalDistance = ((region.right - region.left) * SWIPE_FRACTION).toInt().coerceAtLeast(1)
        val verticalDistance = ((region.bottom - region.top) * SWIPE_FRACTION).toInt().coerceAtLeast(1)
        return when (direction) {
            Direction.LEFT -> Swipe(
                startX = (region.centerX + horizontalDistance / 2).coerceAtMost(region.right),
                startY = region.centerY,
                endX = (region.centerX - horizontalDistance / 2).coerceAtLeast(region.left),
                endY = region.centerY,
            )
            Direction.RIGHT -> Swipe(
                startX = (region.centerX - horizontalDistance / 2).coerceAtLeast(region.left),
                startY = region.centerY,
                endX = (region.centerX + horizontalDistance / 2).coerceAtMost(region.right),
                endY = region.centerY,
            )
            Direction.UP -> Swipe(
                startX = region.centerX,
                startY = (region.centerY + verticalDistance / 2).coerceAtMost(region.bottom),
                endX = region.centerX,
                endY = (region.centerY - verticalDistance / 2).coerceAtLeast(region.top),
            )
            Direction.DOWN -> Swipe(
                startX = region.centerX,
                startY = (region.centerY - verticalDistance / 2).coerceAtLeast(region.top),
                endX = region.centerX,
                endY = (region.centerY + verticalDistance / 2).coerceAtMost(region.bottom),
            )
        }
    }

    private companion object {
        const val SWIPE_FRACTION = 0.55
        const val LOCAL_GAME_PACKAGE = "local.game2048"
        const val BOARD_SCREEN_ID = "board"
    }
}
