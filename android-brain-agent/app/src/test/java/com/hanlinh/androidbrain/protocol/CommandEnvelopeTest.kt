package com.hanlinh.androidbrain.protocol

import com.hanlinh.androidbrain.policy.RiskClass
import java.security.KeyPairGenerator
import java.security.Signature
import java.time.Instant
import java.util.Base64
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CommandEnvelopeTest {
    private val now = Instant.parse("2026-09-14T04:00:00Z")
    private val keyPair = KeyPairGenerator.getInstance("EC").apply { initialize(256) }.generateKeyPair()
    private val verifier = CommandEnvelopeVerifier(
        expectedDeviceId = "device-1",
        allowedCapabilities = setOf("apps.open", "ui.navigate")
    )

    private fun envelope(expiresAt: Instant = now.plusSeconds(60), nonce: String = "nonce-1") = CommandEnvelope(
        schema = 1,
        commandId = "cmd-1",
        deviceId = "device-1",
        issuedAt = now.minusSeconds(1),
        expiresAt = expiresAt,
        nonce = nonce,
        goal = "Open Settings",
        capabilityScope = setOf("apps.open"),
        riskClass = RiskClass.A,
        signature = ""
    )

    private fun signed(envelope: CommandEnvelope): CommandEnvelope {
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(keyPair.private)
        signer.update(envelope.canonicalSigningBytes())
        return envelope.copy(signature = Base64.getEncoder().encodeToString(signer.sign()))
    }

    @Test fun expired_command_is_rejected() {
        val result = verifier.verify(signed(envelope(now.minusSeconds(1))), keyPair.public, now, emptySet())
        assertEquals(RejectReason.EXPIRED, result.reason)
    }

    @Test fun seen_nonce_is_rejected() {
        val candidate = signed(envelope(nonce = "seen"))
        val result = verifier.verify(candidate, keyPair.public, now, setOf("seen"))
        assertEquals(RejectReason.REPLAY, result.reason)
    }

    @Test fun valid_signed_command_is_accepted() {
        val result = verifier.verify(signed(envelope()), keyPair.public, now, emptySet())
        assertTrue(result.accepted)
    }

    @Test fun webcrypto_p1363_signature_is_accepted() {
        val derSigned = signed(envelope())
        val raw = derToP1363(Base64.getDecoder().decode(derSigned.signature))
        val candidate = derSigned.copy(signature = Base64.getEncoder().encodeToString(raw))
        assertTrue(verifier.verify(candidate, keyPair.public, now, emptySet()).accepted)
    }

    private fun derToP1363(der: ByteArray): ByteArray {
        var p = 2
        check(der[p++].toInt() == 0x02)
        val rLen = der[p++].toInt() and 0xff
        val r = der.copyOfRange(p, p + rLen); p += rLen
        check(der[p++].toInt() == 0x02)
        val sLen = der[p++].toInt() and 0xff
        val s = der.copyOfRange(p, p + sLen)
        fun fixed(v: ByteArray): ByteArray {
            val stripped = if (v.size > 32) v.copyOfRange(v.size - 32, v.size) else v
            return ByteArray(32).also { stripped.copyInto(it, 32 - stripped.size) }
        }
        return fixed(r) + fixed(s)
    }
}
