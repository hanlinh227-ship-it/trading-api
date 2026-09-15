package com.hanlinh.androidbrain.network

import android.content.Context
import com.hanlinh.androidbrain.agent.CommandDispatcher
import com.hanlinh.androidbrain.agent.TaskLoopDecision
import com.hanlinh.androidbrain.agent.TaskPersistence
import com.hanlinh.androidbrain.agent.TaskProgress
import com.hanlinh.androidbrain.agent.TaskProgressCheckpoint
import com.hanlinh.androidbrain.agent.TaskSessionEngine
import com.hanlinh.androidbrain.agent.TaskStepOutcome
import com.hanlinh.androidbrain.agent.TaskStepResult
import com.hanlinh.androidbrain.local.ContactsResolver
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.perception.ScreenshotCapture
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.CommandEnvelope
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService
import com.hanlinh.androidbrain.skills.core.UnknownNumberConversationClassifier
import com.hanlinh.androidbrain.skills.core.UnknownNumberConversationSelector
import java.security.MessageDigest
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

class AgentConnectionManager(
    context: Context,
    private val pairing: PairingData,
    private val client: GatewayClient = GatewayClient(),
) {
    private val appContext = context.applicationContext
    private val executor = Executors.newSingleThreadScheduledExecutor()
    private val running = AtomicBoolean(false)
    private var maintenanceTask: ScheduledFuture<*>? = null
    private var reconnectTask: ScheduledFuture<*>? = null
    private var reconnectAttempt = 0
    @Volatile private var socket: WebSocket? = null
    @Volatile private var socketConnected: Boolean = false
    private val dispatcher = CommandDispatcher(appContext, pairing)
    private val taskEngines = mutableMapOf<String, TaskSessionEngine>()
    private val receiptTracker = CommandReceiptTracker(maxEntries = 64)
    private val unknownConversationSelector by lazy {
        UnknownNumberConversationSelector(
            UnknownNumberConversationClassifier(ContactsResolver(appContext))
        )
    }

    fun start() {
        if (!running.compareAndSet(false, true)) return
        maintenanceTask = executor.scheduleWithFixedDelay(
            { maintainConnection() },
            ConnectionCadence.INITIAL_MAINTENANCE_DELAY_MS,
            ConnectionCadence.MAINTENANCE_TICK_MS,
            TimeUnit.MILLISECONDS,
        )
        submit { connectSocket() }
    }

    fun stop() {
        if (!running.compareAndSet(true, false)) return
        maintenanceTask?.cancel(true)
        reconnectTask?.cancel(true)
        maintenanceTask = null
        reconnectTask = null
        socketConnected = false
        val activeSocket = socket
        socket = null
        activeSocket?.close(1000, "service_stop")
        taskEngines.clear()
        executor.shutdownNow()
    }

    private fun connectSocket() {
        if (!running.get()) return
        try {
            socketConnected = false
            socket?.cancel()
            val listener = object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    submit {
                        if (socket === webSocket) {
                            socketConnected = true
                            reconnectAttempt = 0
                            reconnectTask?.cancel(false)
                            reconnectTask = null
                            pollOnce()
                        }
                    }
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    if (CommandSocketProtocol.isCommandAvailable(text)) {
                        submit { pollOnce() }
                    }
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    submit { handleSocketUnavailable(webSocket) }
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    submit { handleSocketUnavailable(webSocket) }
                }
            }
            socket = client.openCommandSocket(pairing.deviceId, pairing.deviceToken, listener)
        } catch (_: Throwable) {
            socketConnected = false
            socket = null
            scheduleReconnect()
        }
    }

    private fun maintainConnection() {
        if (!running.get()) return
        when (ConnectionMaintenancePolicy.action(socketConnected, socket != null)) {
            ConnectionMaintenanceAction.HEARTBEAT -> {
                val activeSocket = socket
                if (activeSocket == null || !activeSocket.send("ping")) {
                    socketConnected = false
                    activeSocket?.cancel()
                    socket = null
                    pollOnce()
                    scheduleReconnect()
                }
            }
            ConnectionMaintenanceAction.WAIT_CONNECTING -> Unit
            ConnectionMaintenanceAction.FALLBACK_POLL -> {
                pollOnce()
                scheduleReconnect()
            }
        }
    }

    private fun handleSocketUnavailable(failedSocket: WebSocket) {
        if (socket !== failedSocket) return
        socketConnected = false
        socket = null
        scheduleReconnect()
    }

    private fun scheduleReconnect() {
        if (!running.get()) return
        val existing = reconnectTask
        if (existing != null && !existing.isDone) return

        val shift = reconnectAttempt.coerceAtMost(5)
        val delayMs = (ConnectionCadence.RECONNECT_MIN_MS * (1L shl shift))
            .coerceAtMost(ConnectionCadence.RECONNECT_MAX_MS)
        reconnectAttempt = (reconnectAttempt + 1).coerceAtMost(30)
        reconnectTask = executor.schedule(
            {
                reconnectTask = null
                connectSocket()
            },
            delayMs,
            TimeUnit.MILLISECONDS,
        )
    }

    private fun submit(block: () -> Unit) {
        if (!running.get() || executor.isShutdown) return
        try {
            executor.execute(block)
        } catch (_: RejectedExecutionException) {
            // Service is stopping; no work should be rescheduled.
        }
    }

    private fun pollOnce() {
        if (!running.get()) return
        try {
            while (running.get()) {
                val command = client.nextCommand(pairing.deviceId, pairing.deviceToken) ?: return
                val cached = receiptTracker.resultFor(command.commandId)
                if (cached != null) {
                    client.postResult(pairing.deviceId, pairing.deviceToken, cached)
                    continue
                }

                val result = dispatcher.handle(command)
                receiptTracker.record(result)
                client.postResult(pairing.deviceId, pairing.deviceToken, result)
                if (command.schema == 2 && !command.taskId.isNullOrBlank()) {
                    continueTask(command, result)
                }
            }
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } catch (_: Throwable) {
            // Push-first connection maintenance retries without high-frequency HTTP churn.
        }
    }

    private fun continueTask(command: CommandEnvelope, result: GatewayClient.TaskResult) {
        val taskId = command.taskId ?: return
        val service = BrainAccessibilityService.current ?: return
        val snapshot = service.snapshot() ?: return

        val localGrounding = localGrounding(command, snapshot, result)
        if (localGrounding.failureCode != null) {
            try {
                client.postTaskStep(
                    deviceId = pairing.deviceId,
                    token = pairing.deviceToken,
                    taskId = taskId,
                    observation = snapshot,
                    previousResult = GatewayClient.TaskResult(
                        command.commandId,
                        "FAILED",
                        localGrounding.failureCode,
                    ),
                    imageDataUrl = null,
                    localFacts = emptyList(),
                )
            } finally {
                taskEngines.remove(taskId)
            }
            return
        }

        val confirmedClassC = command.riskClass == RiskClass.C &&
            "ui.destructive.confirmed" in command.capabilityScope
        val existing = taskEngines[taskId]
        val existingProgress = existing?.currentProgress()
        val effectiveRisk = if (existingProgress == null || command.riskClass.ordinal > existingProgress.riskClass.ordinal) {
            command.riskClass
        } else {
            existingProgress.riskClass
        }
        val desiredProgress = (existingProgress ?: TaskProgress(
            taskId = taskId,
            persistence = TaskPersistence.LONG_RUNNING,
        )).copy(
            riskClass = effectiveRisk,
            confirmedRiskClassC = (existingProgress?.confirmedRiskClassC == true) || confirmedClassC,
        )
        val engine = if (
            existing == null ||
            desiredProgress.riskClass != existingProgress?.riskClass ||
            desiredProgress.confirmedRiskClassC != existingProgress?.confirmedRiskClassC
        ) {
            TaskSessionEngine(desiredProgress).also { taskEngines[taskId] = it }
        } else {
            existing
        }

        val localResult = result.toTaskStepResult()
        val decision = engine.next(
            observation = snapshot,
            previousResult = localResult,
            killSwitchActive = AgentForegroundService.killSwitchActive,
        )

        if (decision is TaskLoopDecision.Failed) {
            try {
                client.postTaskStep(
                    deviceId = pairing.deviceId,
                    token = pairing.deviceToken,
                    taskId = taskId,
                    observation = snapshot,
                    previousResult = GatewayClient.TaskResult(command.commandId, "FAILED", decision.code),
                    imageDataUrl = null,
                    localFacts = localGrounding.facts,
                )
            } finally {
                taskEngines.remove(taskId)
            }
            return
        }

        val capture = capturePlannerScreenshot(service)
        val groundedSnapshot = if (capture != null) snapshot.copy(screenshotHash = capture.sha256) else snapshot
        val response = client.postTaskStep(
            deviceId = pairing.deviceId,
            token = pairing.deviceToken,
            taskId = taskId,
            observation = groundedSnapshot,
            previousResult = result,
            imageDataUrl = capture?.dataUrl,
            localFacts = localGrounding.facts,
        )
        engine.resume(
            TaskProgressCheckpoint(
                stepCount = response.stepCount,
                epoch = response.epoch,
                epochStepCount = response.epochStepCount,
                checkpointCount = response.checkpointCount,
                recoveryCount = response.recoveryCount,
            )
        )
        if (response.status in TERMINAL_TASK_STATUSES || decision is TaskLoopDecision.Completed) {
            taskEngines.remove(taskId)
        }
    }

    private fun localGrounding(
        command: CommandEnvelope,
        snapshot: AccessibilitySnapshot,
        result: GatewayClient.TaskResult,
    ): LocalGrounding {
        if (result.status.uppercase() != "COMPLETED") return LocalGrounding()
        if ("contacts.read" !in command.capabilityScope) return LocalGrounding()
        if (!isMessagingPackage(snapshot.packageName)) return LocalGrounding()

        val selection = unknownConversationSelector.select(snapshot)
        if (selection.permissionUnavailable) {
            return LocalGrounding(failureCode = "CONTACTS_PERMISSION_UNAVAILABLE")
        }
        return LocalGrounding(
            facts = selection.targets.map { target ->
                GatewayClient.LocalObservationFact(
                    kind = "UNKNOWN_NUMBER_CONFIRMED",
                    nodeId = target.actionableNodeId,
                    relatedNodeId = target.senderNodeId,
                )
            },
        )
    }

    private fun isMessagingPackage(packageName: String): Boolean {
        val value = packageName.lowercase()
        return value == "com.google.android.apps.messaging" ||
            value == "com.samsung.android.messaging" ||
            value == "com.android.messaging" ||
            value == "com.android.mms" ||
            value.endsWith(".messages") ||
            value.contains(".messaging")
    }

    private fun capturePlannerScreenshot(service: BrainAccessibilityService): PlannerScreenshot? {
        val latch = CountDownLatch(1)
        var capture: ScreenshotCapture? = null
        service.captureScreenshot {
            capture = it
            latch.countDown()
        }
        if (!latch.await(SCREENSHOT_TIMEOUT_MS, TimeUnit.MILLISECONDS)) return null
        val captured = capture as? ScreenshotCapture.Captured ?: return null
        if (captured.bytes.isEmpty() || captured.bytes.size > MAX_SCREENSHOT_BYTES) return null
        val encoded = Base64.getEncoder().encodeToString(captured.bytes)
        val sha256 = MessageDigest.getInstance("SHA-256")
            .digest(captured.bytes)
            .joinToString("") { "%02x".format(it) }
        return PlannerScreenshot(
            dataUrl = "data:${captured.mimeType};base64,$encoded",
            sha256 = sha256,
        )
    }

    private fun GatewayClient.TaskResult.toTaskStepResult(): TaskStepResult = when (status.uppercase()) {
        "COMPLETED" -> TaskStepResult(TaskStepOutcome.EXECUTED)
        "NEEDS_CONFIRMATION" -> TaskStepResult(TaskStepOutcome.NEEDS_CONFIRMATION, detail)
        "FAILED" -> if (detail in RECOVERABLE_CODES) {
            TaskStepResult(TaskStepOutcome.RECOVERABLE_FAILURE, detail)
        } else {
            TaskStepResult(TaskStepOutcome.FATAL_FAILURE, detail ?: "FAILED")
        }
        else -> TaskStepResult(TaskStepOutcome.FATAL_FAILURE, "UNKNOWN_RESULT_STATUS")
    }

    private data class PlannerScreenshot(
        val dataUrl: String,
        val sha256: String,
    )

    private data class LocalGrounding(
        val facts: List<GatewayClient.LocalObservationFact> = emptyList(),
        val failureCode: String? = null,
    )

    private companion object {
        const val SCREENSHOT_TIMEOUT_MS = 1_500L
        const val MAX_SCREENSHOT_BYTES = 2_000_000
        val TERMINAL_TASK_STATUSES = setOf("COMPLETED", "FAILED", "CANCELLED")
        val RECOVERABLE_CODES = setOf(
            "ACTION_DISPATCH_FAILED",
            "POSTCONDITION_NOT_MET",
        )
    }
}
