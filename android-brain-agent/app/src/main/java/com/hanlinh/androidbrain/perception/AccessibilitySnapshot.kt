package com.hanlinh.androidbrain.perception

import java.nio.charset.StandardCharsets
import java.security.MessageDigest

data class NodeBounds(val left: Int, val top: Int, val right: Int, val bottom: Int)

data class RawAccessibilityNode(
    val nodePath: String = "0",
    val resourceId: String?,
    val text: String?,
    val contentDescription: String?,
    val className: String?,
    val enabled: Boolean,
    val clickable: Boolean,
    val longClickable: Boolean = false,
    val editable: Boolean = false,
    val scrollable: Boolean = false,
    val checkable: Boolean = false,
    val checked: Boolean = false,
    val selected: Boolean = false,
    val focused: Boolean = false,
    val visibleToUser: Boolean = true,
    val isPassword: Boolean,
    val bounds: NodeBounds,
)

data class AccessibilityNode(
    val nodeId: String,
    val resourceId: String?,
    val text: String?,
    val contentDescription: String?,
    val className: String?,
    val enabled: Boolean,
    val clickable: Boolean,
    val longClickable: Boolean,
    val editable: Boolean,
    val scrollable: Boolean,
    val checkable: Boolean,
    val checked: Boolean,
    val selected: Boolean,
    val focused: Boolean,
    val visibleToUser: Boolean,
    val bounds: NodeBounds,
)

data class AccessibilitySnapshot(
    val packageName: String,
    val windowTitle: String?,
    val nodes: List<AccessibilityNode>,
    val screenWidth: Int? = null,
    val screenHeight: Int? = null,
    val orientation: String? = null,
    val screenshotHash: String? = null,
    val regionHashes: Map<String, String> = emptyMap(),
) {
    fun fingerprint(): String {
        val canonical = buildString {
            append(packageName).append('\n')
            append(windowTitle.orEmpty()).append('\n')
            append(screenWidth ?: -1).append('x').append(screenHeight ?: -1).append('|')
            append(orientation.orEmpty()).append('|')
            append(screenshotHash.orEmpty()).append('\n')
            regionHashes.toSortedMap().forEach { (region, hash) ->
                append("region:").append(region).append('=').append(hash).append('\n')
            }
            nodes.forEach { node ->
                append(node.nodeId).append('|')
                append(node.resourceId.orEmpty()).append('|')
                append(node.text.orEmpty()).append('|')
                append(node.contentDescription.orEmpty()).append('|')
                append(node.className.orEmpty()).append('|')
                append(node.enabled).append('|')
                append(node.clickable).append('|')
                append(node.longClickable).append('|')
                append(node.editable).append('|')
                append(node.scrollable).append('|')
                append(node.checkable).append('|')
                append(node.checked).append('|')
                append(node.selected).append('|')
                append(node.focused).append('|')
                append(node.visibleToUser).append('|')
                append(node.bounds.left).append(',')
                append(node.bounds.top).append(',')
                append(node.bounds.right).append(',')
                append(node.bounds.bottom).append('\n')
            }
        }
        return MessageDigest.getInstance("SHA-256")
            .digest(canonical.toByteArray(StandardCharsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
    }
}

typealias DeviceObservation = AccessibilitySnapshot

data class ObservedNode(
    val nodeId: String,
    val resourceId: String?,
    val text: String?,
    val contentDescription: String?,
    val className: String?,
    val enabled: Boolean,
    val clickable: Boolean,
    val longClickable: Boolean,
    val editable: Boolean,
    val scrollable: Boolean,
    val checkable: Boolean,
    val checked: Boolean,
    val selected: Boolean,
    val focused: Boolean,
    val visibleToUser: Boolean,
    val bounds: NodeBounds,
)

class AccessibilitySnapshotMapper(
    private val sanitizer: ObservationSanitizer = ObservationSanitizer(),
) {
    fun from(
        packageName: String,
        windowTitle: String?,
        rawNodes: List<RawAccessibilityNode>,
        screenWidth: Int? = null,
        screenHeight: Int? = null,
        orientation: String? = null,
        screenshotHash: String? = null,
        regionHashes: Map<String, String> = emptyMap(),
    ): AccessibilitySnapshot = AccessibilitySnapshot(
        packageName = packageName,
        windowTitle = windowTitle,
        nodes = rawNodes.map { raw ->
            AccessibilityNode(
                nodeId = "n:${raw.nodePath}",
                resourceId = raw.resourceId,
                text = sanitizer.sanitizeText(raw.text, raw.isPassword, raw.resourceId, raw.className),
                contentDescription = sanitizer.sanitizeText(
                    raw.contentDescription,
                    raw.isPassword,
                    raw.resourceId,
                    raw.className,
                ),
                className = raw.className,
                enabled = raw.enabled,
                clickable = raw.clickable,
                longClickable = raw.longClickable,
                editable = raw.editable,
                scrollable = raw.scrollable,
                checkable = raw.checkable,
                checked = raw.checked,
                selected = raw.selected,
                focused = raw.focused,
                visibleToUser = raw.visibleToUser,
                bounds = raw.bounds,
            )
        },
        screenWidth = screenWidth,
        screenHeight = screenHeight,
        orientation = orientation,
        screenshotHash = screenshotHash,
        regionHashes = regionHashes.toSortedMap(),
    )
}
