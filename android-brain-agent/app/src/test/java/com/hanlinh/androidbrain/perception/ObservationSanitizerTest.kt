package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ObservationSanitizerTest {
    private val sanitizer = ObservationSanitizer()

    @Test fun redacts_password_pin_otp_and_recovery_values() {
        assertNull(sanitizer.sanitizeText("hunter2", isPassword = true, resourceId = "password", className = "EditText"))
        assertNull(sanitizer.sanitizeText("123456", isPassword = false, resourceId = "otp_code", className = "EditText"))
        assertNull(sanitizer.sanitizeText("1234", isPassword = false, resourceId = "pin_input", className = "EditText"))
        assertNull(sanitizer.sanitizeText("word1 word2 word3", isPassword = false, resourceId = "recovery_phrase", className = "EditText"))
    }

    @Test fun keeps_ordinary_non_secret_ui_text() {
        assertEquals(
            "Tin nhắn",
            sanitizer.sanitizeText("Tin nhắn", isPassword = false, resourceId = "title", className = "TextView"),
        )
    }
}
