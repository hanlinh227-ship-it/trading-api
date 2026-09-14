package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class VisionSessionTest {
    @Test fun capture_without_projection_requires_consent() {
        val session = VisionSession()
        assertNull(session.captureFrame())
        assertEquals(VisionSessionState.ConsentRequired, session.state)
    }
}
