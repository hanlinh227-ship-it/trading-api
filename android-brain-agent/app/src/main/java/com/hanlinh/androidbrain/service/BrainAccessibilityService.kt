package com.hanlinh.androidbrain.service

import android.accessibilityservice.AccessibilityService
import android.content.res.Configuration
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.hanlinh.androidbrain.perception.AccessibilityScreenshotProvider
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.perception.AccessibilitySnapshotMapper
import com.hanlinh.androidbrain.perception.EventDrivenObserver
import com.hanlinh.androidbrain.perception.NodeBounds
import com.hanlinh.androidbrain.perception.RawAccessibilityNode
import com.hanlinh.androidbrain.perception.ScreenshotCapture

class BrainAccessibilityService : AccessibilityService() {
    companion object {
        @Volatile var current: BrainAccessibilityService? = null
            private set
    }

    private val screenshotProvider by lazy { AccessibilityScreenshotProvider(this) }
    private var eventObserver: EventDrivenObserver? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        current = this
        eventObserver = EventDrivenObserver.install(::snapshot)
        eventObserver?.refresh()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        eventObserver?.onAccessibilityEvent(event.eventType)
    }

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        EventDrivenObserver.clear(eventObserver)
        eventObserver = null
        if (current === this) current = null
        super.onDestroy()
    }

    fun snapshot(): AccessibilitySnapshot? {
        val root = rootInActiveWindow ?: return null
        val raw = mutableListOf<RawAccessibilityNode>()
        try {
            collect(root, "0", raw)
            val packageName = root.packageName?.toString().orEmpty()
            if (packageName.isBlank()) return null
            val title = root.window?.title?.toString()
            val metrics = resources.displayMetrics
            val orientation = when (resources.configuration.orientation) {
                Configuration.ORIENTATION_PORTRAIT -> "PORTRAIT"
                Configuration.ORIENTATION_LANDSCAPE -> "LANDSCAPE"
                else -> "UNDEFINED"
            }
            return AccessibilitySnapshotMapper().from(
                packageName = packageName,
                windowTitle = title,
                rawNodes = raw,
                screenWidth = metrics.widthPixels,
                screenHeight = metrics.heightPixels,
                orientation = orientation,
            )
        } finally {
            root.recycle()
        }
    }

    fun captureScreenshot(callback: (ScreenshotCapture) -> Unit) {
        screenshotProvider.captureScreenshot(callback)
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
