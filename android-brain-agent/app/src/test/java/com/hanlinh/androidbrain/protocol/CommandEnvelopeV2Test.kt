package com.hanlinh.androidbrain.protocol

import com.hanlinh.androidbrain.policy.RiskClass
import java.security.KeyPairGenerator
import java.security.Signature
import java.time.Instant
import java.util.Base64
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CommandEnvelopeV2Test {
    private val now = Instant.parse("2026-09-14T04:00:00Z")
    private val keyPair = KeyPairGenerator.getInstance("EC").apply { initialize(256) }.generateKeyPair()
    private val verifier = CommandEnvelopeVerifier(
        expectedDeviceId = "device-1",
        allowedCapabilities = setOf("apps.open", "ui.navigate"),
    )

    @Test fun schema1_canonical_bytes_remain_unchanged() {
        val envelope = CommandEnvelope(
            schema = 1,
            commandId = "cmd-1",
            deviceId = "device-1",
            issuedAt = Instant.parse("2026-09-14T03:59:59Z"),
            expiresAt = Instant.parse("2026-09-14T04:01:00Z"),
            nonce = "nonce-1",
            goal = "Open Settings",
            capabilityScope = setOf("ui.navigate", "apps.open"),
            riskClass = RiskClass.A,
            signature = "",
        )

        assertEquals(
            listOf(
                "1",
                "cmd-1",
                "device-1",
                "2026-09-14T03:59:59Z",
                "2026-09-14T04:01:00Z",
                "nonce-1",
                "Open Settings",
                "apps.open,ui.navigate",
                "A",
            ).joinToString("\n"),
            envelope.canonicalSigningBytes().toString(Charsets.UTF_8),
        )
    }

    @Test fun schema2_canonical_bytes_include_task_and_deterministic_action_json() {
        val envelope = schema2Envelope()

        assertEquals(
            listOf(
                "2",
                "cmd-2",
                "device-1",
                "2026-09-14T03:59:59Z",
                "2026-09-14T04:01:00Z",
                "nonce-2",
                "task-7",
                "{\"type\":\"tap_point\",\"x\":120,\"y\":340}",
                "ui.navigate",
                "A",
            ).joinToString("\n"),
            envelope.canonicalSigningBytes().toString(Charsets.UTF_8),
        )
    }

    @Test fun valid_signed_schema2_command_is_accepted() {
        val result = verifier.verify(signed(schema2Envelope()), keyPair.public, now, emptySet())
        assertTrue(result.accepted)
    }

    @Test fun schema2_wrong_device_is_rejected_before_signature_acceptance() {
        val command = signed(schema2Envelope().copy(deviceId = "other-device"))
        val result = verifier.verify(command, keyPair.public, now, emptySet())
        assertEquals(RejectReason.WRONG_DEVICE, result.reason)
    }

    @Test fun schema2_disallowed_capability_scope_is_rejected() {
        val command = signed(schema2Envelope().copy(capabilityScope = setOf("wallet.sign")))
        val result = verifier.verify(command, keyPair.public, now, emptySet())
        assertEquals(RejectReason.INVALID_SCOPE, result.reason)
    }

    private fun schema2Envelope() = CommandEnvelope(
        schema = 2,
        commandId = "cmd-2",
        deviceId = "device-1",
        issuedAt = now.minusSeconds(1),
        expiresAt = now.plusSeconds(60),
        nonce = "nonce-2",
        goal = "",
        capabilityScope = setOf("ui.navigate"),
        riskClass = RiskClass.A,
        signature = "",
        taskId = "task-7",
        action = TapPoint(120, 340),
    )

    private fun signed(envelope: CommandEnvelope): CommandEnvelope {
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(keyPair.private)
        signer.update(envelope.canonicalSigningBytes())
        return envelope.copy(signature = Base64.getEncoder().encodeToString(signer.sign()))
    }
}
