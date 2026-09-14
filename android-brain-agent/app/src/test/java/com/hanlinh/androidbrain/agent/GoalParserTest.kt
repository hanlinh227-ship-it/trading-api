package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.protocol.ClickNode
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.LongClickNode
import com.hanlinh.androidbrain.protocol.ReadScreen
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class GoalParserTest {
    @Test
    fun `natural Vietnamese settings command resolves to settings package`() {
        val action = GoalParser.parse(
            "Mở ứng dụng Cài đặt trên điện thoại và không thay đổi bất kỳ cài đặt nào",
            resolvePackage = { null },
        )

        assertTrue(action is LaunchApp)
        assertEquals("com.android.settings", (action as LaunchApp).packageName)
    }

    @Test
    fun `natural Vietnamese open app command strips filler suffix`() {
        var requestedLabel: String? = null
        val action = GoalParser.parse(
            "Mở ứng dụng Chrome trên điện thoại và không thay đổi gì khác",
            resolvePackage = { label ->
                requestedLabel = label
                if (label.equals("Chrome", ignoreCase = true)) "com.android.chrome" else null
            },
        )

        assertEquals("Chrome", requestedLabel)
        assertEquals("com.android.chrome", (action as LaunchApp).packageName)
    }

    @Test
    fun `read screen command maps to read screen action`() {
        assertEquals(ReadScreen, GoalParser.parse("Đọc màn hình") { null })
    }

    @Test
    fun `tap text command maps to click node`() {
        assertEquals(ClickNode("Spam & blocked"), GoalParser.parse("Bấm Spam & blocked") { null })
    }

    @Test
    fun `long press text command maps to long click node`() {
        assertEquals(LongClickNode("Spam & blocked"), GoalParser.parse("Giữ Spam & blocked") { null })
    }
}
