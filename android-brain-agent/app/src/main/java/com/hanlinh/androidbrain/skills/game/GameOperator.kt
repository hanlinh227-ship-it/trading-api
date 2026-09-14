package com.hanlinh.androidbrain.skills.game

class GameOperator {
    fun canAutoplay(profile: GameProfile): Boolean = profile.onlineAutomationAllowed
    fun assistantMode(profile: GameProfile): Boolean = !profile.onlineAutomationAllowed
}
