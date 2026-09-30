package com.hanlinh.androidbrain.perception

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class UnifiedObservationTest {
    @Test
    fun screenSignature_changesWhenSemanticStateChanges() {
        val a = UnifiedObservation.signature("com.example", "screenA", "sem-a", null, 1080, 2400, "PORTRAIT")
        val b = UnifiedObservation.signature("com.example", "screenA", "sem-b", null, 1080, 2400, "PORTRAIT")
        assertNotEquals(a, b)
    }

    @Test
    fun screenSignature_isDeterministicAndNormalizesIdentity() {
        val a = UnifiedObservation.signature("COM.EXAMPLE", " ScreenA ", "sem", "visual", 1080, 2400, "portrait")
        val b = UnifiedObservation.signature("com.example", "screena", "sem", "visual", 1080, 2400, "PORTRAIT")
        assertEquals(a, b)
    }
}
