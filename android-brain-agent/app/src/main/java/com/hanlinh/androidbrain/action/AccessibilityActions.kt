package com.hanlinh.androidbrain.action

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.ClearText
import com.hanlinh.androidbrain.protocol.ClickNode
import com.hanlinh.androidbrain.protocol.DoubleTapPoint
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.GlobalHome
import com.hanlinh.androidbrain.protocol.GlobalNotifications
import com.hanlinh.androidbrain.protocol.GlobalQuickSettings
import com.hanlinh.androidbrain.protocol.GlobalRecents
import com.hanlinh.androidbrain.protocol.LongClickNode
import com.hanlinh.androidbrain.protocol.LongPressPoint
import com.hanlinh.androidbrain.protocol.ScrollDirection
import com.hanlinh.androidbrain.protocol.ScrollNode
import com.hanlinh.androidbrain.protocol.SetText
import com.hanlinh.androidbrain.protocol.Swipe
import com.hanlinh.androidbrain.protocol.TapPoint
import com.hanlinh.androidbrain.protocol.Wait
import com.hanlinh.androidbrain.service.BrainAccessibilityService

class AccessibilityActions(
    private val serviceProvider: () -> BrainAccessibilityService? = { BrainAccessibilityService.current },
    private val nodeLocator: NodeLocator = NodeLocator(),
    private val sleeper: (Long) -> Unit = { durationMs -> Thread.sleep(durationMs) },
) {
    fun click(action: ClickNode): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = findNode(root, action.selector) ?: return false
        return clickNodeOrParent(node)
    }

    fun longClick(action: LongClickNode): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = findNode(root, action.selector) ?: return false
        return longClickNodeOrParent(node)
    }

    fun setText(action: SetText): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = findNode(root, action.selector) ?: return false
        return replaceText(node, action.value)
    }

    fun clearText(action: ClearText): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = nodeLocator.locate(root, action.nodeId) ?: return false
        return replaceText(node, "")
    }

    fun globalBack(): Boolean =
        serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK) == true

    fun globalHome(): Boolean =
        serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME) == true

    fun globalRecents(): Boolean =
        serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS) == true

    fun globalNotifications(): Boolean =
        serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS) == true

    fun globalQuickSettings(): Boolean =
        serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS) == true

    fun swipe(action: Swipe): Boolean {
        val service = serviceProvider() ?: return false
        val path = Path().apply {
            moveTo(action.startX.toFloat(), action.startY.toFloat())
            lineTo(action.endX.toFloat(), action.endY.toFloat())
        }
        val gesture = GestureDescription.Builder()
            .addStroke(
                GestureDescription.StrokeDescription(
                    path,
                    0,
                    action.durationMs.coerceIn(MIN_GESTURE_MS, MAX_GESTURE_MS),
                )
            )
            .build()
        return service.dispatchGesture(gesture, null, null)
    }

    fun tapPoint(action: TapPoint): Boolean =
        dispatchPointGesture(action.x, action.y, TAP_DURATION_MS)

    fun longPressPoint(action: LongPressPoint): Boolean =
        dispatchPointGesture(
            action.x,
            action.y,
            action.durationMs.coerceIn(MIN_LONG_PRESS_MS, MAX_GESTURE_MS),
        )

    fun doubleTapPoint(action: DoubleTapPoint): Boolean {
        if (action.x < 0 || action.y < 0) return false
        val service = serviceProvider() ?: return false
        val first = pointPath(action.x, action.y)
        val second = pointPath(action.x, action.y)
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(first, 0, TAP_DURATION_MS))
            .addStroke(
                GestureDescription.StrokeDescription(
                    second,
                    DOUBLE_TAP_INTERVAL_MS,
                    TAP_DURATION_MS,
                )
            )
            .build()
        return service.dispatchGesture(gesture, null, null)
    }

    fun scrollNode(action: ScrollNode): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = nodeLocator.locate(root, action.nodeId) ?: return false
        val accessibilityAction = when (action.direction) {
            ScrollDirection.FORWARD -> AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
            ScrollDirection.BACKWARD -> AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
        }
        return performNodeActionOrParent(node, accessibilityAction)
    }

    fun wait(action: Wait): Boolean {
        if (action.durationMs < 0) return false
        return try {
            sleeper(action.durationMs.coerceAtMost(MAX_WAIT_MS))
            true
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
            false
        }
    }

    fun execute(action: Action): Boolean = when (action) {
        is ClickNode -> click(action)
        is LongClickNode -> longClick(action)
        is SetText -> setText(action)
        is ClearText -> clearText(action)
        is Swipe -> swipe(action)
        is TapPoint -> tapPoint(action)
        is LongPressPoint -> longPressPoint(action)
        is DoubleTapPoint -> doubleTapPoint(action)
        is ScrollNode -> scrollNode(action)
        is Wait -> wait(action)
        GlobalBack -> globalBack()
        GlobalHome -> globalHome()
        GlobalRecents -> globalRecents()
        GlobalNotifications -> globalNotifications()
        GlobalQuickSettings -> globalQuickSettings()
        else -> false
    }

    private fun dispatchPointGesture(x: Int, y: Int, durationMs: Long): Boolean {
        if (x < 0 || y < 0) return false
        val service = serviceProvider() ?: return false
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(pointPath(x, y), 0, durationMs))
            .build()
        return service.dispatchGesture(gesture, null, null)
    }

    private fun pointPath(x: Int, y: Int): Path = Path().apply {
        moveTo(x.toFloat(), y.toFloat())
    }

    private fun replaceText(node: AccessibilityNodeInfo, value: String): Boolean {
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
        }
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    private fun findNode(root: AccessibilityNodeInfo, selector: String): AccessibilityNodeInfo? {
        // V3 ephemeral IDs always use exact traversal. Never degrade a stale
        // node ID into fuzzy label matching because that could target a sibling.
        if (selector.startsWith("n:")) return nodeLocator.locate(root, selector)

        if (root.viewIdResourceName == selector) return root
        val wanted = normalize(selector)
        if (wanted.isBlank()) return null
        if (matches(root.text?.toString(), wanted) || matches(root.contentDescription?.toString(), wanted)) {
            return root
        }

        if (selector.contains(":")) {
            try {
                root.findAccessibilityNodeInfosByViewId(selector).firstOrNull()?.let { return it }
            } catch (_: Throwable) {
                // Some OEM accessibility implementations throw on unsupported IDs.
            }
        }

        try {
            root.findAccessibilityNodeInfosByText(selector).firstOrNull { node ->
                matches(node.text?.toString(), wanted) ||
                    matches(node.contentDescription?.toString(), wanted)
            }?.let { return it }
        } catch (_: Throwable) {
            // Fall back to deterministic tree traversal below.
        }

        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findNode(child, selector)
            if (found != null) return found
            child.recycle()
        }
        return null
    }

    private fun normalize(value: String): String =
        value.trim().lowercase().replace(Regex("\\s+"), " ")

    private fun matches(value: String?, wanted: String): Boolean {
        val candidate = value?.let(::normalize) ?: return false
        if (candidate.isBlank() || wanted.isBlank()) return false
        return candidate == wanted || candidate.contains(wanted) || wanted.contains(candidate)
    }

    private fun clickNodeOrParent(start: AccessibilityNodeInfo): Boolean =
        performNodeActionOrParent(start, AccessibilityNodeInfo.ACTION_CLICK) { node -> node.isClickable }

    private fun longClickNodeOrParent(start: AccessibilityNodeInfo): Boolean =
        performNodeActionOrParent(start, AccessibilityNodeInfo.ACTION_LONG_CLICK) { node -> node.isLongClickable }

    private fun performNodeActionOrParent(
        start: AccessibilityNodeInfo,
        action: Int,
        predicate: (AccessibilityNodeInfo) -> Boolean = { true },
    ): Boolean {
        var node: AccessibilityNodeInfo? = start
        repeat(MAX_PARENT_HOPS) {
            val current = node ?: return false
            if (predicate(current) && current.performAction(action)) return true
            node = current.parent
        }
        return false
    }

    private companion object {
        const val MAX_PARENT_HOPS = 6
        const val MIN_GESTURE_MS = 50L
        const val MAX_GESTURE_MS = 3_000L
        const val TAP_DURATION_MS = 60L
        const val MIN_LONG_PRESS_MS = 500L
        const val DOUBLE_TAP_INTERVAL_MS = 140L
        const val MAX_WAIT_MS = 5_000L
    }
}
