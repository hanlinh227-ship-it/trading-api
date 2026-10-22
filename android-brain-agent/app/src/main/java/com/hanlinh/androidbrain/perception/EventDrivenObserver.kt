package com.hanlinh.androidbrain.perception

class EventDrivenObserver(
    private val snapshotProvider: () -> AccessibilitySnapshot?,
    val cache: ObservationCache = ObservationCache(),
    private val debounceMs: Long = 25L,
) {
    @Volatile private var lastEventType: Int? = null
    @Volatile private var lastEventAtMs: Long = 0

    fun onAccessibilityEvent(eventType: Int, nowMs: Long = System.currentTimeMillis()) {
        val duplicateBurst = eventType == lastEventType && nowMs - lastEventAtMs in 0 until debounceMs
        lastEventType = eventType
        lastEventAtMs = nowMs
        if (duplicateBurst) return
        cache.markAccessibilityChanged(eventType)
        refresh(nowMs)
    }

    @Synchronized
    fun refresh(nowMs: Long = System.currentTimeMillis()): UnifiedObservation? {
        val snapshot = snapshotProvider() ?: return cache.latestObservation
        return cache.updateSemantic(snapshot, nowMs)
    }

    /**
     * Waits briefly for an accessibility revision after a dispatched action, then re-observes.
     * The timeout is a safety bound; normal completion remains event-driven rather than a fixed sleep.
     */
    fun awaitSemanticChange(
        afterRevision: Long,
        timeoutMs: Long = 800L,
        pollMs: Long = 20L,
    ): UnifiedObservation? {
        require(timeoutMs >= 0)
        require(pollMs > 0)
        val deadline = System.nanoTime() + timeoutMs * 1_000_000L
        while (cache.semanticRevision <= afterRevision && System.nanoTime() < deadline) {
            try {
                Thread.sleep(pollMs.coerceAtMost(50L))
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                break
            }
        }
        return refresh()
    }

    fun latest(): UnifiedObservation? = cache.latestObservation ?: refresh()

    companion object {
        @Volatile var current: EventDrivenObserver? = null
            private set

        fun install(snapshotProvider: () -> AccessibilitySnapshot?): EventDrivenObserver {
            return EventDrivenObserver(snapshotProvider).also { current = it }
        }

        fun clear(observer: EventDrivenObserver?) {
            if (observer != null && current === observer) current = null
        }
    }
}