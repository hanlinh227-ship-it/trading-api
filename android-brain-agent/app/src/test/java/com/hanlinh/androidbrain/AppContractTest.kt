package com.hanlinh.androidbrain

import org.junit.Assert.assertEquals
import org.junit.Test

class AppContractTest {
    @Test
    fun package_contract_is_stable() {
        assertEquals("com.hanlinh.androidbrain", BuildConfig.APPLICATION_ID)
    }
}
