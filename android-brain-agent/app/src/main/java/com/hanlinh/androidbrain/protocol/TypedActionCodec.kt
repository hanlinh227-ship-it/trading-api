package com.hanlinh.androidbrain.protocol

import org.json.JSONObject

/** Deterministic schema-2 JSON codec for typed Android actions. */
object TypedActionCodec {
    private data class RawJson(val value: String)

    fun encode(action: Action): String = when (action) {
        is LaunchApp -> obj("type" to action.type, "packageName" to action.packageName)
        is ClickNode -> obj("type" to action.type, "selector" to action.selector)
        is LongClickNode -> obj("type" to action.type, "selector" to action.selector)
        ReadScreen -> obj("type" to action.type)
        is SetText -> obj("type" to action.type, "selector" to action.selector, "value" to action.value)
        is ReplaceText -> obj("type" to action.type, "selector" to action.selector, "value" to action.value)
        is ClearText -> obj("type" to action.type, "nodeId" to action.nodeId)
        is ClipboardSet -> obj("type" to action.type, "value" to action.value)
        is ClipboardPaste -> obj("type" to action.type, "selector" to action.selector)
        is SelectText -> obj("type" to action.type, "selector" to action.selector, "start" to action.start, "end" to action.end)
        GlobalBack -> obj("type" to action.type)
        GlobalHome -> obj("type" to action.type)
        GlobalRecents -> obj("type" to action.type)
        GlobalNotifications -> obj("type" to action.type)
        GlobalQuickSettings -> obj("type" to action.type)
        is Swipe -> gestureObj(action.type, action.startX, action.startY, action.endX, action.endY, action.durationMs)
        is Drag -> gestureObj(action.type, action.startX, action.startY, action.endX, action.endY, action.durationMs)
        is MultiStrokeGesture -> obj(
            "type" to action.type,
            "strokes" to RawJson(action.strokes.joinToString(prefix = "[", postfix = "]") { stroke ->
                gestureObj(null, stroke.startX, stroke.startY, stroke.endX, stroke.endY, stroke.durationMs)
            }),
        )
        is TapPoint -> obj("type" to action.type, "x" to action.x, "y" to action.y)
        is LongPressPoint -> obj("type" to action.type, "x" to action.x, "y" to action.y, "durationMs" to action.durationMs)
        is DoubleTapPoint -> obj("type" to action.type, "x" to action.x, "y" to action.y)
        is ScrollNode -> obj("type" to action.type, "nodeId" to action.nodeId, "direction" to action.direction.name)
        is Wait -> obj("type" to action.type, "durationMs" to action.durationMs)
        is OpenUrl -> obj("type" to action.type, "url" to action.url)
        is SendMessage -> obj("type" to action.type, "contact" to action.contact, "message" to action.message)
        is DeleteData -> obj("type" to action.type, "itemCount" to action.itemCount)
        is WalletSign -> obj("type" to action.type, "payload" to action.payload)
    }

    fun decode(raw: String): Action {
        val json = try { JSONObject(raw) } catch (error: Exception) {
            throw IllegalArgumentException("Invalid typed action JSON", error)
        }
        return try {
            when (json.getString("type")) {
                "launch_app" -> LaunchApp(json.requiredString("packageName"))
                "click_node" -> ClickNode(json.requiredString("selector"))
                "long_click_node" -> LongClickNode(json.requiredString("selector"))
                "read_screen" -> ReadScreen
                "set_text" -> SetText(json.requiredString("selector"), json.getString("value"))
                "replace_text" -> ReplaceText(json.requiredString("selector"), json.getString("value"))
                "clear_text" -> ClearText(json.requiredString("nodeId"))
                "clipboard_set" -> ClipboardSet(json.getString("value"))
                "clipboard_paste" -> ClipboardPaste(json.requiredString("selector"))
                "select_text" -> SelectText(json.requiredString("selector"), json.getInt("start"), json.getInt("end")).also {
                    require(it.start >= 0 && it.end >= it.start) { "invalid selection" }
                }
                "global_back" -> GlobalBack
                "global_home" -> GlobalHome
                "global_recents" -> GlobalRecents
                "global_notifications" -> GlobalNotifications
                "global_quick_settings" -> GlobalQuickSettings
                "swipe" -> Swipe(json.getInt("startX"), json.getInt("startY"), json.getInt("endX"), json.getInt("endY"), json.getLong("durationMs"))
                "drag" -> Drag(json.getInt("startX"), json.getInt("startY"), json.getInt("endX"), json.getInt("endY"), json.getLong("durationMs"))
                "multi_stroke_gesture" -> {
                    val array = json.getJSONArray("strokes")
                    require(array.length() in 1..8) { "strokes must contain 1..8 entries" }
                    val strokes = (0 until array.length()).map { index ->
                        val stroke = array.getJSONObject(index)
                        GestureStroke(
                            stroke.getInt("startX"), stroke.getInt("startY"),
                            stroke.getInt("endX"), stroke.getInt("endY"), stroke.getLong("durationMs"),
                        ).also { require(it.durationMs in 50L..5_000L) { "invalid stroke duration" } }
                    }
                    MultiStrokeGesture(strokes)
                }
                "tap_point" -> TapPoint(json.getInt("x"), json.getInt("y"))
                "long_press_point" -> LongPressPoint(json.getInt("x"), json.getInt("y"), json.getLong("durationMs"))
                "double_tap_point" -> DoubleTapPoint(json.getInt("x"), json.getInt("y"))
                "scroll_node" -> ScrollNode(json.requiredString("nodeId"), ScrollDirection.valueOf(json.requiredString("direction")))
                "wait" -> Wait(json.getLong("durationMs"))
                "open_url" -> OpenUrl(json.requiredString("url"))
                "send_message" -> SendMessage(json.requiredString("contact"), json.getString("message"))
                "delete_data" -> DeleteData(json.getInt("itemCount"))
                "wallet_sign" -> WalletSign(json.requiredString("payload"))
                else -> throw IllegalArgumentException("Unknown typed action")
            }
        } catch (error: IllegalArgumentException) {
            throw error
        } catch (error: Exception) {
            throw IllegalArgumentException("Malformed typed action", error)
        }
    }

    private fun gestureObj(type: String?, startX: Int, startY: Int, endX: Int, endY: Int, durationMs: Long): String {
        val fields = mutableListOf<Pair<String, Any?>>()
        if (type != null) fields += "type" to type
        fields += listOf("startX" to startX, "startY" to startY, "endX" to endX, "endY" to endY, "durationMs" to durationMs)
        return obj(*fields.toTypedArray())
    }

    private fun JSONObject.requiredString(name: String): String =
        getString(name).also { require(it.isNotBlank()) { "$name must not be blank" } }

    private fun obj(vararg fields: Pair<String, Any?>): String = buildString {
        append('{')
        fields.forEachIndexed { index, (key, value) ->
            if (index > 0) append(',')
            append(JSONObject.quote(key)).append(':')
            when (value) {
                null -> append("null")
                is RawJson -> append(value.value)
                is String -> append(JSONObject.quote(value))
                is Boolean, is Number -> append(value.toString())
                else -> append(JSONObject.quote(value.toString()))
            }
        }
        append('}')
    }
}
