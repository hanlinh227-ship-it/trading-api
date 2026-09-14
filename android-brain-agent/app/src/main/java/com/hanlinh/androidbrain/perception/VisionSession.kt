package com.hanlinh.androidbrain.perception

enum class VisionSessionState { Idle, ConsentRequired, Active, Stopped }

data class Frame(val width: Int, val height: Int, val rgba: ByteArray)

class VisionSession {
    var state: VisionSessionState = VisionSessionState.Idle
        private set

    private var frameProvider: (() -> Frame?)? = null

    fun requireConsent() {
        if (state != VisionSessionState.Active) state = VisionSessionState.ConsentRequired
    }

    fun activate(provider: () -> Frame?) {
        frameProvider = provider
        state = VisionSessionState.Active
    }

    fun captureFrame(): Frame? {
        if (state != VisionSessionState.Active) {
            state = VisionSessionState.ConsentRequired
            return null
        }
        return frameProvider?.invoke()
    }

    fun stop() {
        frameProvider = null
        state = VisionSessionState.Stopped
    }
}
