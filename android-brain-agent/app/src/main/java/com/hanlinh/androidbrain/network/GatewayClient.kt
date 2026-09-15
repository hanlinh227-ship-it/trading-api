package com.hanlinh.androidbrain.network

import com.hanlinh.androidbrain.BuildConfig
import com.hanlinh.androidbrain.perception.AccessibilitySnapshot
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.CommandEnvelope
import com.hanlinh.androidbrain.protocol.TypedActionCodec
import java.time.Instant
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject

class GatewayClient(
    private val baseUrl: String = BuildConfig.GATEWAY_BASE_URL.trimEnd('/'),
    private val http: OkHttpClient = OkHttpClient.Builder()
        .dns(GatewayDns.resilient())
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build(),
) {
    data class PairStart(val challenge: String, val expiresAt: Long, val recovery: Boolean)
    data class PairComplete(val deviceToken: String, val gatewayPublicKeyJwk: String)
    data class TaskResult(val commandId: String, val status: String, val detail: String? = null)
    data class V5Checkpoint(
        val stepCount: Int,
        val epoch: Int,
        val checkpointCount: Int,
        val screenSignature: String? = null,
        val selectedSkillId: String? = null,
        val metrics: Map<String, Double> = emptyMap(),
    ) {
        init {
            require(stepCount >= 0)
            require(epoch >= 0)
            require(checkpointCount >= 0)
        }
    }
    data class LocalObservationFact(
        val kind: String,
        val nodeId: String,
        val relatedNodeId: String? = null,
    )
    data class TaskStepResponse(
        val status: String,
        val stepCount: Int,
        val recoveryCount: Int,
        val epoch: Int = 0,
        val epochStepCount: Int = 0,
        val checkpointCount: Int = 0,
        val persistence: String? = null,
        val plannerMode: String? = null,
        val commandId: String? = null,
        val failureCode: String? = null,
    )

    fun pairStart(deviceId: String, devicePublicKey: String): PairStart {
        val body = JSONObject().put("deviceId", deviceId).put("devicePublicKey", devicePublicKey)
        val json = post("/v1/pair/start", body, null)
        return PairStart(
            challenge = json.getString("challenge"),
            expiresAt = json.getLong("expiresAt"),
            recovery = json.optBoolean("recovery", false),
        )
    }

    fun pairComplete(deviceId: String, challenge: String, signature: String, recovery: Boolean): PairComplete {
        val body = JSONObject()
            .put("deviceId", deviceId)
            .put("challenge", challenge)
            .put("signature", signature)
            .put("recovery", recovery)
        val json = post("/v1/pair/complete", body, null)
        return PairComplete(json.getString("deviceToken"), json.getJSONObject("gatewayPublicKeyJwk").toString())
    }

    fun health(): JSONObject {
        val request = Request.Builder().url("$baseUrl/health").get().build()
        return executeJson(request)
    }

    fun nextCommand(deviceId: String, token: String): CommandEnvelope? {
        val request = Request.Builder()
            .url("$baseUrl/v1/device/${encodeSegment(deviceId)}/next")
            .header("Authorization", "Bearer $token")
            .get()
            .build()
        val json = executeJson(request)
        if (json.isNull("command")) return null
        return parseCommand(json.getJSONObject("command"))
    }

    fun openCommandSocket(deviceId: String, token: String, listener: WebSocketListener): WebSocket {
        val request = Request.Builder()
            .url(CommandSocketProtocol.socketUrl(baseUrl, deviceId))
            .header("Authorization", "Bearer $token")
            .build()
        return http.newWebSocket(request, listener)
    }

    fun postResult(deviceId: String, token: String, result: TaskResult) {
        val body = JSONObject()
            .put("commandId", result.commandId)
            .put("status", result.status)
            .put("detail", result.detail)
        post("/v1/device/${encodeSegment(deviceId)}/result", body, token)
    }

    fun taskStatus(deviceId: String, authorizationToken: String, taskId: String): JSONObject =
        get(
            "/v1/device/${encodeSegment(deviceId)}/tasks/${encodeSegment(taskId)}",
            authorizationToken,
        )

    fun cancelTask(deviceId: String, authorizationToken: String, taskId: String): JSONObject =
        post(
            "/v1/device/${encodeSegment(deviceId)}/tasks/${encodeSegment(taskId)}/cancel",
            JSONObject(),
            authorizationToken,
        )

    fun postCheckpoint(
        deviceId: String,
        token: String,
        taskId: String,
        checkpoint: V5Checkpoint,
    ): JSONObject {
        val metrics = JSONObject()
        checkpoint.metrics.forEach { (key, value) -> metrics.put(key, value) }
        val body = JSONObject()
            .put("stepCount", checkpoint.stepCount)
            .put("epoch", checkpoint.epoch)
            .put("checkpointCount", checkpoint.checkpointCount)
            .put("screenSignature", checkpoint.screenSignature ?: JSONObject.NULL)
            .put("selectedSkillId", checkpoint.selectedSkillId ?: JSONObject.NULL)
            .put("metrics", metrics)
        return post(
            "/v1/device/${encodeSegment(deviceId)}/tasks/${encodeSegment(taskId)}/checkpoint",
            body,
            token,
        )
    }

    fun requestMicroPlan(
        deviceId: String,
        token: String,
        taskId: String,
        observation: JSONObject,
    ): JSONObject = post(
        "/v1/device/${encodeSegment(deviceId)}/tasks/${encodeSegment(taskId)}/micro-plan",
        JSONObject().put("observation", observation),
        token,
    )

    fun requestRecovery(
        deviceId: String,
        token: String,
        taskId: String,
        observation: JSONObject,
        reason: String,
    ): JSONObject = post(
        "/v1/device/${encodeSegment(deviceId)}/tasks/${encodeSegment(taskId)}/recovery",
        JSONObject()
            .put("observation", observation)
            .put("reason", reason.take(96)),
        token,
    )

    fun postTaskStep(
        deviceId: String,
        token: String,
        taskId: String,
        observation: AccessibilitySnapshot,
        previousResult: TaskResult?,
        imageDataUrl: String? = null,
        localFacts: List<LocalObservationFact> = emptyList(),
    ): TaskStepResponse {
        val body = JSONObject()
            .put("taskId", taskId)
            .put("observation", observationJson(observation, localFacts))
        if (previousResult != null) {
            body.put(
                "previousResult",
                JSONObject()
                    .put("commandId", previousResult.commandId)
                    .put("status", previousResult.status)
                    .put("code", previousResult.detail),
            )
        }
        if (!imageDataUrl.isNullOrBlank()) body.put("imageDataUrl", imageDataUrl)
        val json = post("/v1/device/${encodeSegment(deviceId)}/task-step", body, token)
        return TaskStepResponse(
            status = json.optString("status", "UNKNOWN"),
            stepCount = json.optInt("stepCount", 0),
            recoveryCount = json.optInt("recoveryCount", 0),
            epoch = json.optInt("epoch", 0),
            epochStepCount = json.optInt("epochStepCount", 0),
            checkpointCount = json.optInt("checkpointCount", 0),
            persistence = json.optString("persistence").takeIf { it.isNotBlank() },
            plannerMode = json.optString("plannerMode").takeIf { it.isNotBlank() },
            commandId = json.optString("commandId").takeIf { it.isNotBlank() },
            failureCode = json.optString("failureCode").takeIf { it.isNotBlank() },
        )
    }

    internal fun observationJson(
        observation: AccessibilitySnapshot,
        localFacts: List<LocalObservationFact> = emptyList(),
    ): JSONObject {
        val nodes = JSONArray()
        observation.nodes.take(MAX_OBSERVATION_NODES).forEach { node ->
            val bounds = JSONObject()
                .put("left", node.bounds.left)
                .put("top", node.bounds.top)
                .put("right", node.bounds.right)
                .put("bottom", node.bounds.bottom)
            val item = JSONObject()
                .put("nodeId", node.nodeId)
                .put("resourceId", node.resourceId)
                .put("text", node.text)
                .put("contentDescription", node.contentDescription)
                .put("className", node.className)
                .put("enabled", node.enabled)
                .put("clickable", node.clickable)
                .put("longClickable", node.longClickable)
                .put("editable", node.editable)
                .put("scrollable", node.scrollable)
                .put("checkable", node.checkable)
                .put("checked", node.checked)
                .put("selected", node.selected)
                .put("focused", node.focused)
                .put("visibleToUser", node.visibleToUser)
                .put("bounds", bounds)
            nodes.put(item)
        }
        val facts = JSONArray()
        localFacts.take(MAX_LOCAL_FACTS).forEach { fact ->
            if (fact.kind !in ALLOWED_LOCAL_FACT_KINDS || !fact.nodeId.startsWith("n:")) return@forEach
            facts.put(
                JSONObject()
                    .put("kind", fact.kind)
                    .put("nodeId", fact.nodeId)
                    .put("relatedNodeId", fact.relatedNodeId),
            )
        }
        val regions = JSONObject()
        observation.regionHashes.toSortedMap().forEach { (name, hash) ->
            regions.put(name.take(64), hash.take(192))
        }
        return JSONObject()
            .put("packageName", observation.packageName)
            .put("windowTitle", observation.windowTitle)
            .put("fingerprint", observation.fingerprint())
            .put("screenWidth", observation.screenWidth ?: JSONObject.NULL)
            .put("screenHeight", observation.screenHeight ?: JSONObject.NULL)
            .put("orientation", observation.orientation ?: JSONObject.NULL)
            .put("screenshotAvailable", !observation.screenshotHash.isNullOrBlank())
            .put("screenshotHash", observation.screenshotHash ?: JSONObject.NULL)
            .put("regionHashes", regions)
            .put("nodes", nodes)
            .put("localFacts", facts)
    }

    private fun get(path: String, token: String?): JSONObject {
        val builder = Request.Builder().url("$baseUrl$path").get()
        if (token != null) builder.header("Authorization", "Bearer $token")
        return executeJson(builder.build())
    }

    private fun post(path: String, body: JSONObject, token: String?): JSONObject {
        val builder = Request.Builder()
            .url("$baseUrl$path")
            .post(body.toString().toRequestBody(JSON_MEDIA_TYPE))
        if (token != null) builder.header("Authorization", "Bearer $token")
        return executeJson(builder.build())
    }

    private fun executeJson(request: Request): JSONObject {
        http.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw GatewayException(response.code, text.take(1000))
            return if (text.isBlank()) JSONObject() else JSONObject(text)
        }
    }

    internal fun parseCommand(json: JSONObject): CommandEnvelope {
        val schema = json.getInt("schema")
        require(schema == 1 || schema == 2) { "Unsupported command schema" }
        val scopeJson = json.optJSONArray("capabilityScope") ?: JSONArray()
        val scope = buildSet {
            for (i in 0 until scopeJson.length()) add(scopeJson.getString(i))
        }
        val typedAction = if (schema == 2) {
            val actionObject = json.optJSONObject("action")
                ?: throw IllegalArgumentException("Schema-2 command requires action")
            TypedActionCodec.decode(actionObject.toString())
        } else null
        return CommandEnvelope(
            schema = schema,
            commandId = json.getString("commandId"),
            deviceId = json.getString("deviceId"),
            issuedAt = Instant.parse(json.getString("issuedAt")),
            expiresAt = Instant.parse(json.getString("expiresAt")),
            nonce = json.getString("nonce"),
            goal = if (schema == 1) json.getString("goal") else json.optString("goal", ""),
            capabilityScope = scope,
            riskClass = RiskClass.valueOf(json.getString("riskClass")),
            signature = json.getString("signature"),
            taskId = if (schema == 2) json.getString("taskId") else null,
            action = typedAction,
        )
    }

    private fun encodeSegment(value: String): String = java.net.URLEncoder.encode(value, Charsets.UTF_8.name())

    class GatewayException(val statusCode: Int, message: String) : RuntimeException(message)

    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
        private const val MAX_OBSERVATION_NODES = 80
        private const val MAX_LOCAL_FACTS = 40
        private val ALLOWED_LOCAL_FACT_KINDS = setOf("UNKNOWN_NUMBER_CONFIRMED")
    }
}
