package com.hanlinh.androidbrain.service

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.perception.AccessibilitySnapshotMapper
import com.hanlinh.androidbrain.perception.NodeBounds
import com.hanlinh.androidbrain.perception.RawAccessibilityNode

class BrainAccessibilityService : AccessibilityService() {
    companion object {
        @Volatile var current: BrainAccessibilityService? = null
            private set
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        current = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    fun snapshot(): AccessibilitySnapshot? {
        val root = rootInActiveWindow ?: return null
        val raw = mutableListOf<RawAccessibilityNode>()
        collect(root, "0", raw)
        val packageName = root.packageName?.toString().orEmpty()
        val title = root.window?.title?.toString()
        return AccessibilitySnapshotMapper().from(packageName, title, raw)
    }

    private fun collect(
        node: AccessibilityNodeInfo,
        path: String,
        out: MutableList<RawAccessibilityNode>,
    ) {
        val rect = Rect()
        node.getBoundsInScreen(rect)
        out += RawAccessibilityNode(
            nodePath = path,
            resourceId = node.viewIdResourceName,
            text = node.text?.toString(),
            contentDescription = node.contentDescription?.toString(),
            className = node.className?.toString(),
            enabled = node.isEnabled,
            clickable = node.isClickable,
            longClickable = node.isLongClickable,
            editable = node.isEditable,
            scrollable = node.isScrollable,
            checkable = node.isCheckable,
            checked = node.isChecked,
            selected = node.isSelected,
            focused = node.isFocused,
            visibleToUser = node.isVisibleToUser,
            isPassword = node.isPassword,
            bounds = NodeBounds(rect.left, rect.top, rect.right, rect.bottom),
        )
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { child ->
                try { collect(child, "$path.$i", out) } finally { child.recycle() }
            }
        }
    }
}
