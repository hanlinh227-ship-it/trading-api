package com.hanlinh.androidbrain.local

/** Conservative phone-number normalization for local on-device contact matching. */
object PhoneNumberNormalizer {
    fun normalize(raw: String, defaultCountry: String = "VN"): String? {
        val value = raw.trim()
        if (value.isBlank()) return null
        if (!ALLOWED.matches(value)) return null

        val digits = value.filter(Char::isDigit)
        if ('+' in value) {
            if (value.count { it == '+' } != 1) return null
            if (digits.length !in 8..15) return null
            return "+$digits"
        }

        if (defaultCountry.equals("VN", ignoreCase = true) &&
            digits.length == 10 && digits.startsWith('0')
        ) {
            return "+84${digits.drop(1)}"
        }

        return null
    }

    private val ALLOWED = Regex("^[+() .\\-0-9]+$")
}
