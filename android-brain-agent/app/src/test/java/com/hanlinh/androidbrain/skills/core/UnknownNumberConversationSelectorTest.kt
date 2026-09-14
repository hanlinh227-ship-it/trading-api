package com.hanlinh.androidbrain.skills.core

import com.hanlinh.androidbrain.local.ContactMatch
import com.hanlinh.androidbrain.perception.AccessibilityNode
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.perception.NodeBounds
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UnknownNumberConversationSelectorTest {
    private fun node(
        id: String,
        text: String? = null,
        clickable: Boolean = false,
        longClickable: Boolean = false,
    ) = AccessibilityNode(
        nodeId = id,
        resourceId = null,
        text = text,
        contentDescription = null,
        className = "android.view.View",
        enabled = true,
        clickable = clickable,
        longClickable = longClickable,
        editable = false,
        scrollable = false,
        checkable = false,
        checked = false,
        selected = false,
        focused = false,
        visibleToUser = true,
        bounds = NodeBounds(0, 0, 100, 100),
    )

    @Test fun `unknown sender resolves to nearest actionable conversation row`() {
        val classifier = UnknownNumberConversationClassifier { number ->
            if (number.endsWith("4567")) ContactMatch.NotSaved else ContactMatch.Saved
        }
        val selector = UnknownNumberConversationSelector(classifier)
        val snapshot = AccessibilitySnapshot(
            packageName = "com.google.android.apps.messaging",
            windowTitle = "Messages",
            nodes = listOf(
                node("n:0", clickable = false),
                node("n:0.1", clickable = true),
                node("n:0.1.0", text = "090 123 4567"),
                node("n:0.2", clickable = true),
                node("n:0.2.0", text = "Mum"),
            ),
        )

        val result = selector.select(snapshot)
        assertFalse(result.permissionUnavailable)
        assertEquals(
            listOf(UnknownConversationTarget("n:0.1.0", "n:0.1")),
            result.targets,
        )
    }

    @Test fun `saved contacts are never selected`() {
        val selector = UnknownNumberConversationSelector(
            UnknownNumberConversationClassifier { ContactMatch.Saved }
        )
        val snapshot = AccessibilitySnapshot(
            "com.google.android.apps.messaging",
            "Messages",
            listOf(node("n:0", clickable = true), node("n:0.0", text = "+84 90 123 4567")),
        )
        assertTrue(selector.select(snapshot).targets.isEmpty())
    }

    @Test fun `permission uncertainty fails closed for the whole selection`() {
        val selector = UnknownNumberConversationSelector(
            UnknownNumberConversationClassifier { ContactMatch.PermissionUnavailable }
        )
        val snapshot = AccessibilitySnapshot(
            "com.google.android.apps.messaging",
            "Messages",
            listOf(node("n:0", clickable = true), node("n:0.0", text = "0901234567")),
        )
        val result = selector.select(snapshot)
        assertTrue(result.permissionUnavailable)
        assertTrue(result.targets.isEmpty())
    }
}
