package com.hanlinh.androidbrain.perception

interface VisualStateProvider {
    fun requestVisualState(callback: (ScreenshotCapture?) -> Unit)
}
