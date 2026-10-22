package com.hanlinh.androidbrain.perception

import java.security.MessageDigest

data class UnifiedObservation(
    val timestampMs: Long,
    val packageName: String,
    val appVersionHint: String? = null,
    val activityHint: String? = null,
    val windowTitle: String? = null,
    val orientation: String,
    val screenWidth: Int,
    val screenHeight: Int,
    val semanticFingerprint: String,
    val screenshotHash: String? = null,
    val perceptualHash: String? = null,
    val semanticNodeCount: Int = 0,
    val skillSpecificState: String? = null,
    val screenSignature: String = signature(
        packageName = packageName,
        activityHint = activityHint,
        semanticFingerprint = semanticFingerprint,
        visualFingerprint = perceptualHash ?: screenshotHash,
        screenWidth = screenWidth,
        screenHeight = screenHeight,
        orientation = orientation,
    ),
) {
    init {
        require(timestampMs >= 0)
        require(packageName.isNotBlank())
        require(screenWidth > 0)
        require(screenHeight > 0)
        require(semanticNodeCount >= 0)
    }

    companion object {
        fun signature(
            packageName: String,
            activityHint: String?,
            semanticFingerprint: String,
            visualFingerprint: String?,
            screenWidth: Int,
            screenHeight: Int,
            orientation: String,
        ): String {
            val normalized = listOf(
                packageName.trim().lowercase(),
                activityHint.orEmpty().trim().lowercase(),
                semanticFingerprint.trim(),
                visualFingerprint.orEmpty().trim(),
                screenWidth.toString(),
                screenHeight.toString(),
                orientation.trim().uppercase(),
            ).joinToString("|")
            return MessageDigest.getInstance("SHA-256")
                .digest(normalized.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
        }
    }
}
