package com.hanlinh.androidbrain.perception

import android.view.accessibility.AccessibilityEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class EventDrivenObserverTest {
    @Test
    fun duplicateBurst_isDebouncedButDistinctEventRefreshes() {
        var calls = 0
        val observer = EventDrivenObserver(
            snapshotProvider = {
                calls += 1
                AccessibilitySnapshot(
                    packageName = "com.example",
                    windowTitle = null,
                    nodes = emptyList(),
                    screenWidth = 1080,
                    screenHeight = 2400,
                    orientation = "PORTRAIT",
                )
            },
            debounceMs = 25,
        )
        observer.onAccessibilityEvent(AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED, nowMs = 100)
        observer.onAccessibilityEvent(AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED, nowMs = 110)
        observer.onAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_SCROLLED, nowMs = 115)
        assertEquals(2, calls)
        assertNotNull(observer.latest())
    }
}
