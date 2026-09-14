package com.hanlinh.androidbrain.security

import org.junit.Assert.assertEquals
import org.junit.Test

class DeviceIdentityTest {
    @Test fun keystore_alias_is_stable() {
        assertEquals("android_brain_device_identity_v1", DeviceIdentity.KEY_ALIAS)
    }
}
