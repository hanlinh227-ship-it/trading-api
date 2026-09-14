package com.hanlinh.androidbrain.perception

import android.accessibilityservice.AccessibilityService
import android.graphics.Bitmap
import android.os.Build
import android.view.Display
import androidx.annotation.RequiresApi
import java.io.ByteArrayOutputStream

/**
 * Policy guard for screenshot capture. Screenshots are perception inputs only:
 * they must never be captured on obviously credential/secret-bearing surfaces.
 */
class ScreenshotPolicy {
    fun isApiSupported(apiLevel: Int): Boolean = apiLevel >= Build.VERSION_CODES.R

    fun mayCapture(packageName: String?, windowTitle: String?): Boolean {
        val packageValue = packageName.orEmpty().lowercase()
        val titleValue = windowTitle.orEmpty().lowercase()
        val combined = "$packageValue $titleValue"

        if (SENSITIVE_TERMS.any { combined.contains(it) }) return false

        // System UI is allowed for ordinary navigation, but authentication-like
        // system surfaces fail closed even when OEM wording differs slightly.
        if (packageValue == "com.android.systemui" &&
            SYSTEM_AUTH_TERMS.any { titleValue.contains(it) }
        ) {
            return false
        }

        return true
    }

    private companion object {
        val SENSITIVE_TERMS = listOf(
            "password",
            "passwd",
            "passcode",
            "enter pin",
            "confirm your pin",
            "confirm pin",
            "otp",
            "one-time password",
            "one time password",
            "2fa",
            "mfa",
            "verification code",
            "security code",
            "recovery phrase",
            "seed phrase",
            "mnemonic",
            "private key",
            "private_key",
        )

        val SYSTEM_AUTH_TERMS = listOf(
            "unlock",
            "authenticate",
            "authentication",
            "biometric",
            "fingerprint",
            "face unlock",
            "pattern",
        )
    }
}

sealed interface ScreenshotCapture {
    class Captured(
        val mimeType: String,
        val bytes: ByteArray,
        val width: Int,
        val height: Int,
    ) : ScreenshotCapture {
        override fun toString(): String =
            "Captured(mimeType=$mimeType, width=$width, height=$height, byteCount=${bytes.size})"
    }

    data object Unsupported : ScreenshotCapture

    data class Denied(val reason: String = "sensitive_surface") : ScreenshotCapture

    data class Failed(val code: String) : ScreenshotCapture
}

/**
 * Captures an accessibility screenshot on API 30+ and keeps image bytes only in
 * memory. The caller owns the returned byte array and must keep it ephemeral.
 */
class AccessibilityScreenshotProvider(
    private val service: AccessibilityService,
    private val policy: ScreenshotPolicy = ScreenshotPolicy(),
) {
    fun captureScreenshot(callback: (ScreenshotCapture) -> Unit) {
        if (!policy.isApiSupported(Build.VERSION.SDK_INT)) {
            callback(ScreenshotCapture.Unsupported)
            return
        }

        val root = service.rootInActiveWindow
        val packageName = root?.packageName?.toString()
        val windowTitle = root?.window?.title?.toString()
        if (!policy.mayCapture(packageName, windowTitle)) {
            callback(ScreenshotCapture.Denied())
            return
        }

        captureApi30(callback)
    }

    @RequiresApi(Build.VERSION_CODES.R)
    private fun captureApi30(callback: (ScreenshotCapture) -> Unit) {
        try {
            service.takeScreenshot(
                Display.DEFAULT_DISPLAY,
                service.mainExecutor,
                object : AccessibilityService.TakeScreenshotCallback {
                    override fun onSuccess(screenshot: AccessibilityService.ScreenshotResult) {
                        val buffer = screenshot.hardwareBuffer
                        try {
                            val hardwareBitmap = Bitmap.wrapHardwareBuffer(buffer, screenshot.colorSpace)
                                ?: run {
                                    callback(ScreenshotCapture.Failed("hardware_buffer_wrap_failed"))
                                    return
                                }
                            try {
                                val softwareBitmap = hardwareBitmap.copy(Bitmap.Config.ARGB_8888, false)
                                    ?: run {
                                        callback(ScreenshotCapture.Failed("bitmap_copy_failed"))
                                        return
                                    }
                                try {
                                    val bytes = ByteArrayOutputStream().use { output ->
                                        val compressed = softwareBitmap.compress(
                                            Bitmap.CompressFormat.JPEG,
                                            JPEG_QUALITY,
                                            output,
                                        )
                                        if (!compressed) {
                                            callback(ScreenshotCapture.Failed("bitmap_compress_failed"))
                                            return
                                        }
                                        output.toByteArray()
                                    }
                                    callback(
                                        ScreenshotCapture.Captured(
                                            mimeType = JPEG_MIME_TYPE,
                                            bytes = bytes,
                                            width = softwareBitmap.width,
                                            height = softwareBitmap.height,
                                        )
                                    )
                                } finally {
                                    softwareBitmap.recycle()
                                }
                            } finally {
                                hardwareBitmap.recycle()
                            }
                        } catch (error: RuntimeException) {
                            callback(
                                ScreenshotCapture.Failed(
                                    "capture_processing_${error.javaClass.simpleName.lowercase()}"
                                )
                            )
                        } finally {
                            buffer.close()
                        }
                    }

                    override fun onFailure(errorCode: Int) {
                        callback(ScreenshotCapture.Failed("take_screenshot_error_$errorCode"))
                    }
                },
            )
        } catch (error: RuntimeException) {
            callback(
                ScreenshotCapture.Failed(
                    "take_screenshot_${error.javaClass.simpleName.lowercase()}"
                )
            )
        }
    }

    private companion object {
        const val JPEG_QUALITY = 82
        const val JPEG_MIME_TYPE = "image/jpeg"
    }
}
