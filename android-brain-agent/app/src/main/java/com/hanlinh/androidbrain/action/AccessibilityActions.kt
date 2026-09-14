package com.hanlinh.androidbrain.action

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import com.hanlinh.androidbrain.protocol.ClickNode
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.GlobalHome
import com.hanlinh.androidbrain.protocol.SetText
import com.hanlinh.androidbrain.protocol.Swipe
import com.hanlinh.androidbrain.service.BrainAccessibilityService

class AccessibilityActions(
    private val serviceProvider: () -> BrainAccessibilityService? = { BrainAccessibilityService.current }
) {
    fun click(action: ClickNode): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = findNode(root, action.selector) ?: return false
        return clickNodeOrParent(node)
    }

    fun setText(action: SetText): Boolean {
        val service = serviceProvider() ?: return false
        val root = service.rootInActiveWindow ?: return false
        val node = findNode(root, action.selector) ?: return false
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, action.value)
        }
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    fun globalBack(): Boolean = serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK) == true
    fun globalHome(): Boolean = serviceProvider()?.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME) == true

    fun swipe(action: Swipe): Boolean {
        val service = serviceProvider() ?: return false
        val path = Path().apply {
            moveTo(action.startX.toFloat(), action.startY.toFloat())
            lineTo(action.endX.toFloat(), action.endY.toFloat())
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, action.durationMs.coerceIn(50, 3000)))
            .build()
        return service.dispatchGesture(gesture, null, null)
    }

    fun execute(action: Any): Boolean = when (action) {
        is ClickNode -> click(action)
        is SetText -> setText(action)
        is Swipe -> swipe(action)
        GlobalBack -> globalBack()
        GlobalHome -> globalHome()
        else -> false
    }

    private fun findNode(root: AccessibilityNodeInfo, selector: String): AccessibilityNodeInfo? {
        if (root.viewIdResourceName == selector || root.text?.toString() == selector || root.contentDescription?.toString() == selector) {
            return root
        }
        if (selector.contains(":")) {
            try {
                root.findAccessibilityNodeInfosByViewId(selector).firstOrNull()?.let { return it }
            } catch (_: Throwable) { }
        }
        root.findAccessibilityNodeInfosByText(selector).firstOrNull()?.let { return it }
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findNode(child, selector)
            if (found != null) return found
            child.recycle()
        }
        return null
    }

    private fun clickNodeOrParent(start: AccessibilityNodeInfo): Boolean {
        var node: AccessibilityNodeInfo? = start
        repeat(5) {
            val current = node ?: return false
            if (current.isClickable && current.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
            node = current.parent
        }
        return false
    }
}
