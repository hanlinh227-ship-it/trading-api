package com.hanlinh.androidbrain.network

import android.content.Context
import com.hanlinh.androidbrain.agent.CommandDispatcher
import com.hanlinh.androidbrain.agent.PersistentOperatorSession
import com.hanlinh.androidbrain.agent.UnifiedTaskRuntime
import com.hanlinh.androidbrain.local.ContactsResolver
import com.hanlinh.androidbrain.mapping.SharedPreferencesAppMappingStore
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.perception.EventDrivenObserver
import com.hanlinh.androidbrain.perception.ScreenshotCapture
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService
import com.hanlinh.androidbrain.skills.core.UnknownNumberConversationClassifier
import com.hanlinh.androidbrain.skills.core.UnknownNumberConversationSelector
import java.security.MessageDigest
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
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
    private val mappingStore = SharedPreferencesAppMappingStore(appContext)
    private val taskRuntimes = ConcurrentHashMap<String, UnifiedTaskRuntime>()
    private val taskLocalActionTotals = ConcurrentHashMap<String, Long>()
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
        taskRuntimes.values.forEach { it.requestCancel() }
        taskRuntimes.clear()
        taskLocalActionTotals.clear()
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
                    when (val event = CommandSocketProtocol.parseEvent(text)) {
                        CommandSocketEvent.CommandAvailable -> submit { pollOnce() }
                        is CommandSocketEvent.TaskCancelled -> {
                            // Cancellation is thread-safe and intentionally bypasses the single-thread queue
                            // so a long local loop stops before its next non-atomic action.
                            taskRuntimes[event.taskId]?.requestCancel()
                        }
                        null -> Unit
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
                    continueTask(command.taskId!!, command.commandId, command.capabilityScope, result)
                }
            }
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } catch (_: Throwable) {
            // Push-first connection maintenance retries without high-frequency HTTP churn.
        }
    }

    private fun continueTask(
        taskId: String,
        commandId: String,
        commandScope: Set<String>,
        result: GatewayClient.TaskResult,
    ) {
        val service = BrainAccessibilityService.current ?: return
        val snapshot = service.snapshot() ?: return
        val localGrounding = localGrounding(commandScope, snapshot, result.status)
        if (localGrounding.failureCode != null) {
            try {
                client.postTaskStep(
                    deviceId = pairing.deviceId,
                    token = pairing.deviceToken,
                    taskId = taskId,
                    observation = snapshot,
                    previousResult = GatewayClient.TaskResult(commandId, "FAILED", localGrounding.failureCode),
                    localFacts = emptyList(),
                    localOperator = true,
                )
            } finally {
                cleanupTask(taskId)
            }
            return
        }

        val initialCapture = if (snapshot.nodes.size <= SPARSE_NODE_THRESHOLD) capturePlannerScreenshot(service) else null
        val groundedSnapshot = if (initialCapture != null) snapshot.copy(screenshotHash = initialCapture.sha256) else snapshot
        val response = client.postTaskStep(
            deviceId = pairing.deviceId,
            token = pairing.deviceToken,
            taskId = taskId,
            observation = groundedSnapshot,
            previousResult = result,
            imageDataUrl = initialCapture?.dataUrl,
            localFacts = localGrounding.facts,
            localOperator = true,
            maxActions = MAX_CLOUD_BATCH_ACTIONS,
        )

        if (response.status in TERMINAL_TASK_STATUSES) {
            cleanupTask(taskId)
            return
        }

        val batchId = response.localBatchId
        val session = response.persistentSessionOrNull(taskId)
        if (batchId == null || session == null) {
            // The gateway may intentionally keep a consequential task on the signed-command path.
            // In that case no local authority is inferred from an incomplete response.
            cleanupTask(taskId)
            return
        }

        val runtime = createRuntime(session, response.localActions)
        taskRuntimes[taskId] = runtime
        runLocalRuntime(taskId, runtime, batchId, service, response)
    }

    private fun createRuntime(
        session: PersistentOperatorSession,
        initialActions: List<com.hanlinh.androidbrain.protocol.Action>,
    ): UnifiedTaskRuntime {
        var revisionToAwait: Long? = null
        val observationProvider = {
            val observer = EventDrivenObserver.current
            val revision = revisionToAwait
            if (observer == null) {
                null
            } else if (revision != null) {
                revisionToAwait = null
                observer.awaitSemanticChange(revision, timeoutMs = POST_ACTION_EVENT_TIMEOUT_MS)
            } else {
                observer.refresh()
            }
        }
        val actionExecutor: (com.hanlinh.androidbrain.protocol.Action, PersistentOperatorSession) -> Boolean = { action, authority ->
            val observer = EventDrivenObserver.current
            val beforeRevision = observer?.cache?.semanticRevision
            val executed = dispatcher.executeAuthorizedLocal(action, authority)
            if (executed && beforeRevision != null) revisionToAwait = beforeRevision
            executed
        }
        return UnifiedTaskRuntime(
            taskId = session.taskId,
            session = session,
            mappingStore = mappingStore,
            initialCloudActions = initialActions,
            observationProvider = observationProvider,
            actionExecutor = actionExecutor,
        )
    }

    private fun runLocalRuntime(
        taskId: String,
        initialRuntime: UnifiedTaskRuntime,
        initialBatchId: String,
        service: BrainAccessibilityService,
        initialResponse: GatewayClient.TaskStepResponse,
    ) {
        var runtime = initialRuntime
        var batchId = initialBatchId
        var serverStepCount = initialResponse.stepCount
        var serverEpoch = initialResponse.epoch
        var serverCheckpointCount = initialResponse.checkpointCount

        while (running.get() && taskRuntimes[taskId] === runtime) {
            if (AgentForegroundService.killSwitchActive) {
                runtime.requestCancel()
                cleanupTask(taskId)
                return
            }

            val loop = runtime.runUntilEscalation(MAX_LOCAL_ACTIONS_PER_CHUNK)
            val total = taskLocalActionTotals.merge(taskId, loop.executedLocalActions.toLong(), Long::plus) ?: 0L

            if (loop.reason == "LOCAL_BUDGET_REACHED") {
                postCheckpointBestEffort(
                    taskId = taskId,
                    runtime = runtime,
                    serverStepCount = serverStepCount,
                    serverEpoch = serverEpoch,
                    serverCheckpointCount = serverCheckpointCount,
                    localActionTotal = total,
                )
                continue
            }

            if (loop.reason == "CANCELLED") {
                cleanupTask(taskId)
                return
            }

            val snapshot = service.snapshot() ?: run {
                cleanupTask(taskId)
                return
            }
            val grounding = localGrounding(runtime.currentSession().capabilityScope, snapshot, "COMPLETED")
            if (grounding.failureCode != null) {
                reportLocalFailure(taskId, batchId, snapshot, grounding.failureCode)
                cleanupTask(taskId)
                return
            }

            val recoverableCode = when (loop.reason) {
                "LOCAL_ACTION_DISPATCH_FAILED" -> "ACTION_DISPATCH_FAILED"
                "LOCAL_POSTCONDITION_NOT_MET", "POST_ACTION_OBSERVATION_REQUIRED" -> "POSTCONDITION_NOT_MET"
                else -> null
            }
            val terminalCode = when (loop.reason) {
                "APP_SCOPE_EXIT" -> "APP_SCOPE_EXIT"
                "HARD_SAFETY_BLOCK" -> "HARD_SAFETY_BLOCK"
                else -> null
            }
            val captureNeeded = loop.reason in VISUAL_ESCALATION_REASONS || snapshot.nodes.size <= SPARSE_NODE_THRESHOLD
            val capture = if (captureNeeded) capturePlannerScreenshot(service) else null
            val groundedSnapshot = if (capture != null) snapshot.copy(screenshotHash = capture.sha256) else snapshot
            val previousResult = when {
                terminalCode != null -> GatewayClient.TaskResult(batchId, "FAILED", terminalCode)
                recoverableCode != null -> GatewayClient.TaskResult(batchId, "FAILED", recoverableCode)
                else -> GatewayClient.TaskResult(batchId, "COMPLETED")
            }

            val response = try {
                client.postTaskStep(
                    deviceId = pairing.deviceId,
                    token = pairing.deviceToken,
                    taskId = taskId,
                    observation = groundedSnapshot,
                    previousResult = previousResult,
                    imageDataUrl = capture?.dataUrl,
                    localFacts = grounding.facts,
                    localOperator = true,
                    maxActions = MAX_CLOUD_BATCH_ACTIONS,
                )
            } catch (error: GatewayClient.GatewayException) {
                if (error.statusCode == 409) {
                    cleanupTask(taskId)
                    return
                }
                // A temporary cloud loss does not revoke an already-authorized runtime.
                // Continue only while the runtime still has a verified local path.
                if (runtime.hasPendingCloudActions()) continue
                cleanupTask(taskId)
                return
            }

            serverStepCount = response.stepCount
            serverEpoch = response.epoch
            serverCheckpointCount = response.checkpointCount
            if (response.status in TERMINAL_TASK_STATUSES || terminalCode != null) {
                cleanupTask(taskId)
                return
            }

            val nextBatchId = response.localBatchId
            val nextSession = response.persistentSessionOrNull(taskId)
            if (nextBatchId == null || nextSession == null) {
                // Consequential actions remain on the signed command queue.
                cleanupTask(taskId)
                return
            }

            runtime = createRuntime(nextSession, response.localActions)
            taskRuntimes[taskId] = runtime
            batchId = nextBatchId
        }
    }

    private fun postCheckpointBestEffort(
        taskId: String,
        runtime: UnifiedTaskRuntime,
        serverStepCount: Int,
        serverEpoch: Int,
        serverCheckpointCount: Int,
        localActionTotal: Long,
    ) {
        val observation = EventDrivenObserver.current?.latest()
        runCatching {
            client.postCheckpoint(
                pairing.deviceId,
                pairing.deviceToken,
                taskId,
                GatewayClient.V5Checkpoint(
                    stepCount = (serverStepCount.toLong() + localActionTotal).coerceAtMost(Int.MAX_VALUE.toLong()).toInt(),
                    epoch = serverEpoch + (localActionTotal / CHECKPOINT_ACTION_INTERVAL).toInt(),
                    checkpointCount = serverCheckpointCount + (localActionTotal / CHECKPOINT_ACTION_INTERVAL).toInt(),
                    screenSignature = observation?.screenSignature,
                    metrics = mapOf(
                        "localReasoningCount" to localActionTotal.toDouble(),
                        "cloudReasoningCount" to 1.0,
                    ),
                ),
            )
        }
        if (runtime.currentSession().terminal) cleanupTask(taskId)
    }

    private fun reportLocalFailure(
        taskId: String,
        batchId: String,
        snapshot: AccessibilitySnapshot,
        code: String,
    ) {
        runCatching {
            client.postTaskStep(
                deviceId = pairing.deviceId,
                token = pairing.deviceToken,
                taskId = taskId,
                observation = snapshot,
                previousResult = GatewayClient.TaskResult(batchId, "FAILED", code),
                localOperator = true,
            )
        }
    }

    private fun cleanupTask(taskId: String) {
        taskRuntimes.remove(taskId)?.requestCancel()
        taskLocalActionTotals.remove(taskId)
    }

    private fun localGrounding(
        capabilityScope: Set<String>,
        snapshot: AccessibilitySnapshot,
        resultStatus: String,
    ): LocalGrounding {
        if (resultStatus.uppercase() != "COMPLETED") return LocalGrounding()
        if ("contacts.read" !in capabilityScope) return LocalGrounding()
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
        const val POST_ACTION_EVENT_TIMEOUT_MS = 800L
        const val MAX_SCREENSHOT_BYTES = 2_000_000
        const val SPARSE_NODE_THRESHOLD = 2
        const val MAX_CLOUD_BATCH_ACTIONS = 8
        const val MAX_LOCAL_ACTIONS_PER_CHUNK = 32
        const val CHECKPOINT_ACTION_INTERVAL = 50L
        val TERMINAL_TASK_STATUSES = setOf("COMPLETED", "FAILED", "CANCELLED")
        val VISUAL_ESCALATION_REASONS = setOf(
            "CAPTURE_VISUAL",
            "CLOUD_RECOVERY",
            "LOCAL_POSTCONDITION_NOT_MET",
            "POST_ACTION_OBSERVATION_REQUIRED",
        )
    }
}