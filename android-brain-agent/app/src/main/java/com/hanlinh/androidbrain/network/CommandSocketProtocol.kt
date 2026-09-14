package com.hanlinh.androidbrain.network

import java.net.URLEncoder

object CommandSocketProtocol {
    private val commandAvailableType = Regex("\\\"type\\\"\\s*:\\s*\\\"command_available\\\"")

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

    fun isCommandAvailable(message: String): Boolean {
        val text = message.trim()
        return text.startsWith("{") && text.endsWith("}") && commandAvailableType.containsMatchIn(text)
    }
}
