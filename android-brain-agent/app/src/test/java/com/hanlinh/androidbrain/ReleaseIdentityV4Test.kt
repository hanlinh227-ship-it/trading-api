package com.hanlinh.androidbrain

import org.junit.Assert.assertEquals
import org.junit.Test

class ReleaseIdentityV4Test {
    @Test
    fun `V4 release identity is version 13 0_4_0`() {
        assertEquals(13, BuildConfig.VERSION_CODE)
        assertEquals("0.4.0", BuildConfig.VERSION_NAME)
    }
}
