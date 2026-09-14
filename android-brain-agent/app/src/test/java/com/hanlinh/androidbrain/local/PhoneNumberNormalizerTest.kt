package com.hanlinh.androidbrain.local

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhoneNumberNormalizerTest {
    @Test fun vietnamese_local_mobile_number_becomes_e164() {
        assertEquals("+84901234567", PhoneNumberNormalizer.normalize("0901234567"))
    }

    @Test fun vietnamese_plus84_number_is_preserved_after_separator_cleanup() {
        assertEquals("+84901234567", PhoneNumberNormalizer.normalize("+84 90-123-4567"))
        assertEquals("+84901234567", PhoneNumberNormalizer.normalize("(+84) 90 123 4567"))
    }

    @Test fun separators_in_local_number_are_accepted() {
        assertEquals("+84901234567", PhoneNumberNormalizer.normalize("090 123 45 67"))
        assertEquals("+84901234567", PhoneNumberNormalizer.normalize("090.123.4567"))
    }

    @Test fun international_e164_like_number_is_kept() {
        assertEquals("+14155552671", PhoneNumberNormalizer.normalize("+1 (415) 555-2671"))
    }

    @Test fun service_ids_names_and_ambiguous_short_values_are_rejected() {
        assertNull(PhoneNumberNormalizer.normalize("Viettel"))
        assertNull(PhoneNumberNormalizer.normalize("VM-BANK"))
        assertNull(PhoneNumberNormalizer.normalize("1900"))
    }

    @Test fun unsupported_country_local_number_fails_closed() {
        assertNull(PhoneNumberNormalizer.normalize("0901234567", defaultCountry = "US"))
    }
}
