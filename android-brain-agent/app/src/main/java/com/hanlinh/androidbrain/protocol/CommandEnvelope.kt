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
            val signatureVerifier = Signature.getInstance("SHA256withECDSA")
            signatureVerifier.initVerify(gatewayPublicKey)
            signatureVerifier.update(envelope.canonicalSigningBytes())
            val signatureBytes = Base64.getDecoder().decode(envelope.signature)
            if (signatureVerifier.verify(signatureBytes)) {
                VerificationResult(true)
            } else {
                VerificationResult(false, RejectReason.INVALID_SIGNATURE)
            }
        } catch (_: Exception) {
            VerificationResult(false, RejectReason.INVALID_SIGNATURE)
        }
    }
}
