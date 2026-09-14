package com.hanlinh.androidbrain.network

import android.content.Context
import com.hanlinh.androidbrain.agent.CommandDispatcher
import com.hanlinh.androidbrain.agent.TaskLoopDecision
import com.hanlinh.androidbrain.agent.TaskProgress
import com.hanlinh.androidbrain.agent.TaskSessionEngine
import com.hanlinh.androidbrain.agent.TaskStepOutcome
import com.hanlinh.androidbrain.agent.TaskStepResult
import com.hanlinh.androidbrain.perception.ScreenshotCapture
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.CommandEnvelope
import com.hanlinh.androidbrain.service.AgentForegroundService
import com.hanlinh.androidbrain.service.BrainAccessibilityService
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
    private var fallbackTask: ScheduledFuture<*>? = null
    private var reconnectTask: ScheduledFuture<*>? = null
    private var reconnectAttempt = 0
    @Volatile private var socket: WebSocket? = null
    private val dispatcher = CommandDispatcher(appContext, pairing)
    private val taskEngines = mutableMapOf<String, TaskSessionEngine>()

    fun start() {
        if (!running.compareAndSet(false, true)) return
        fallbackTask = executor.scheduleWithFixedDelay(
            { pollOnce() },
            0,
            ConnectionCadence.FALLBACK_POLL_MS,
            TimeUnit.MILLISECONDS,
        )
        submit { connectSocket() }
    }

    fun stop() {
        if (!running.compareAndSet(true, false)) return
        fallbackTask?.cancel(true)
        reconnectTask?.cancel(true)
        fallbackTask = null
        reconnectTask = null
        val activeSocket = socket
        socket = null
        activeSocket?.close(1000, "service_stop")
        taskEngines.clear()
        executor.shutdownNow()
    }

    private fun connectSocket() {
        if (!running.get()) return
        try {
            socket?.cancel()
            val listener = object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    submit {
                        if (socket === webSocket) {
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
            socket = null
            scheduleReconnect()
        }
    }

    private fun handleSocketUnavailable(failedSocket: WebSocket) {
        if (socket !== failedSocket) return
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
                val result = dispatcher.handle(command)
                client.postResult(pairing.deviceId, pairing.deviceToken, result)
                if (command.schema == 2 && !command.taskId.isNullOrBlank()) {
                    continueTask(command, result)
                }
            }
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } catch (_: Throwable) {
            // Fast fallback polling remains active if push is unavailable.
        }
    }

    private fun continueTask(command: CommandEnvelope, result: GatewayClient.TaskResult) {
        val taskId = command.taskId ?: return
        val service = BrainAccessibilityService.current ?: return
        val snapshot = service.snapshot() ?: return

        val confirmedClassC = command.riskClass == RiskClass.C &&
            "ui.destructive.confirmed" in command.capabilityScope
        val existing = taskEngines[taskId]
        val existingProgress = existing?.currentProgress()
        val effectiveRisk = if (existingProgress == null || command.riskClass.ordinal > existingProgress.riskClass.ordinal) {
            command.riskClass
        } else {
            existingProgress.riskClass
        }
        val desiredProgress = (existingProgress ?: TaskProgress(taskId = taskId)).copy(
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
                )
            } finally {
                taskEngines.remove(taskId)
            }
            return
        }

        val imageDataUrl = capturePlannerScreenshot(service)
        val response = client.postTaskStep(
            deviceId = pairing.deviceId,
            token = pairing.deviceToken,
            taskId = taskId,
            observation = snapshot,
            previousResult = result,
            imageDataUrl = imageDataUrl,
        )
        if (response.status in TERMINAL_TASK_STATUSES || decision is TaskLoopDecision.Completed) {
            taskEngines.remove(taskId)
        }
    }

    private fun capturePlannerScreenshot(service: BrainAccessibilityService): String? {
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
        return "data:${captured.mimeType};base64,$encoded"
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
