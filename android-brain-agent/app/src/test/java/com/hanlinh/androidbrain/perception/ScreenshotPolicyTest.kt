package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScreenshotPolicyTest {
    private val policy = ScreenshotPolicy()

    @Test fun api_below_30_is_not_supported() {
        assertFalse(policy.isApiSupported(29))
        assertTrue(policy.isApiSupported(30))
    }

    @Test fun known_sensitive_surfaces_are_denied() {
        assertFalse(policy.mayCapture("com.android.systemui", "Confirm your PIN"))
        assertFalse(policy.mayCapture("com.example.wallet", "Recovery phrase"))
        assertFalse(policy.mayCapture("com.bank.app", "Enter OTP"))
        assertTrue(policy.mayCapture("com.android.mms", "Tin nhắn"))
    }

    @Test fun screenshot_result_never_prints_raw_bytes() {
        val result: ScreenshotCapture = ScreenshotCapture.Captured(
            mimeType = "image/jpeg",
            bytes = byteArrayOf(1, 2, 3, 4),
            width = 100,
            height = 200,
        )
        val rendered = result.toString()
        assertFalse(rendered.contains("1, 2, 3, 4"))
        assertFalse(rendered.contains("bytes="))
        assertTrue(rendered.contains("image/jpeg"))
    }
}
