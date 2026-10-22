package com.hanlinh.androidbrain.mapping

data class ScreenState(
    val screenId: String,
    val packageName: String,
    val activityHint: String? = null,
    val semanticSignature: String,
    val visualSignature: String? = null,
    val landmarkAnchors: Set<String> = emptySet(),
    val lastVerifiedAppVersion: String? = null,
    val confidence: Double,
    val firstSeenAtMs: Long,
    val lastVerifiedAtMs: Long,
) {
    init {
        require(screenId.isNotBlank())
        require(packageName.isNotBlank())
        require(semanticSignature.isNotBlank())
        require(confidence in 0.0..1.0)
    }
}

class ScreenGraph {
    private val screens = linkedMapOf<String, ScreenState>()

    @Synchronized fun put(state: ScreenState) { screens[state.screenId] = state }
    @Synchronized fun get(screenId: String): ScreenState? = screens[screenId]
    @Synchronized fun all(): List<ScreenState> = screens.values.toList()
    @Synchronized fun remove(screenId: String) { screens.remove(screenId) }
}
