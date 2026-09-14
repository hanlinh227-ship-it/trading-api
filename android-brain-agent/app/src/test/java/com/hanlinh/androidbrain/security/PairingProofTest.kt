package com.hanlinh.androidbrain.security

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec

class PairingProofTest {
    @Test
    fun canonicalPayloadIsStable() {
        assertEquals(
            "android-brain-pair-v2\ndevice-1\nchallenge-1",
            PairingProof.payload("device-1", "challenge-1").toString(Charsets.UTF_8),
        )
    }

    @Test
    fun derSignatureRoundTripsThroughP1363() {
        val generator = KeyPairGenerator.getInstance("EC")
        generator.initialize(ECGenParameterSpec("secp256r1"))
        val pair = generator.generateKeyPair()
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(pair.private)
        signer.update(PairingProof.payload("device-1", "challenge-1"))
        val der = signer.sign()

        val raw = PairingProof.derToP1363(der)
        assertEquals(64, raw.size)
        assertArrayEquals(der, PairingProof.p1363ToDer(raw))
    }
}
