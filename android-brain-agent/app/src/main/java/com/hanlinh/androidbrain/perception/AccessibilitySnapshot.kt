package com.hanlinh.androidbrain.perception

data class NodeBounds(val left: Int, val top: Int, val right: Int, val bottom: Int)

data class RawAccessibilityNode(
    val resourceId: String?,
    val text: String?,
    val contentDescription: String?,
    val className: String?,
    val enabled: Boolean,
    val clickable: Boolean,
    val isPassword: Boolean,
    val bounds: NodeBounds,
)

data class AccessibilityNode(
    val resourceId: String?,
    val text: String?,
    val contentDescription: String?,
    val className: String?,
    val enabled: Boolean,
    val clickable: Boolean,
    val bounds: NodeBounds,
)

data class AccessibilitySnapshot(
    val packageName: String,
    val windowTitle: String?,
    val nodes: List<AccessibilityNode>,
)

class AccessibilitySnapshotMapper {
    fun from(
        packageName: String,
        windowTitle: String?,
        rawNodes: List<RawAccessibilityNode>,
    ): AccessibilitySnapshot = AccessibilitySnapshot(
        packageName = packageName,
        windowTitle = windowTitle,
        nodes = rawNodes.map { raw ->
            AccessibilityNode(
                resourceId = raw.resourceId,
                text = if (raw.isPassword) null else raw.text,
                contentDescription = if (raw.isPassword) null else raw.contentDescription,
                className = raw.className,
                enabled = raw.enabled,
                clickable = raw.clickable,
                bounds = raw.bounds,
            )
        },
    )
}
