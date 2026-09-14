package com.hanlinh.androidbrain.agent

import android.content.Context
import android.util.Base64
import com.hanlinh.androidbrain.action.AccessibilityActions
import com.hanlinh.androidbrain.action.AppResolver
import com.hanlinh.androidbrain.action.NativeActions
import com.hanlinh.androidbrain.network.GatewayClient
import com.hanlinh.androidbrain.network.PairingData
import com.hanlinh.androidbrain.policy.AuthorizationDecision
import com.hanlinh.androidbrain.policy.RiskPolicy
import com.hanlinh.androidbrain.policy.UserPolicy
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.CommandEnvelope
import com.hanlinh.androidbrain.protocol.CommandEnvelopeVerifier
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.OpenUrl
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService
import java.security.KeyFactory
import java.security.PublicKey
import java.security.spec.X509EncodedKeySpec
import java.time.Instant
import java.util.Collections

class CommandDispatcher(
    private val context: Context,
    private val pairing: PairingData,
    private val riskPolicy: RiskPolicy = RiskPolicy(),
) {
    private val seenNonces = Collections.synchronizedSet(mutableSetOf<String>())
    private val native = NativeActions(context)
    private val accessibility = AccessibilityActions()
    private val appResolver = AppResolver(context)
    private val gatewayKey: PublicKey = KeyFactory.getInstance("EC").generatePublic(
        X509EncodedKeySpec(Base64.decode(pairing.gatewayPublicKeyBase64, Base64.NO_WRAP))
    )
    private val verifier = CommandEnvelopeVerifier(
        expectedDeviceId = pairing.deviceId,
        allowedCapabilities = setOf("apps.open", "ui.navigate", "notifications.read", "files.read"),
    )

    fun handle(command: CommandEnvelope): GatewayClient.TaskResult {
        if (AgentForegroundService.killSwitchActive) return failure(command, "KILL_SWITCH")
        val verified = verifier.verify(command, gatewayKey, Instant.now(), seenNonces.toSet())
        if (!verified.accepted) return failure(command, "SIGNATURE_OR_ENVELOPE_${verified.reason}")
        seenNonces += command.nonce
        if (seenNonces.size > 500) seenNonces.clear()

        val action = GoalParser.parse(command.goal) { appResolver.findPackageByLabel(it) }
            ?: return failure(command, "UNSUPPORTED_GOAL")
        when (riskPolicy.authorize(action, UserPolicy.defaults())) {
            AuthorizationDecision.Allowed -> Unit
            is AuthorizationDecision.NeedsConfirmation -> return GatewayClient.TaskResult(command.commandId, "NEEDS_CONFIRMATION")
            AuthorizationDecision.Denied -> return failure(command, "POLICY_DENIED")
        }
        val dispatched = execute(action)
        if (!dispatched) return failure(command, "ACTION_DISPATCH_FAILED")
        if (action is LaunchApp && !verifyForeground(action.packageName)) return failure(command, "POSTCONDITION_NOT_MET")
        return GatewayClient.TaskResult(command.commandId, "COMPLETED")
    }

    private fun execute(action: Action): Boolean = when (action) {
        is LaunchApp -> native.launch(action)
        is OpenUrl -> native.openUrl(action)
        else -> accessibility.execute(action)
    }

    private fun verifyForeground(packageName: String): Boolean {
        repeat(8) {
            val snapshot = BrainAccessibilityService.current?.snapshot()
            if (snapshot?.packageName == packageName) return true
            Thread.sleep(250)
        }
        return false
    }

    private fun failure(command: CommandEnvelope, code: String) = GatewayClient.TaskResult(command.commandId, "FAILED", code)
}
