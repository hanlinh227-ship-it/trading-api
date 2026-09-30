package com.hanlinh.androidbrain.mapping

data class TransitionEdge(
    val packageName: String,
    val fromScreenId: String,
    val actionKey: String,
    val toScreenId: String,
    val successCount: Int,
    val failureCount: Int,
    val medianLatencyMs: Long,
    val confidence: Double,
    val lastVerifiedAtMs: Long,
) {
    init {
        require(packageName.isNotBlank())
        require(fromScreenId.isNotBlank())
        require(actionKey.isNotBlank())
        require(toScreenId.isNotBlank())
        require(successCount >= 0 && failureCount >= 0)
        require(medianLatencyMs >= 0)
        require(confidence in 0.0..1.0)
        require(lastVerifiedAtMs >= 0)
    }

    val key: String get() = "$fromScreenId|$actionKey|$toScreenId"
}

class TransitionGraph {
    private val edges = linkedMapOf<String, TransitionEdge>()
    @Synchronized fun put(edge: TransitionEdge) { edges[edge.key] = edge }
    @Synchronized fun all(): List<TransitionEdge> = edges.values.toList()
    @Synchronized fun outgoing(screenId: String): List<TransitionEdge> = edges.values.filter { it.fromScreenId == screenId }
}
