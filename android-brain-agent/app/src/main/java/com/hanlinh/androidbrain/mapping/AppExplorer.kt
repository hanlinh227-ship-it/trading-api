package com.hanlinh.androidbrain.mapping

import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.ClickNode
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.ReadScreen
import com.hanlinh.androidbrain.protocol.ScrollNode

class AppExplorer(
    private val minimumPathConfidence: Double = 0.6,
) {
    fun mayExplore(action: Action, safeSemanticNavigation: Boolean = false): Boolean {
        if (action.riskClass != RiskClass.A) return false
        return when (action) {
            GlobalBack, ReadScreen -> true
            is ScrollNode -> true
            is ClickNode -> safeSemanticNavigation
            else -> false
        }
    }

    fun shortestVerifiedPath(
        transitions: List<TransitionEdge>,
        fromScreenId: String,
        toScreenId: String,
    ): List<TransitionEdge>? {
        if (fromScreenId == toScreenId) return emptyList()
        val outgoing = transitions
            .filter { it.confidence >= minimumPathConfidence && it.successCount > 0 }
            .groupBy { it.fromScreenId }
        val queue = ArrayDeque<String>()
        val previous = mutableMapOf<String, TransitionEdge>()
        val visited = mutableSetOf(fromScreenId)
        queue.add(fromScreenId)
        while (queue.isNotEmpty()) {
            val current = queue.removeFirst()
            for (edge in outgoing[current].orEmpty().sortedByDescending { it.confidence }) {
                if (!visited.add(edge.toScreenId)) continue
                previous[edge.toScreenId] = edge
                if (edge.toScreenId == toScreenId) {
                    val path = mutableListOf<TransitionEdge>()
                    var cursor = toScreenId
                    while (cursor != fromScreenId) {
                        val step = previous[cursor] ?: return null
                        path += step
                        cursor = step.fromScreenId
                    }
                    return path.asReversed()
                }
                queue.add(edge.toScreenId)
            }
        }
        return null
    }

    fun shouldStopExploring(
        credentialOrAuthenticationVisible: Boolean,
        secureSurface: Boolean,
        appScopeExited: Boolean,
        repeatedNoNewCoverage: Boolean,
        consequentialOnlyControls: Boolean,
    ): Boolean = credentialOrAuthenticationVisible || secureSurface || appScopeExited ||
        repeatedNoNewCoverage || consequentialOnlyControls
}
