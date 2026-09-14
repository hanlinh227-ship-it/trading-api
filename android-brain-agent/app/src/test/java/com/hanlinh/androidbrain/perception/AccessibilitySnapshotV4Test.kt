package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class AccessibilitySnapshotV4Test {
    @Test
    fun `V4 observation carries display and transient visual metadata into fingerprint`() {
        val first = AccessibilitySnapshot(
            packageName = "com.example",
            windowTitle = "Canvas",
            nodes = emptyList(),
            screenWidth = 1080,
            screenHeight = 2400,
            orientation = "PORTRAIT",
            screenshotHash = "frame-a",
            regionHashes = mapOf("center" to "region-a"),
        )
        val second = first.copy(screenshotHash = "frame-b")

        assertEquals(1080, first.screenWidth)
        assertEquals(2400, first.screenHeight)
        assertEquals("PORTRAIT", first.orientation)
        assertEquals("region-a", first.regionHashes["center"])
        assertNotEquals(first.fingerprint(), second.fingerprint())
    }

    @Test
    fun `mapper accepts display metadata without weakening node sanitization`() {
        val snapshot = AccessibilitySnapshotMapper().from(
            packageName = "com.example",
            windowTitle = "Login",
            rawNodes = emptyList(),
            screenWidth = 1440,
            screenHeight = 3120,
            orientation = "PORTRAIT",
        )
        assertEquals(1440, snapshot.screenWidth)
        assertEquals(3120, snapshot.screenHeight)
    }
}
