package com.hanlinh.androidbrain.network

import android.content.Context
import com.hanlinh.androidbrain.agent.CommandDispatcher
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
            }
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } catch (_: Throwable) {
            // Fast fallback polling remains active if push is unavailable.
        }
    }
}
