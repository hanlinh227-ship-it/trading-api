package com.hanlinh.androidbrain.agent

import android.content.Context
import android.util.Base64
import com.hanlinh.androidbrain.action.AccessibilityActions
import com.hanlinh.androidbrain.action.AppResolver
import com.hanlinh.androidbrain.action.NativeActions
import com.hanlinh.androidbrain.network.GatewayClient
import com.hanlinh.androidbrain.network.PairingData
import com.hanlinh.androidbrain.policy.AuthorizationDecision
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.policy.RiskPolicy
import com.hanlinh.androidbrain.policy.UserPolicy
import com.hanlinh.androidbrain.protocol.Action
import com.hanlinh.androidbrain.protocol.CommandEnvelope
import com.hanlinh.androidbrain.protocol.CommandEnvelopeVerifier
import com.hanlinh.androidbrain.protocol.LaunchApp
import com.hanlinh.androidbrain.protocol.OpenUrl
import com.hanlinh.androidbrain.protocol.ReadScreen
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService
import java.security.KeyFactory
import java.security.PublicKey
import java.security.spec.X509EncodedKeySpec
import java.time.Instant
import java.util.Collections
import org.json.JSONArray
import org.json.JSONObject

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
        allowedCapabilities = setOf(
            "apps.open",
            "ui.navigate",
            "ui.write",
            "ui.destructive.confirmed",
            "notifications.read",
            "contacts.read",
            "files.read",
        ),
    )

    fun handle(command: CommandEnvelope): GatewayClient.TaskResult {
        if (AgentForegroundService.killSwitchActive) return failure(command, "KILL_SWITCH")
        val verified = verifier.verify(command, gatewayKey, Instant.now(), seenNonces.toSet())
        if (!verified.accepted) return failure(command, "SIGNATURE_OR_ENVELOPE_${verified.reason}")
        seenNonces += command.nonce
        if (seenNonces.size > 500) seenNonces.clear()

        val action = when (command.schema) {
            1 -> GoalParser.parse(command.goal) { appResolver.findPackageByLabel(it) }
                ?: return failure(command, "UNSUPPORTED_GOAL")
            2 -> command.action ?: return failure(command, "MISSING_TYPED_ACTION")
            else -> return failure(command, "UNSUPPORTED_SCHEMA")
        }

        if (!scopeAllows(command, action)) return failure(command, "CAPABILITY_SCOPE_DENIED")

        val effectiveRisk = maxRisk(action.riskClass, command.riskClass)
        val confirmedClassC = effectiveRisk == RiskClass.C &&
            command.riskClass == RiskClass.C &&
            "ui.destructive.confirmed" in command.capabilityScope
        val scopedClassB = command.schema == 2 &&
            effectiveRisk == RiskClass.B &&
            command.riskClass == RiskClass.B &&
            "ui.write" in command.capabilityScope

        when (riskPolicy.authorize(
            action = action,
            userPolicy = UserPolicy(classBEnabled = scopedClassB),
            confirmedClassC = confirmedClassC,
            effectiveRiskClass = effectiveRisk,
        )) {
            AuthorizationDecision.Allowed -> Unit
            is AuthorizationDecision.NeedsConfirmation -> return GatewayClient.TaskResult(command.commandId, "NEEDS_CONFIRMATION")
            AuthorizationDecision.Denied -> return failure(command, "POLICY_DENIED")
        }

        if (action === ReadScreen) {
            return if (command.schema == 2) observationMetadata(command) else safeScreenResult(command)
        }

        val dispatched = execute(action)
        if (!dispatched) return failure(command, "ACTION_DISPATCH_FAILED")
        if (action is LaunchApp && !verifyForeground(action.packageName)) return failure(command, "POSTCONDITION_NOT_MET")
        return if (command.schema == 2) observationMetadata(command) else GatewayClient.TaskResult(command.commandId, "COMPLETED")
    }

    private fun scopeAllows(command: CommandEnvelope, action: Action): Boolean {
        if (command.schema == 1) return true
        val required = when (action) {
            is LaunchApp -> "apps.open"
            is OpenUrl -> "apps.open"
            ReadScreen -> "ui.navigate"
            else -> when (action.riskClass) {
                RiskClass.A -> "ui.navigate"
                RiskClass.B -> "ui.write"
                RiskClass.C -> "ui.destructive.confirmed"
                RiskClass.D -> return false
            }
        }
        return required in command.capabilityScope
    }

    private fun execute(action: Action): Boolean = when (action) {
        is LaunchApp -> native.launch(action)
        is OpenUrl -> native.openUrl(action)
        else -> accessibility.execute(action)
    }

    private fun observationMetadata(command: CommandEnvelope): GatewayClient.TaskResult {
        val snapshot = BrainAccessibilityService.current?.snapshot()
            ?: return failure(command, "SCREEN_UNAVAILABLE")
        val detail = JSONObject()
            .put("taskId", command.taskId ?: JSONObject.NULL)
            .put("packageName", snapshot.packageName)
            .put("fingerprint", snapshot.fingerprint())
            .put("nodeCount", snapshot.nodes.size)
            .toString()
        return GatewayClient.TaskResult(command.commandId, "COMPLETED", detail)
    }

    private fun safeScreenResult(command: CommandEnvelope): GatewayClient.TaskResult {
        val snapshot = BrainAccessibilityService.current?.snapshot()
            ?: return failure(command, "SCREEN_UNAVAILABLE")
        val controls = JSONArray()
        val emitted = mutableSetOf<String>()
        for (node in snapshot.nodes) {
            val candidates = listOfNotNull(node.text, node.contentDescription)
            val canonical = SAFE_CONTROL_TOKENS.firstOrNull { token ->
                candidates.any { value -> value.contains(token, ignoreCase = true) }
            } ?: continue
            if (!emitted.add(canonical)) continue
            controls.put(
                JSONObject()
                    .put("label", canonical)
                    .put("clickable", node.clickable)
                    .put("resourceId", node.resourceId ?: JSONObject.NULL)
            )
            if (controls.length() >= 40) break
        }
        val detail = JSONObject()
            .put("packageName", snapshot.packageName)
            .put("controls", controls)
            .toString()
        return GatewayClient.TaskResult(command.commandId, "COMPLETED", detail)
    }

    private fun maxRisk(a: RiskClass, b: RiskClass): RiskClass = if (a.ordinal >= b.ordinal) a else b

    private fun verifyForeground(packageName: String): Boolean {
        repeat(8) {
            val snapshot = BrainAccessibilityService.current?.snapshot()
            if (snapshot?.packageName == packageName) return true
            Thread.sleep(250)
        }
        return false
    }

    private fun failure(command: CommandEnvelope, code: String) = GatewayClient.TaskResult(command.commandId, "FAILED", code)

    companion object {
        private val SAFE_CONTROL_TOKENS = listOf(
            "spam & blocked", "spam and blocked", "thư rác và bị chặn", "tin nhắn rác và bị chặn",
            "more options", "tùy chọn khác", "account menu", "menu tài khoản", "profile", "hồ sơ",
            "select all", "chọn tất cả", "move to trash", "chuyển vào thùng rác", "trash", "thùng rác",
            "delete", "xóa", "block", "chặn", "messages", "tin nhắn", "back", "quay lại",
            "done", "xong", "cancel", "hủy", "ok",
        )
    }
}
