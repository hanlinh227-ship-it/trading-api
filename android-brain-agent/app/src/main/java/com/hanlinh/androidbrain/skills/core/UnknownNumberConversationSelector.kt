package com.hanlinh.androidbrain.skills.core

import com.hanlinh.androidbrain.perception.AccessibilityNode
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot

data class UnknownConversationTarget(
    val senderNodeId: String,
    val actionableNodeId: String,
)

data class UnknownConversationSelection(
    val targets: List<UnknownConversationTarget>,
    val permissionUnavailable: Boolean = false,
)

/**
 * Resolves visible unknown-number conversation rows entirely on-device.
 * No contact names, address-book rows, or lookup results beyond opaque node IDs
 * need to leave the phone.
 */
class UnknownNumberConversationSelector(
    private val classifier: UnknownNumberConversationClassifier,
) {
    fun select(snapshot: AccessibilitySnapshot): UnknownConversationSelection {
        val byId = snapshot.nodes.associateBy { it.nodeId }
        val targets = linkedMapOf<String, UnknownConversationTarget>()
        var permissionUnavailable = false

        snapshot.nodes
            .asSequence()
            .filter { it.visibleToUser }
            .forEach { node ->
                val sender = sequenceOf(node.text, node.contentDescription)
                    .filterNotNull()
                    .firstOrNull { classifier.classify(it) != ConversationClassification.NotPhoneNumber }
                    ?: return@forEach

                when (classifier.classify(sender)) {
                    ConversationClassification.UnknownConfirmed -> {
                        val actionable = nearestActionable(node, byId) ?: return@forEach
                        targets.putIfAbsent(
                            actionable.nodeId,
                            UnknownConversationTarget(
                                senderNodeId = node.nodeId,
                                actionableNodeId = actionable.nodeId,
                            ),
                        )
                    }
                    ConversationClassification.PermissionUnavailable -> permissionUnavailable = true
                    ConversationClassification.SavedContact,
                    ConversationClassification.NotPhoneNumber -> Unit
                }
            }

        return UnknownConversationSelection(
            targets = if (permissionUnavailable) emptyList() else targets.values.toList(),
            permissionUnavailable = permissionUnavailable,
        )
    }

    private fun nearestActionable(
        start: AccessibilityNode,
        byId: Map<String, AccessibilityNode>,
    ): AccessibilityNode? {
        var current: AccessibilityNode? = start
        repeat(MAX_PARENT_HOPS + 1) {
            val node = current ?: return null
            if (node.enabled && node.visibleToUser && (node.clickable || node.longClickable || node.checkable)) {
                return node
            }
            current = parentId(node.nodeId)?.let(byId::get)
        }
        return null
    }

    private fun parentId(nodeId: String): String? {
        if (!nodeId.startsWith("n:")) return null
        val path = nodeId.removePrefix("n:")
        val split = path.lastIndexOf('.')
        if (split < 0) return null
        return "n:${path.substring(0, split)}"
    }

    private companion object {
        const val MAX_PARENT_HOPS = 6
    }
}
