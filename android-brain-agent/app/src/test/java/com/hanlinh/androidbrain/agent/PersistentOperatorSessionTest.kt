package com.hanlinh.androidbrain.agent

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PersistentOperatorSessionTest {
    @Test
    fun untilUserStop_doesNotExpireFromStepCount() {
        val session = PersistentOperatorSession(
            taskId = "t1",
            goal = "play until I stop",
            allowedPackages = setOf("com.example.game"),
            persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
        )
        assertFalse(session.shouldStop("com.example.game", userCancelled = false, hardSafetyBlock = false))
    }

    @Test
    fun appScopeExit_stopsSingleAppSession() {
        val session = PersistentOperatorSession(
            taskId = "t1",
            goal = "play until I stop",
            allowedPackages = setOf("com.example.game"),
            persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
        )
        assertTrue(session.shouldStop("com.android.launcher", userCancelled = false, hardSafetyBlock = false))
    }

    @Test
    fun userCancelAlwaysStops() {
        val session = PersistentOperatorSession(
            taskId = "t1",
            goal = "keep going",
            allowedPackages = setOf("com.example"),
            persistence = setOf(PersistencePolicy.UNTIL_USER_STOP),
        )
        assertTrue(session.shouldStop("com.example", userCancelled = true, hardSafetyBlock = false))
    }
}
