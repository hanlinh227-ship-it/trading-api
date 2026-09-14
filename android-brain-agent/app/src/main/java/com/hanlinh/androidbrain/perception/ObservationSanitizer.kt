package com.hanlinh.androidbrain.perception

/**
 * Redacts values that must never leave the device observation layer.
 * This is intentionally conservative: a false-positive redaction is safer than
 * exposing a password, OTP, PIN, recovery phrase, or other credential-like value.
 */
class ObservationSanitizer {
    fun sanitizeText(
        value: String?,
        isPassword: Boolean,
        resourceId: String?,
        className: String?,
    ): String? {
        if (value.isNullOrBlank()) return value
        if (isPassword) return null

        val haystack = listOfNotNull(resourceId, className).joinToString(" ").lowercase()
        if (SENSITIVE_HINTS.any { haystack.contains(it) }) return null
        return value
    }

    private companion object {
        val SENSITIVE_HINTS = listOf(
            "password", "passwd", "passcode", "pin", "otp", "one_time", "onetime",
            "verification_code", "verify_code", "2fa", "mfa", "secret", "recovery",
            "seed_phrase", "mnemonic", "private_key", "privatekey",
        )
    }
}
