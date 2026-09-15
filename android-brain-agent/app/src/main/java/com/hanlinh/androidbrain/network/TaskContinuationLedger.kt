package com.hanlinh.androidbrain.network

class TaskContinuationLedger(
    private val maxEntries: Int = 32,
) {
    init {
        require(maxEntries > 0) { "maxEntries must be positive" }
    }

    data class Pending(
        val taskId: String,
        val commandId: String,
    ) {
        init {
            require(taskId.isNotBlank()) { "taskId must not be blank" }
            require(commandId.isNotBlank()) { "commandId must not be blank" }
        }
    }

    private val entries = LinkedHashMap<String, Pending>()

    @Synchronized
    fun record(pending: Pending) {
        entries.remove(pending.taskId)
        entries[pending.taskId] = pending
        while (entries.size > maxEntries) {
            val oldest = entries.entries.firstOrNull()?.key ?: break
            entries.remove(oldest)
        }
    }

    @Synchronized
    fun pendingFor(taskId: String): Pending? = entries[taskId]

    @Synchronized
    fun clear(taskId: String, commandId: String) {
        val current = entries[taskId] ?: return
        if (current.commandId == commandId) entries.remove(taskId)
    }

    @Synchronized
    fun all(): List<Pending> = entries.values.toList()
}
