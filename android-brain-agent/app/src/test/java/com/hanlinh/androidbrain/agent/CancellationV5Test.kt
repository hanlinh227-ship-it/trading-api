package com.hanlinh.androidbrain.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CancellationV5Test {
    @Test
    fun cancellation_abortsBeforeNextNonAtomicAction() {
        val engine = UnifiedOperatorEngine(
            initialSession = PersistentOperatorSession(
                taskId = "cancel-task",
                goal = "keep working",
                allowedPackages = setOf("com.example"),
                persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
            )
        )
        engine.requestCancel()
        val decision = engine.nextDecision()
        assertEquals("CANCELLED", decision.code)
        assertTrue(decision.terminal)
    }

    @Test
    fun targetAppExit_terminatesSingleAppPersistentSession() {
        val engine = UnifiedOperatorEngine(
            initialSession = PersistentOperatorSession(
                taskId = "scope-task",
                goal = "stay in game",
                allowedPackages = setOf("com.example.game"),
                persistence = setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
            )
        )
        engine.observePackage("com.android.launcher")
        assertTrue(engine.currentSession().terminal)
        assertEquals("APP_SCOPE_EXIT", engine.nextDecision().code)
    }
}
