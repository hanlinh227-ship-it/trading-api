package com.hanlinh.androidbrain.action

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.Swipe
import com.hanlinh.androidbrain.service.BrainAccessibilityService

class AccessibilityAppLauncher(
    private val labelProvider: (String) -> String?,
    private val serviceProvider: () -> BrainAccessibilityService? = { BrainAccessibilityService.current },
    private val sleeper: (Long) -> Unit = { Thread.sleep(it) },
) {
    fun launch(action: LaunchApp): Boolean {
        val service = serviceProvider() ?: return false
        val label = labelProvider(action.packageName)?.trim().orEmpty()
        if (label.isBlank()) return false

        if (!openAppDrawer(service)) return false
        safeSleep(450)
        if (clickExactLabel(service, label)) return true

        if (searchAndClick(service, label)) return true

        repeat(MAX_SCROLL_ATTEMPTS) {
            val root = service.rootInActiveWindow ?: return@repeat
            val scrollable = findScrollableNode(root) ?: return@repeat
            if (!scrollable.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)) return@repeat
            safeSleep(300)
            if (clickExactLabel(service, label)) return true
        }

        return false
    }

    private fun openAppDrawer(service: BrainAccessibilityService): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_ACCESSIBILITY_ALL_APPS)
        ) {
            return true
        }

        if (!service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)) return false
        safeSleep(350)
        return openLegacyAppDrawer(service)
    }

    private fun openLegacyAppDrawer(service: BrainAccessibilityService): Boolean {
        val root = service.rootInActiveWindow ?: return false
        val bounds = Rect().also(root::getBoundsInScreen)
        if (bounds.width() <= 0 || bounds.height() <= 0) return false
        val x = bounds.centerX()
        val startY = bounds.bottom - (bounds.height() * 0.12f).toInt()
        val endY = bounds.top + (bounds.height() * 0.32f).toInt()
        return AccessibilityActions(serviceProvider = { service }).swipe(
            Swipe(x, startY, x, endY, 350L),
        )
    }

    private fun searchAndClick(service: BrainAccessibilityService, label: String): Boolean {
        val root = service.rootInActiveWindow ?: return false
        val search = findEditableNode(root) ?: return false
        search.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, label)
        }
        if (!search.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) return false
        safeSleep(450)
        return clickExactLabel(service, label)
    }

    private fun clickExactLabel(service: BrainAccessibilityService, label: String): Boolean {
        val root = service.rootInActiveWindow ?: return false
        val node = findExactLabel(root, normalize(label)) ?: return false
        var current: AccessibilityNodeInfo? = node
        repeat(8) {
            val candidate = current ?: return@repeat
            if (candidate.isEnabled && candidate.isClickable && candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return true
            }
            current = candidate.parent
        }
        return false
    }

    private fun findExactLabel(node: AccessibilityNodeInfo, wanted: String): AccessibilityNodeInfo? {
        if (node.isVisibleToUser && (
                normalize(node.text?.toString()) == wanted ||
                    normalize(node.contentDescription?.toString()) == wanted
            )
        ) return node

        for (index in 0 until node.childCount) {
            val child = node.getChild(index) ?: continue
            val found = findExactLabel(child, wanted)
            if (found != null) return found
        }
        return null
    }

    private fun findEditableNode(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isVisibleToUser && node.isEnabled && node.isEditable) return node
        for (index in 0 until node.childCount) {
            val child = node.getChild(index) ?: continue
            val found = findEditableNode(child)
            if (found != null) return found
        }
        return null
    }

    private fun findScrollableNode(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (node.isVisibleToUser && node.isEnabled && node.isScrollable) return node
        for (index in 0 until node.childCount) {
            val child = node.getChild(index) ?: continue
            val found = findScrollableNode(child)
            if (found != null) return found
        }
        return null
    }

    private fun normalize(value: String?): String =
        value.orEmpty().trim().lowercase().replace(Regex("\\s+"), " ")

    private fun safeSleep(durationMs: Long) {
        try {
            sleeper(durationMs)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }

    companion object {
        private const val MAX_SCROLL_ATTEMPTS = 12
    }
}
