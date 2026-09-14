package com.hanlinh.androidbrain.network

import android.content.Context
import com.hanlinh.androidbrain.agent.CommandDispatcher
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class AgentConnectionManager(
    context: Context,
    private val pairing: PairingData,
    private val client: GatewayClient = GatewayClient(),
) {
    private val appContext = context.applicationContext
    private val executor = Executors.newSingleThreadScheduledExecutor()
    private val running = AtomicBoolean(false)
    private var task: ScheduledFuture<*>? = null
    private val dispatcher = CommandDispatcher(appContext, pairing)

    fun start() {
        if (!running.compareAndSet(false, true)) return
        task = executor.scheduleWithFixedDelay({ pollOnce() }, 0, 4, TimeUnit.SECONDS)
    }

    fun stop() {
        running.set(false)
        task?.cancel(true)
        executor.shutdownNow()
    }

    private fun pollOnce() {
        if (!running.get()) return
        try {
            val command = client.nextCommand(pairing.deviceId, pairing.deviceToken) ?: return
            val result = dispatcher.handle(command)
            client.postResult(pairing.deviceId, pairing.deviceToken, result)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        } catch (_: Throwable) {
            // Network failures are retried on the next bounded polling cycle; secrets are never logged.
        }
    }
}
