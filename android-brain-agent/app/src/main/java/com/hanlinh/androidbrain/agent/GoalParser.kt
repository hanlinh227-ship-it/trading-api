package com.hanlinh.androidbrain.agent

import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.ClickNode
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.GlobalHome
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.LongClickNode
import com.hanlinh.androidbrain.protocol.OpenUrl
import com.hanlinh.androidbrain.protocol.ReadScreen

object GoalParser {
    fun parse(goal: String, resolvePackage: (String) -> String?): Action? {
        val raw = goal.trim()
        if (raw.isBlank()) return null
        val lower = raw.lowercase()

        if (lower in setOf("back", "go back", "quay lại")) return GlobalBack
        if (lower in setOf("home", "go home", "về màn hình chính")) return GlobalHome
        if (lower in setOf("đọc màn hình", "xem màn hình", "read screen", "inspect screen")) return ReadScreen

        parseLongClick(raw)?.let { return it }
        parseClick(raw)?.let { return it }

        Regex("https?://\\S+", RegexOption.IGNORE_CASE).find(raw)?.value?.let { return OpenUrl(it) }

        val isOpenIntent = lower.startsWith("mở ") || lower.startsWith("open ")
        if (isOpenIntent && (lower.contains("cài đặt") || lower.contains("settings"))) {
            return LaunchApp("com.android.settings")
        }

        val appName = extractAppName(raw) ?: return null
        return resolvePackage(appName)?.let { LaunchApp(it) }
    }

    private fun parseLongClick(raw: String): LongClickNode? {
        val prefixes = listOf("Nhấn giữ ", "Giữ ", "Long press ")
        val prefix = prefixes.firstOrNull { raw.startsWith(it, ignoreCase = true) } ?: return null
        return cleanSelector(raw.substring(prefix.length))?.let { LongClickNode(it) }
    }

    private fun parseClick(raw: String): ClickNode? {
        val prefixes = listOf("Bấm ", "Nhấn ", "Tap ", "Click ")
        val prefix = prefixes.firstOrNull { raw.startsWith(it, ignoreCase = true) } ?: return null
        return cleanSelector(raw.substring(prefix.length))?.let { ClickNode(it) }
    }

    private fun cleanSelector(value: String): String? {
        var selector = value.trim()
        val fillers = listOf("nút ", "button ", "vào ")
        for (filler in fillers) {
            if (selector.startsWith(filler, ignoreCase = true)) {
                selector = selector.substring(filler.length).trim()
                break
            }
        }
        return selector.ifBlank { null }
    }

    private fun extractAppName(raw: String): String? {
        val stripped = when {
            raw.startsWith("Mở ứng dụng ", ignoreCase = true) -> raw.substring("Mở ứng dụng ".length)
            raw.startsWith("Mở ", ignoreCase = true) -> raw.substring("Mở ".length)
            raw.startsWith("Open app ", ignoreCase = true) -> raw.substring("Open app ".length)
            raw.startsWith("Open application ", ignoreCase = true) -> raw.substring("Open application ".length)
            raw.startsWith("Open ", ignoreCase = true) -> raw.substring("Open ".length)
            else -> return null
        }.trim()

        val suffixes = listOf(
            " trên điện thoại",
            " trên máy",
            " và không ",
            " và đừng ",
            " and do not ",
            " and don't ",
            " on the phone",
            ",",
        )

        var end = stripped.length
        for (suffix in suffixes) {
            val index = stripped.indexOf(suffix, ignoreCase = true)
            if (index >= 0 && index < end) end = index
        }
        return stripped.substring(0, end).trim().ifBlank { null }
    }
}
