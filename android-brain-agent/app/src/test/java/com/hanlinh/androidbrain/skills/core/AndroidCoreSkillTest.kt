package com.hanlinh.androidbrain.skills.core

import com.hanlinh.androidbrain.action.ShizukuActions
import com.hanlinh.androidbrain.protocol.LaunchApp
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AndroidCoreSkillTest {
    @Test fun shizuku_absence_does_not_break_core_agent() {
        val shizuku = ShizukuActions { false }
        val coreSkill = AndroidCoreSkill()
        assertFalse(shizuku.available())
        assertTrue(coreSkill.canHandle(LaunchApp("com.android.settings")))
    }
}
