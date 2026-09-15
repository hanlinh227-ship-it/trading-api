package com.hanlinh.androidbrain.perception

import android.view.accessibility.AccessibilityEvent

class ObservationCache(
    private val sparseNodeThreshold: Int = 2,
) {
    @Volatile var semanticRevision: Long = 0
        private set
    @Volatile var visualRevision: Long = 0
        private set
    @Volatile var visualCaptureRequired: Boolean = false
        private set
    @Volatile var latestSnapshot: AccessibilitySnapshot? = null
        private set
    @Volatile var latestObservation: UnifiedObservation? = null
        private set

    @Synchronized
    fun updateSemantic(snapshot: AccessibilitySnapshot, timestampMs: Long = System.currentTimeMillis()): UnifiedObservation {
        latestSnapshot = snapshot
        val width = snapshot.screenWidth ?: 1
        val height = snapshot.screenHeight ?: 1
        val orientation = snapshot.orientation ?: "UNDEFINED"
        val observation = UnifiedObservation(
            timestampMs = timestampMs,
            packageName = snapshot.packageName,
            windowTitle = snapshot.windowTitle,
            orientation = orientation,
            screenWidth = width.coerceAtLeast(1),
            screenHeight = height.coerceAtLeast(1),
            semanticFingerprint = snapshot.fingerprint(),
            screenshotHash = snapshot.screenshotHash,
            perceptualHash = snapshot.screenshotHash,
            semanticNodeCount = snapshot.nodes.size,
        )
        latestObservation = observation
        if (snapshot.nodes.size <= sparseNodeThreshold) visualCaptureRequired = true
        return observation
    }

    @Synchronized
    fun updateVisual(hash: String?, timestampMs: Long = System.currentTimeMillis()) {
        if (hash.isNullOrBlank()) return
        val current = latestObservation ?: return
        visualRevision += 1
        visualCaptureRequired = false
        latestObservation = current.copy(
            timestampMs = timestampMs,
            screenshotHash = hash,
            perceptualHash = hash,
            screenSignature = UnifiedObservation.signature(
                current.packageName,
                current.activityHint,
                current.semanticFingerprint,
                hash,
                current.screenWidth,
                current.screenHeight,
                current.orientation,
            ),
        )
    }

    @Synchronized
    fun markAccessibilityChanged(eventType: Int) {
        if (eventType in REVISION_EVENTS) semanticRevision += 1
    }

    @Synchronized
    fun requestVisualCapture() {
        visualCaptureRequired = true
    }

    @Synchronized
    fun markEvidenceConflict() {
        visualCaptureRequired = true
    }

    fun shouldCaptureVisual(): Boolean = visualCaptureRequired || (latestSnapshot?.nodes?.size ?: Int.MAX_VALUE) <= sparseNodeThreshold

    companion object {
        private val REVISION_EVENTS = setOf(
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOWS_CHANGED,
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_SCROLLED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_CLICKED,
        )
    }
}
