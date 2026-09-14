package com.hanlinh.androidbrain.action

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NodeLocatorTest {
    private data class FakeNode(
        val name: String,
        val children: List<FakeNode> = emptyList(),
    )

    private val tree = FakeNode(
        name = "root",
        children = listOf(
            FakeNode("first"),
            FakeNode(
                "second",
                children = listOf(
                    FakeNode("second-first"),
                    FakeNode("target"),
                ),
            ),
        ),
    )

    @Test fun ephemeral_node_id_resolves_by_exact_traversal_path() {
        val result = NodeLocator().locateByNodeId(tree, "n:0.1.1") { node, index ->
            node.children.getOrNull(index)
        }

        assertEquals("target", result?.name)
    }

    @Test fun lookup_is_independent_of_duplicate_or_missing_text() {
        val duplicateTree = FakeNode(
            "root",
            children = listOf(
                FakeNode("same"),
                FakeNode("same"),
            ),
        )

        val result = NodeLocator().locateByNodeId(duplicateTree, "n:0.1") { node, index ->
            node.children.getOrNull(index)
        }

        assertEquals(duplicateTree.children[1], result)
    }

    @Test fun malformed_or_stale_node_id_fails_closed() {
        val locator = NodeLocator()
        val childAt = { node: FakeNode, index: Int -> node.children.getOrNull(index) }

        assertNull(locator.locateByNodeId(tree, "n:1.0", childAt))
        assertNull(locator.locateByNodeId(tree, "n:0.-1", childAt))
        assertNull(locator.locateByNodeId(tree, "label:Settings", childAt))
        assertNull(locator.locateByNodeId(tree, "n:0.9", childAt))
    }
}
