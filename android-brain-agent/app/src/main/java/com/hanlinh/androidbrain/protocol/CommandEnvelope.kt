package com.hanlinh.androidbrain.protocol

import com.hanlinh.androidbrain.policy.RiskClass
import java.nio.charset.StandardCharsets
import java.security.PublicKey
import java.security.Signature
import java.time.Instant
import java.util.Base64

data class CommandEnvelope(
    val schema: Int,
    val commandId: String,
    val deviceId: String,
    val issuedAt: Instant,
    val expiresAt: Instant,
    val nonce: String,
    val goal: String,
    val capabilityScope: Set<String>,
    val riskClass: RiskClass,
    val signature: String,
) {
    fun canonicalSigningBytes(): ByteArray {
        val canonical = listOf(
            schema.toString(),
            commandId,
            deviceId,
            issuedAt.toString(),
            expiresAt.toString(),
            nonce,
            goal,
            capabilityScope.toList().sorted().joinToString(","),
            riskClass.name,
        ).joinToString("\n")
        return canonical.toByteArray(StandardCharsets.UTF_8)
    }
}

enum class RejectReason {
    INVALID_SCHEMA,
    WRONG_DEVICE,
    EXPIRED,
    REPLAY,
    INVALID_SCOPE,
    INVALID_SIGNATURE,
}

data class VerificationResult(
    val accepted: Boolean,
    val reason: RejectReason? = null,
)

class CommandEnvelopeVerifier(
    private val expectedDeviceId: String,
    private val allowedCapabilities: Set<String>,
) {
    fun verify(
        envelope: CommandEnvelope,
        gatewayPublicKey: PublicKey,
        now: Instant,
        seenNonces: Set<String>,
    ): VerificationResult {
        if (envelope.schema != 1) return VerificationResult(false, RejectReason.INVALID_SCHEMA)
        if (envelope.deviceId != expectedDeviceId) return VerificationResult(false, RejectReason.WRONG_DEVICE)
        if (!now.isBefore(envelope.expiresAt)) return VerificationResult(false, RejectReason.EXPIRED)
        if (envelope.nonce in seenNonces) return VerificationResult(false, RejectReason.REPLAY)
        if (!allowedCapabilities.containsAll(envelope.capabilityScope)) return VerificationResult(false, RejectReason.INVALID_SCOPE)
        if (envelope.signature.isBlank()) return VerificationResult(false, RejectReason.INVALID_SIGNATURE)

        return try {
            val decoded = Base64.getDecoder().decode(envelope.signature)
            val normalized = if (decoded.size == 64) p1363ToDer(decoded) else decoded
            val signatureVerifier = Signature.getInstance("SHA256withECDSA")
            signatureVerifier.initVerify(gatewayPublicKey)
            signatureVerifier.update(envelope.canonicalSigningBytes())
            if (signatureVerifier.verify(normalized)) {
                VerificationResult(true)
            } else {
                VerificationResult(false, RejectReason.INVALID_SIGNATURE)
            }
        } catch (_: Exception) {
            VerificationResult(false, RejectReason.INVALID_SIGNATURE)
        }
    }

    private fun p1363ToDer(raw: ByteArray): ByteArray {
        require(raw.size == 64) { "P-256 signature must be 64 bytes" }
        val r = normalizeInteger(raw.copyOfRange(0, 32))
        val s = normalizeInteger(raw.copyOfRange(32, 64))
        val payloadLength = 2 + r.size + 2 + s.size
        require(payloadLength < 128) { "Unexpected DER signature length" }
        return ByteArray(2 + payloadLength).also { out ->
            var p = 0
            out[p++] = 0x30
            out[p++] = payloadLength.toByte()
            out[p++] = 0x02
            out[p++] = r.size.toByte()
            r.copyInto(out, p); p += r.size
            out[p++] = 0x02
            out[p++] = s.size.toByte()
            s.copyInto(out, p)
        }
    }

    private fun normalizeInteger(input: ByteArray): ByteArray {
        var first = 0
        while (first < input.lastIndex && input[first] == 0.toByte()) first++
        val stripped = input.copyOfRange(first, input.size)
        return if ((stripped[0].toInt() and 0x80) != 0) {
            byteArrayOf(0) + stripped
        } else {
            stripped
        }
    }
}
