package com.hanlinh.androidbrain.skills.game

data class GameProfile(
    val packageId: String,
    val supportedScreens: Set<String> = emptySet(),
    val anchors: Set<String> = emptySet(),
    val actions: Set<String> = setOf("tap", "swipe", "hold"),
    val onlineAutomationAllowed: Boolean = false,
)
