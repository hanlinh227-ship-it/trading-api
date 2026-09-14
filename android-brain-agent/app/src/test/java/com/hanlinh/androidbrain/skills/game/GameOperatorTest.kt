package com.hanlinh.androidbrain.skills.game

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GameOperatorTest {
    @Test fun online_profile_defaults_to_assistant_mode() {
        val profile = GameProfile(packageId = "game.example")
        assertFalse(profile.onlineAutomationAllowed)
    }

    @Test fun operator_refuses_autoplay_when_profile_disallows_it() {
        val operator = GameOperator()
        val result = operator.canAutoplay(GameProfile(packageId = "game.example"))
        assertFalse(result)
        assertTrue(operator.assistantMode(GameProfile(packageId = "game.example")))
    }
}
