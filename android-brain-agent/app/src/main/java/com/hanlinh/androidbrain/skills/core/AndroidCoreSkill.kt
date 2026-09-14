package com.hanlinh.androidbrain.skills.core

import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.GlobalHome
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.OpenUrl
import com.hanlinh.androidbrain.protocol.Swipe

class AndroidCoreSkill {
    fun canHandle(action: Action): Boolean = when (action) {
        is LaunchApp, is OpenUrl, is Swipe, GlobalBack, GlobalHome -> true
        else -> false
    }
}
