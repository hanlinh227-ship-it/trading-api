package com.hanlinh.androidbrain.mapping

import com.hanlinh.androidbrain.policy.RiskClass
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class V4SkillMigrationTest {
    @Test
    fun oldCoordinateRecipe_neverBecomesTrustedTransition() {
        val candidate = V4SkillMigration().migrate(
            V4SkillRecipe(
                packageName = "com.example",
                actionType = "tap_point",
                riskClass = RiskClass.A,
                confidence = 1.0,
                x = 400,
                y = 800,
            )
        )
        assertTrue(candidate.confidence < 0.8)
        assertTrue(candidate.requiresRegrounding)
        assertEquals(MigrationAuthority.HINT_ONLY, candidate.authority)
        assertTrue(candidate.requiresCurrentAuthorization)
    }

    @Test
    fun highRiskV4Hint_doesNotDowngradeRisk() {
        val candidate = V4SkillMigration().migrate(
            V4SkillRecipe(
                packageName = "com.example",
                actionType = "delete_data",
                riskClass = RiskClass.C,
                confidence = 1.0,
            )
        )
        assertEquals(RiskClass.C, candidate.riskClass)
        assertTrue(candidate.requiresCurrentAuthorization)
        assertTrue(candidate.requiresRegrounding)
    }
}
