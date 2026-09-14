package com.hanlinh.androidbrain.protocol

import com.hanlinh.androidbrain.policy.RiskClass

/** Stable typed action grammar shared by the cloud policy clamp and Android executor. */
sealed interface Action {
    val type: String
    val riskClass: RiskClass
}

data class LaunchApp(val packageName: String) : Action { override val type = "launch_app"; override val riskClass = RiskClass.A }
data class ClickNode(val selector: String) : Action { override val type = "click_node"; override val riskClass = RiskClass.A }
data class LongClickNode(val selector: String) : Action { override val type = "long_click_node"; override val riskClass = RiskClass.A }
data object ReadScreen : Action { override val type = "read_screen"; override val riskClass = RiskClass.A }
data class SetText(val selector: String, val value: String) : Action { override val type = "set_text"; override val riskClass = RiskClass.B }
data class ReplaceText(val selector: String, val value: String) : Action { override val type = "replace_text"; override val riskClass = RiskClass.B }
data class ClearText(val nodeId: String) : Action { override val type = "clear_text"; override val riskClass = RiskClass.B }
data class ClipboardSet(val value: String) : Action { override val type = "clipboard_set"; override val riskClass = RiskClass.B }
data class ClipboardPaste(val selector: String) : Action { override val type = "clipboard_paste"; override val riskClass = RiskClass.B }
data class SelectText(val selector: String, val start: Int, val end: Int) : Action { override val type = "select_text"; override val riskClass = RiskClass.B }

data object GlobalBack : Action { override val type = "global_back"; override val riskClass = RiskClass.A }
data object GlobalHome : Action { override val type = "global_home"; override val riskClass = RiskClass.A }
data object GlobalRecents : Action { override val type = "global_recents"; override val riskClass = RiskClass.A }
data object GlobalNotifications : Action { override val type = "global_notifications"; override val riskClass = RiskClass.A }
data object GlobalQuickSettings : Action { override val type = "global_quick_settings"; override val riskClass = RiskClass.A }

data class Swipe(val startX: Int, val startY: Int, val endX: Int, val endY: Int, val durationMs: Long = 300) : Action {
    override val type = "swipe"; override val riskClass = RiskClass.A
}
data class Drag(val startX: Int, val startY: Int, val endX: Int, val endY: Int, val durationMs: Long = 500) : Action {
    override val type = "drag"; override val riskClass = RiskClass.A
}
data class GestureStroke(val startX: Int, val startY: Int, val endX: Int, val endY: Int, val durationMs: Long)
data class MultiStrokeGesture(val strokes: List<GestureStroke>) : Action {
    override val type = "multi_stroke_gesture"; override val riskClass = RiskClass.A
    init { require(strokes.isNotEmpty() && strokes.size <= 8) { "strokes must contain 1..8 entries" } }
}
data class TapPoint(val x: Int, val y: Int) : Action { override val type = "tap_point"; override val riskClass = RiskClass.A }
data class LongPressPoint(val x: Int, val y: Int, val durationMs: Long = 600) : Action { override val type = "long_press_point"; override val riskClass = RiskClass.A }
data class DoubleTapPoint(val x: Int, val y: Int) : Action { override val type = "double_tap_point"; override val riskClass = RiskClass.A }

enum class ScrollDirection { FORWARD, BACKWARD }
data class ScrollNode(val nodeId: String, val direction: ScrollDirection) : Action { override val type = "scroll_node"; override val riskClass = RiskClass.A }
data class Wait(val durationMs: Long) : Action { override val type = "wait"; override val riskClass = RiskClass.A }
data class OpenUrl(val url: String) : Action { override val type = "open_url"; override val riskClass = RiskClass.A }

data class SendMessage(val contact: String, val message: String) : Action { override val type = "send_message"; override val riskClass = RiskClass.C }
data class DeleteData(val itemCount: Int) : Action { override val type = "delete_data"; override val riskClass = RiskClass.C }
data class WalletSign(val payload: String) : Action { override val type = "wallet_sign"; override val riskClass = RiskClass.D }
