package com.hanlinh.androidbrain.perception

import android.view.accessibility.AccessibilityEvent
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ObservationCacheV5Test {
    @Test
    fun contentChange_invalidatesSemanticRevisionWithoutForcingScreenshot() {
        val cache = ObservationCache()
        cache.updateSemantic(snapshot(nodeCount = 20))
        cache.updateVisual("visual")
        val before = cache.semanticRevision
        cache.markAccessibilityChanged(AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED)
        assertTrue(cache.semanticRevision > before)
        assertFalse(cache.visualCaptureRequired)
    }

    @Test
    fun sparseTree_requestsVisualState() {
        val cache = ObservationCache()
        cache.updateSemantic(snapshot(nodeCount = 1))
        assertTrue(cache.shouldCaptureVisual())
    }

    private fun snapshot(nodeCount: Int): AccessibilitySnapshot = AccessibilitySnapshot(
        packageName = "com.example",
        windowTitle = "Example",
        nodes = (0 until nodeCount).map { index ->
            AccessibilityNode(
                nodeId = "n:$index",
                resourceId = "id/$index",
                text = null,
                contentDescription = null,
                className = "android.view.View",
                enabled = true,
                clickable = false,
                longClickable = false,
                editable = false,
                scrollable = false,
                checkable = false,
                checked = false,
                selected = false,
                focused = false,
                visibleToUser = true,
                bounds = NodeBounds(0, 0, 10, 10),
            )
        },
        screenWidth = 1080,
        screenHeight = 2400,
        orientation = "PORTRAIT",
    )
}
