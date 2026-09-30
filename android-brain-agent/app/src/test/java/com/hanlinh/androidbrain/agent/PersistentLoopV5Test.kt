package com.hanlinh.androidbrain.agent

import org.junit.Assert.assertFalse
import org.junit.Assert.assertEquals
import org.junit.Test

class PersistentLoopV5Test {
    @Test
    fun untilUserStop_survivesMoreThanOneThousandActions() {
        val engine = UnifiedOperatorEngine(
            initialSession = PersistentOperatorSession(
                taskId = "persistent",
                goal = "keep running",
                allowedPackages = setOf("com.example"),
                persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
            )
        )
        repeat(1_050) { engine.recordVerifiedLocalAction() }
        assertFalse(engine.currentSession().terminal)
        assertEquals(1_050L, engine.verifiedLocalActions())
    }
}
