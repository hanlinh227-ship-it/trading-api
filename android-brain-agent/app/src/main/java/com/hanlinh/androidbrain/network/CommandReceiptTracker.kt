package com.hanlinh.androidbrain.network

class CommandReceiptTracker(
    private val maxEntries: Int = 64,
) {
    init {
        require(maxEntries > 0) { "maxEntries must be positive" }
    }

    private val receipts = LinkedHashMap<String, GatewayClient.TaskResult>()

    @Synchronized
    fun record(result: GatewayClient.TaskResult) {
        receipts.remove(result.commandId)
        receipts[result.commandId] = result
        while (receipts.size > maxEntries) {
            val oldest = receipts.entries.firstOrNull()?.key ?: break
            receipts.remove(oldest)
        }
    }

    @Synchronized
    fun resultFor(commandId: String): GatewayClient.TaskResult? = receipts[commandId]
}
