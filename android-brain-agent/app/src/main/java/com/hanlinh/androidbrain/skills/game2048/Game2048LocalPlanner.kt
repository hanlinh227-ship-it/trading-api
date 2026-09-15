package com.hanlinh.androidbrain.skills.game2048

import com.hanlinh.androidbrain.agent.MicroPlan
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.protocol.ClickNode
import com.hanlinh.androidbrain.protocol.Swipe

/**
 * Fast local 2048 planner used as a reference workload for the V5 persistent loop.
 * It intentionally ignores ads, purchases, links and account controls; restart is
 * allowed only through a tightly matched in-app game restart label.
 */
class Game2048LocalPlanner(
    private val snapshotProvider: () -> AccessibilitySnapshot?,
) {
    private var moveCount: Long = 0

    fun nextPlan(): MicroPlan? {
        val snapshot = snapshotProvider() ?: return null
        val restart = verifiedRestartControl(snapshot)
        if (terminalTextVisible(snapshot)) {
            return restart?.let {
                MicroPlan(
                    actions = listOf(ClickNode(it)),
                    reobserveAfter = setOf(0),
                    confidence = 0.99,
                )
            }
        }

        val width = (snapshot.screenWidth ?: DEFAULT_WIDTH).coerceAtLeast(2)
        val height = (snapshot.screenHeight ?: DEFAULT_HEIGHT).coerceAtLeast(2)
        val direction = STRATEGY[(moveCount % STRATEGY.size).toInt()]
        moveCount += 1
        return MicroPlan(
            actions = listOf(swipeFor(direction, width, height)),
            reobserveAfter = setOf(0),
            confidence = 0.98,
        )
    }

    fun resetAfterRestart() {
        moveCount = 0
    }

    private fun terminalTextVisible(snapshot: AccessibilitySnapshot): Boolean = snapshot.nodes.any { node ->
        val text = listOfNotNull(node.text, node.contentDescription)
            .joinToString(" ")
            .lowercase()
            .replace(Regex("\\s+"), " ")
        TERMINAL_PATTERNS.any(text::contains)
    }

    private fun verifiedRestartControl(snapshot: AccessibilitySnapshot): String? = snapshot.nodes
        .asSequence()
        .filter { it.enabled && it.visibleToUser }
        .firstOrNull { node ->
            val labels = listOfNotNull(node.text, node.contentDescription).map(::normalize)
            labels.any { it in RESTART_LABELS }
        }
        ?.nodeId

    private fun swipeFor(direction: Direction, width: Int, height: Int): Swipe {
        val left = point(width * 0.20, width)
        val right = point(width * 0.80, width)
        val middleX = point(width * 0.50, width)
        val middleY = point(height * 0.55, height)
        val top = point(height * 0.36, height)
        val bottom = point(height * 0.74, height)
        return when (direction) {
            Direction.LEFT -> Swipe(right, middleY, left, middleY, FAST_SWIPE_MS)
            Direction.RIGHT -> Swipe(left, middleY, right, middleY, FAST_SWIPE_MS)
            Direction.UP -> Swipe(middleX, bottom, middleX, top, FAST_SWIPE_MS)
            Direction.DOWN -> Swipe(middleX, top, middleX, bottom, FAST_SWIPE_MS)
        }
    }

    private fun point(value: Double, dimension: Int): Int =
        value.toInt().coerceIn(1, dimension - 1)

    private fun normalize(value: String): String = value
        .trim()
        .lowercase()
        .replace(Regex("\\s+"), " ")

    private companion object {
        val STRATEGY = listOf(Direction.LEFT, Direction.DOWN, Direction.LEFT, Direction.DOWN, Direction.RIGHT, Direction.DOWN)
        val TERMINAL_PATTERNS = setOf("game over", "no more moves", "trò chơi kết thúc", "hết nước đi")
        val RESTART_LABELS = setOf("try again", "new game", "chơi lại", "trò chơi mới")
        const val DEFAULT_WIDTH = 1080
        const val DEFAULT_HEIGHT = 2400
        const val FAST_SWIPE_MS = 90L
    }
}