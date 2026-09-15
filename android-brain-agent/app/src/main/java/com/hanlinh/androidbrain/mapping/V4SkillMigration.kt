package com.hanlinh.androidbrain.mapping

import com.hanlinh.androidbrain.policy.RiskClass

enum class MigrationAuthority { HINT_ONLY }

data class V4SkillRecipe(
    val packageName: String,
    val actionType: String,
    val riskClass: RiskClass,
    val confidence: Double,
    val x: Int? = null,
    val y: Int? = null,
    val semanticAnchor: String? = null,
    val visualAnchor: String? = null,
)

data class V5SkillCandidate(
    val packageName: String,
    val actionType: String,
    val riskClass: RiskClass,
    val confidence: Double,
    val authority: MigrationAuthority,
    val requiresCurrentAuthorization: Boolean,
    val requiresRegrounding: Boolean,
    val semanticAnchor: String?,
    val visualAnchor: String?,
    val legacyCoordinateHint: Pair<Int, Int>?,
)

class V4SkillMigration {
    fun migrate(recipe: V4SkillRecipe): V5SkillCandidate {
        require(recipe.packageName.isNotBlank())
        require(recipe.actionType.isNotBlank())
        require(recipe.confidence in 0.0..1.0)

        val hasSemanticOrVisualAnchor = !recipe.semanticAnchor.isNullOrBlank() || !recipe.visualAnchor.isNullOrBlank()
        val coordinateOnly = recipe.x != null && recipe.y != null && !hasSemanticOrVisualAnchor
        val confidenceCap = when {
            coordinateOnly -> COORDINATE_ONLY_CONFIDENCE_CAP
            hasSemanticOrVisualAnchor -> ANCHORED_HINT_CONFIDENCE_CAP
            else -> UNGROUNDED_HINT_CONFIDENCE_CAP
        }

        return V5SkillCandidate(
            packageName = recipe.packageName,
            actionType = recipe.actionType,
            riskClass = recipe.riskClass,
            confidence = recipe.confidence.coerceAtMost(confidenceCap),
            authority = MigrationAuthority.HINT_ONLY,
            requiresCurrentAuthorization = true,
            requiresRegrounding = true,
            semanticAnchor = recipe.semanticAnchor?.takeIf { it.isNotBlank() },
            visualAnchor = recipe.visualAnchor?.takeIf { it.isNotBlank() },
            legacyCoordinateHint = if (recipe.x != null && recipe.y != null) recipe.x to recipe.y else null,
        )
    }

    private companion object {
        const val COORDINATE_ONLY_CONFIDENCE_CAP = 0.55
        const val ANCHORED_HINT_CONFIDENCE_CAP = 0.72
        const val UNGROUNDED_HINT_CONFIDENCE_CAP = 0.45
    }
}
