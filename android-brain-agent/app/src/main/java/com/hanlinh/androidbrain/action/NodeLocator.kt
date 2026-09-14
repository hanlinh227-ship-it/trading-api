package com.hanlinh.androidbrain.action

import android.view.accessibility.AccessibilityNodeInfo

/**
 * Resolves the ephemeral node IDs emitted by AccessibilitySnapshotMapper.
 * IDs are traversal paths (for example n:0.2.1), not text selectors, so V3
 * execution remains deterministic even when labels are duplicated or absent.
 */
class NodeLocator {
    fun locate(root: AccessibilityNodeInfo, nodeId: String): AccessibilityNodeInfo? =
        locateByNodeId(root, nodeId) { node, index -> node.getChild(index) }

    fun <T> locateByNodeId(
        root: T,
        nodeId: String,
        childAt: (T, Int) -> T?,
    ): T? {
        val path = parsePath(nodeId) ?: return null
        var current = root
        for (index in path.drop(1)) {
            current = childAt(current, index) ?: return null
        }
        return current
    }

    fun isEphemeralNodeId(value: String): Boolean = parsePath(value) != null

    private fun parsePath(nodeId: String): List<Int>? {
        if (!nodeId.startsWith(PREFIX)) return null
        val raw = nodeId.removePrefix(PREFIX)
        if (raw.isBlank()) return null

        val path = raw.split('.').map { segment ->
            if (segment.isBlank()) return null
            val index = segment.toIntOrNull() ?: return null
            if (index < 0) return null
            index
        }
        if (path.isEmpty() || path.first() != ROOT_INDEX) return null
        return path
    }

    private companion object {
        const val PREFIX = "n:"
        const val ROOT_INDEX = 0
    }
}
