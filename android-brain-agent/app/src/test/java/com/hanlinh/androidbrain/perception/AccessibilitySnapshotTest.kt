package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AccessibilitySnapshotTest {
    @Test fun snapshot_drops_password_node_text() {
        val mapper = AccessibilitySnapshotMapper()
        val snapshot = mapper.from(
            packageName = "com.example.app",
            windowTitle = "Login",
            rawNodes = listOf(
                RawAccessibilityNode(
                    resourceId = "password",
                    text = "secret",
                    contentDescription = null,
                    className = "android.widget.EditText",
                    enabled = true,
                    clickable = false,
                    isPassword = true,
                    bounds = NodeBounds(0, 0, 100, 40)
                )
            )
        )
        assertTrue(snapshot.nodes.size == 1)
        assertFalse(snapshot.nodes.any { it.text == "secret" })
    }
}
