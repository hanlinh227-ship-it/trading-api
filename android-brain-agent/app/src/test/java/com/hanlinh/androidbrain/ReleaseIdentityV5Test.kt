package com.hanlinh.androidbrain

import org.junit.Assert.assertEquals
import org.junit.Test

class ReleaseIdentityV5Test {
    @Test
    fun releaseIdentity_isV5() {
        assertEquals("0.5.0", BuildConfig.VERSION_NAME)
        assertEquals(14, BuildConfig.VERSION_CODE)
    }
}
