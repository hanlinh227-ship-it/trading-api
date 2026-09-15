package com.hanlinh.androidbrain.network

import com.hanlinh.androidbrain.agent.PersistencePolicy
import com.hanlinh.androidbrain.policy.RiskClass
import com.hanlinh.androidbrain.protocol.ReadScreen
import java.util.concurrent.CopyOnWriteArrayList
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class V5GatewayClientContractTest {
    private val seen = CopyOnWriteArrayList<Pair<String, String>>()
    private val http = OkHttpClient.Builder()
        .addInterceptor(Interceptor { chain ->
            val request = chain.request()
            seen += request.method to request.url.encodedPath
            val body = when {
                request.url.encodedPath.endsWith("/micro-plan") -> "{\"actions\":[],\"mode\":\"local\"}"
                request.url.encodedPath.endsWith("/recovery") -> "{\"actions\":[],\"mode\":\"recovery\"}"
                else -> "{\"status\":\"RUNNING\"}"
            }
            Response.Builder()
                .request(request)
                .protocol(Protocol.HTTP_1_1)
                .code(200)
                .message("OK")
                .body(body.toResponseBody("application/json".toMediaType()))
                .build()
        })
        .build()

    @Test fun v5TaskMethods_useExplicitAuthenticatedEndpoints() {
        val client = GatewayClient(baseUrl = "https://gateway.example", http = http)
        val observation = JSONObject().put("packageName", "com.example").put("screenSignature", "screen-1")

        client.taskStatus("device-1", "token-1", "task-1")
        client.cancelTask("device-1", "token-1", "task-1")
        client.postCheckpoint(
            "device-1",
            "token-1",
            "task-1",
            GatewayClient.V5Checkpoint(stepCount = 10, epoch = 1, checkpointCount = 2, screenSignature = "screen-1"),
        )
        client.requestMicroPlan("device-1", "token-1", "task-1", observation)
        client.requestRecovery("device-1", "token-1", "task-1", observation, "LOCAL_POSTCONDITION_NOT_MET")

        assertEquals(
            listOf(
                "GET" to "/v1/device/device-1/tasks/task-1",
                "POST" to "/v1/device/device-1/tasks/task-1/cancel",
                "POST" to "/v1/device/device-1/tasks/task-1/checkpoint",
                "POST" to "/v1/device/device-1/tasks/task-1/micro-plan",
                "POST" to "/v1/device/device-1/tasks/task-1/recovery",
            ),
            seen.toList(),
        )
    }

    @Test fun v5TaskMethods_encodePathSegments() {
        val client = GatewayClient(baseUrl = "https://gateway.example", http = http)
        client.taskStatus("device one", "token-1", "task/one")
        val path = seen.single().second
        assertTrue(path.contains("device+one") || path.contains("device%20one"))
        assertTrue(path.contains("task%2Fone"))
    }

    @Test fun localOperatorResponse_preservesAuthoritativeTaskScopeAndBoundedActions() {
        val client = GatewayClient(baseUrl = "https://gateway.example", http = http)
        val response = client.parseTaskStepResponse(
            JSONObject()
                .put("status", "ACTING")
                .put("goal", "keep navigating")
                .put("riskClass", "B")
                .put("capabilityScope", JSONArray().put("ui.navigate").put("ui.write"))
                .put("allowedPackages", JSONArray().put("com.example"))
                .put("persistencePolicy", JSONArray().put("UNTIL_USER_STOP").put("UNTIL_APP_SCOPE_EXIT"))
                .put("localBatchId", "batch-1")
                .put("localActions", JSONArray().put(JSONObject().put("type", "read_screen"))),
        )

        val session = requireNotNull(response.persistentSessionOrNull("task-1"))
        assertEquals("task-1", session.taskId)
        assertEquals(RiskClass.B, session.riskCeiling)
        assertEquals(setOf("ui.navigate", "ui.write"), session.capabilityScope)
        assertEquals(setOf("com.example"), session.allowedPackages)
        assertEquals(
            setOf(PersistencePolicy.UNTIL_USER_STOP, PersistencePolicy.UNTIL_APP_SCOPE_EXIT),
            session.persistence,
        )
        assertEquals(listOf(ReadScreen), response.localActions)
        assertEquals("batch-1", response.localBatchId)
    }
}