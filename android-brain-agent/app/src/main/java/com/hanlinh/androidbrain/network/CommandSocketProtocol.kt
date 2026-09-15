package com.hanlinh.androidbrain.network

import java.net.URLEncoder
import org.json.JSONObject

sealed interface CommandSocketEvent {
    data object CommandAvailable : CommandSocketEvent
    data class TaskCancelled(val taskId: String) : CommandSocketEvent
}

object CommandSocketProtocol {
    fun socketUrl(baseUrl: String, deviceId: String): String {
        val trimmed = baseUrl.trimEnd('/')
        val wsBase = when {
            trimmed.startsWith("https://", ignoreCase = true) -> "wss://${trimmed.substring(8)}"
            trimmed.startsWith("http://", ignoreCase = true) -> "ws://${trimmed.substring(7)}"
            else -> trimmed
        }
        val encodedDeviceId = URLEncoder.encode(deviceId, Charsets.UTF_8.name()).replace("+", "%20")
        return "$wsBase/v1/device/$encodedDeviceId/socket"
    }

    fun parseEvent(message: String): CommandSocketEvent? {
        val text = message.trim()
        if (!text.startsWith("{") || !text.endsWith("}")) return null
        return runCatching {
            val json = JSONObject(text)
            when (json.optString("type")) {
                "command_available" -> CommandSocketEvent.CommandAvailable
                "task_cancelled" -> json.optString("taskId")
                    .trim()
                    .takeIf { it.isNotEmpty() && it.length <= 128 }
                    ?.let(CommandSocketEvent::TaskCancelled)
                else -> null
            }
        }.getOrNull()
    }

    fun isCommandAvailable(message: String): Boolean =
        parseEvent(message) is CommandSocketEvent.CommandAvailable
}
