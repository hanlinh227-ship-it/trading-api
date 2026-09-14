package com.hanlinh.androidbrain.protocol

import com.hanlinh.androidbrain.policy.RiskClass
import org.junit.Assert.assertEquals
import org.junit.Test

class TypedActionTest {
    @Test fun navigation_and_observation_actions_are_class_a_with_stable_types() {
        val actions = listOf(
            TapPoint(10, 20) to "tap_point",
            LongPressPoint(10, 20) to "long_press_point",
            DoubleTapPoint(10, 20) to "double_tap_point",
            ScrollNode("n:0.1", ScrollDirection.FORWARD) to "scroll_node",
            Wait(250) to "wait",
            GlobalBack to "global_back",
            GlobalHome to "global_home",
            GlobalRecents to "global_recents",
            GlobalNotifications to "global_notifications",
            GlobalQuickSettings to "global_quick_settings",
            ReadScreen to "read_screen",
        )

        actions.forEach { (action, expectedType) ->
            assertEquals(expectedType, action.type)
            assertEquals(RiskClass.A, action.riskClass)
        }
    }

    @Test fun text_mutation_actions_are_class_b() {
        val setText = SetText("n:0.2", "hello")
        val clearText = ClearText("n:0.2")

        assertEquals("set_text", setText.type)
        assertEquals(RiskClass.B, setText.riskClass)
        assertEquals("clear_text", clearText.type)
        assertEquals(RiskClass.B, clearText.riskClass)
    }

    @Test fun destructive_or_security_actions_are_never_downgraded() {
        assertEquals(RiskClass.C, SendMessage("contact", "hello").riskClass)
        assertEquals(RiskClass.C, DeleteData(1).riskClass)
        assertEquals(RiskClass.D, WalletSign("payload").riskClass)
    }
}
