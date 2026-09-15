package com.hanlinh.androidbrain.agent

import android.content.Context
import android.util.Base64
import com.hanlinh.androidbrain.action.AccessibilityActions
import com.hanlinh.androidbrain.action.AccessibilityAppLauncher
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
import com.hanlinh.androidbrain.protocol.GlobalBack
import com.hanlinh.androidbrain.protocol.GlobalHome
import com.hanlinh.androidbrain.protocol.GlobalNotifications
import com.hanlinh.androidbrain.protocol.GlobalQuickSettings
import com.hanlinh.androidbrain.protocol.GlobalRecents
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
    private val accessibilityLauncher = AccessibilityAppLauncher(appResolver::labelForPackage)
    private val launchCoordinator = AppLaunchCoordinator(
        directLaunch = native::launch,
        verifyForeground = ::verifyForeground,
        accessibilityFallback = accessibilityLauncher::launch,
    )
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
            command.riskClass == RiskClass.B

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

        if (action is LaunchApp) {
            val result = launchCoordinator.launch(action)
            if (result == AppLaunchResult.FAILED_POSTCONDITION) {
                return failure(command, "POSTCONDITION_NOT_MET")
            }
            return if (command.schema == 2) observationMetadata(command)
            else GatewayClient.TaskResult(command.commandId, "COMPLETED")
        }

        val beforeSnapshot = BrainAccessibilityService.current?.snapshot()
        val dispatched = execute(action)
        if (!dispatched) return failure(command, "ACTION_DISPATCH_FAILED")

        when (action) {
            GlobalHome -> {
                val homePackage = appResolver.findHomePackage()
                    ?: return failure(command, "HOME_PACKAGE_UNRESOLVED")
                if (!verifyForeground(homePackage)) return failure(command, "POSTCONDITION_NOT_MET")
            }
            GlobalBack, GlobalRecents, GlobalNotifications, GlobalQuickSettings -> {
                if (beforeSnapshot == null) return failure(command, "SCREEN_UNAVAILABLE")
                if (!verifyObservationChanged(beforeSnapshot.fingerprint(), beforeSnapshot.packageName)) {
                    return failure(command, "POSTCONDITION_NOT_MET")
                }
            }
            else -> Unit
        }

        return if (command.schema == 2) observationMetadata(command) else GatewayClient.TaskResult(command.commandId, "COMPLETED")
    }

    /**
     * Executes a typed V5 action only inside already-authorized task authority.
     * This is a second clamp behind UnifiedOperatorEngine; it never permits Class C/D locally.
     */
    fun executeAuthorizedLocal(action: Action, session: PersistentOperatorSession): Boolean {
        if (AgentForegroundService.killSwitchActive || session.terminal) return false
        if (action.riskClass.ordinal >= RiskClass.C.ordinal) return false
        if (action.riskClass.ordinal > session.riskCeiling.ordinal) return false

        val requiredCapability = when (action) {
            is LaunchApp, is OpenUrl -> "apps.open"
            else -> if (action.riskClass == RiskClass.B) "ui.write" else "ui.navigate"
        }
        if (requiredCapability !in session.capabilityScope) return false
        if (action is LaunchApp && session.allowedPackages.isNotEmpty() && action.packageName !in session.allowedPackages) {
            return false
        }
        if (action is OpenUrl && session.allowedPackages.isNotEmpty()) return false

        when (riskPolicy.authorize(
            action = action,
            userPolicy = UserPolicy(classBEnabled = action.riskClass == RiskClass.B),
            confirmedClassC = false,
            effectiveRiskClass = action.riskClass,
        )) {
            AuthorizationDecision.Allowed -> Unit
            else -> return false
        }

        if (action === ReadScreen) return BrainAccessibilityService.current?.snapshot() != null
        return execute(action)
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
        repeat(10) {
            val snapshot = BrainAccessibilityService.current?.snapshot()
            if (snapshot?.packageName == packageName) return true
            Thread.sleep(250)
        }
        return false
    }

    private fun verifyObservationChanged(previousFingerprint: String, previousPackage: String): Boolean {
        repeat(10) {
            val snapshot = BrainAccessibilityService.current?.snapshot()
            if (snapshot != null && (
                    snapshot.packageName != previousPackage ||
                        snapshot.fingerprint() != previousFingerprint
                )
            ) return true
            Thread.sleep(200)
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
