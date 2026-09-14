package com.hanlinh.androidbrain.service

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.graphics.Rect
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
        collect(root, raw)
        val packageName = root.packageName?.toString().orEmpty()
        val title = root.window?.title?.toString()
        return AccessibilitySnapshotMapper().from(packageName, title, raw)
    }

    private fun collect(node: AccessibilityNodeInfo, out: MutableList<RawAccessibilityNode>) {
        val rect = Rect()
        node.getBoundsInScreen(rect)
        out += RawAccessibilityNode(
            resourceId = node.viewIdResourceName,
            text = node.text?.toString(),
            contentDescription = node.contentDescription?.toString(),
            className = node.className?.toString(),
            enabled = node.isEnabled,
            clickable = node.isClickable,
            isPassword = node.isPassword,
            bounds = NodeBounds(rect.left, rect.top, rect.right, rect.bottom),
        )
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { child ->
                try { collect(child, out) } finally { child.recycle() }
            }
        }
    }
}
