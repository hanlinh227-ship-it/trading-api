package com.hanlinh.androidbrain.protocol

import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test

class TypedActionCodecTest {
    @Test fun supported_actions_round_trip_through_deterministic_json() {
        val actions: List<Action> = listOf(
            LaunchApp("com.android.settings"),
            ClickNode("n:0.1"),
            LongClickNode("n:0.2"),
            ReadScreen,
            SetText("n:0.3", "hello"),
            ClearText("n:0.3"),
            GlobalBack,
            GlobalHome,
            GlobalRecents,
            GlobalNotifications,
            GlobalQuickSettings,
            Swipe(10, 20, 30, 40, 500),
            TapPoint(120, 340),
            LongPressPoint(120, 340, 700),
            DoubleTapPoint(120, 340),
            ScrollNode("n:0.4", ScrollDirection.FORWARD),
            Wait(250),
            OpenUrl("https://example.com/path?q=1"),
            SendMessage("+84901234567", "hello"),
            DeleteData(2),
            WalletSign("payload"),
        )

        actions.forEach { action ->
            val encoded = TypedActionCodec.encode(action)
            assertEquals(action, TypedActionCodec.decode(encoded))
            assertEquals(encoded, TypedActionCodec.encode(TypedActionCodec.decode(encoded)))
        }
    }

    @Test fun canonical_tap_json_has_stable_field_order() {
        assertEquals(
            "{\"type\":\"tap_point\",\"x\":120,\"y\":340}",
            TypedActionCodec.encode(TapPoint(120, 340)),
        )
    }

    @Test fun unknown_or_malformed_typed_action_is_rejected() {
        assertRejected("{\"type\":\"launch_app\"}")
        assertRejected("{\"type\":\"totally_unknown\"}")
        assertRejected("{\"type\":\"tap_point\",\"x\":1}")
        assertRejected("not-json")
    }

    private fun assertRejected(raw: String) {
        try {
            TypedActionCodec.decode(raw)
            fail("Expected malformed typed action to be rejected: $raw")
        } catch (_: IllegalArgumentException) {
            // Expected: reject at the codec boundary before envelope verification/dispatch.
        }
    }
}
