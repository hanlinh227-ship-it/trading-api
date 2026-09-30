package com.hanlinh.androidbrain.mapping

import com.hanlinh.androidbrain.protocol.DeleteData
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.OpenUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppExplorerTest {
    @Test
    fun exploration_allowsSafeNavigationOnly() {
        val explorer = AppExplorer()
        assertTrue(explorer.mayExplore(GlobalBack))
        assertFalse(explorer.mayExplore(DeleteData(1)))
        assertFalse(explorer.mayExplore(OpenUrl("https://example.com")))
    }

    @Test
    fun pathfinding_usesVerifiedHighConfidenceEdges() {
        val explorer = AppExplorer()
        val edges = listOf(
            edge("a", "b", 0.9),
            edge("b", "c", 0.9),
            edge("a", "c", 0.2),
        )
        val path = explorer.shortestVerifiedPath(edges, "a", "c")
        assertEquals(listOf("b", "c"), path!!.map { it.toScreenId })
    }

    private fun edge(from: String, to: String, confidence: Double) = TransitionEdge(
        packageName = "com.example",
        fromScreenId = from,
        actionKey = "go-$to",
        toScreenId = to,
        successCount = 1,
        failureCount = 0,
        medianLatencyMs = 50,
        confidence = confidence,
        lastVerifiedAtMs = 1,
    )
}
