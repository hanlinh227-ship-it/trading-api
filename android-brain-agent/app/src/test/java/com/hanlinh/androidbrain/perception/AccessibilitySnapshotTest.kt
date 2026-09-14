package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AccessibilitySnapshotTest {
    private fun raw(
        text: String? = "Open",
        password: Boolean = false,
        path: String = "0.1",
    ) = RawAccessibilityNode(
        nodePath = path,
        resourceId = "com.example:id/action",
        text = text,
        contentDescription = "Action",
        className = "android.widget.Button",
        enabled = true,
        clickable = true,
        longClickable = true,
        editable = false,
        scrollable = false,
        checkable = false,
        checked = false,
        selected = false,
        focused = false,
        visibleToUser = true,
        isPassword = password,
        bounds = NodeBounds(10, 20, 110, 70),
    )

    @Test fun snapshot_drops_password_node_text() {
        val snapshot = AccessibilitySnapshotMapper().from(
            packageName = "com.example.app",
            windowTitle = "Login",
            rawNodes = listOf(raw(text = "secret", password = true)),
        )

        assertEquals(1, snapshot.nodes.size)
        assertFalse(snapshot.nodes.any { it.text == "secret" })
        assertFalse(snapshot.nodes.any { it.contentDescription == "Action" })
    }

    @Test fun snapshot_preserves_actionability_and_stable_ephemeral_node_id() {
        val mapper = AccessibilitySnapshotMapper()
        val first = mapper.from("com.example.app", "Home", listOf(raw(path = "0.3")))
        val second = mapper.from("com.example.app", "Home", listOf(raw(path = "0.3")))
        val node = first.nodes.single()

        assertEquals("n:0.3", node.nodeId)
        assertEquals(node.nodeId, second.nodes.single().nodeId)
        assertTrue(node.clickable)
        assertTrue(node.longClickable)
        assertTrue(node.enabled)
        assertTrue(node.visibleToUser)
        assertEquals(NodeBounds(10, 20, 110, 70), node.bounds)
    }

    @Test fun semantically_equal_snapshots_have_equal_fingerprints() {
        val mapper = AccessibilitySnapshotMapper()
        val first = mapper.from("com.example.app", "Home", listOf(raw(path = "0.1")))
        val second = mapper.from("com.example.app", "Home", listOf(raw(path = "0.1")))
        val changed = mapper.from("com.example.app", "Home", listOf(raw(text = "Changed", path = "0.1")))

        assertEquals(first.fingerprint(), second.fingerprint())
        assertFalse(first.fingerprint() == changed.fingerprint())
    }
}
