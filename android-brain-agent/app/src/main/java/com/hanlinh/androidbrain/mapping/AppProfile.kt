package com.hanlinh.androidbrain.mapping

data class AppProfile(
    val packageName: String,
    val labels: Set<String> = emptySet(),
    val versionHints: Set<String> = emptySet(),
    val firstSeenAtMs: Long,
    val lastSeenAtMs: Long,
    val confidence: Double,
) {
    init {
        require(packageName.isNotBlank())
        require(firstSeenAtMs >= 0)
        require(lastSeenAtMs >= firstSeenAtMs)
        require(confidence in 0.0..1.0)
    }
}
