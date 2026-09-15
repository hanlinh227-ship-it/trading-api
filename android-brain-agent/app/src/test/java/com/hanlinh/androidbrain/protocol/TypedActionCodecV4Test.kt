package com.hanlinh.androidbrain.protocol

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TypedActionCodecV4Test {
    @Test
    fun `V4 actions round trip through schema two codec`() {
        val actions = listOf<Action>(
            Drag(1, 2, 30, 40, 500),
            MultiStrokeGesture(listOf(GestureStroke(1, 2, 30, 40, 300), GestureStroke(10, 20, 50, 80, 350))),
            ReplaceText("n:0.1", "hello"),
            ClipboardSet("hello"),
            ClipboardPaste("n:0.1"),
            SelectText("n:0.1", 1, 4),
        )
        actions.forEach { action ->
            assertEquals(action, TypedActionCodec.decode(TypedActionCodec.encode(action)))
        }
    }

    @Test
    fun `V4 action risks remain bounded`() {
        assertEquals("A", Drag(0, 0, 10, 10, 100).riskClass.name)
        assertEquals("B", ReplaceText("n:0", "x").riskClass.name)
        assertEquals("B", ClipboardSet("x").riskClass.name)
        assertTrue(MultiStrokeGesture(listOf(GestureStroke(0, 0, 1, 1, 100))).strokes.isNotEmpty())
    }
}
