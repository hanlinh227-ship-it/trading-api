package com.hanlinh.androidbrain.mapping

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

interface AppMappingStore {
    fun recordScreen(screen: ScreenState, verified: Boolean)
    fun recordTransition(edge: TransitionEdge, verified: Boolean)
    fun screens(packageName: String): List<ScreenState>
    fun transitions(packageName: String): List<TransitionEdge>
}

class InMemoryAppMappingStore : AppMappingStore {
    private val screenByPackage = mutableMapOf<String, LinkedHashMap<String, ScreenState>>()
    private val edgeByPackage = mutableMapOf<String, LinkedHashMap<String, TransitionEdge>>()

    @Synchronized override fun recordScreen(screen: ScreenState, verified: Boolean) {
        if (!verified) return
        screenByPackage.getOrPut(screen.packageName) { linkedMapOf() }[screen.screenId] = screen
    }

    @Synchronized override fun recordTransition(edge: TransitionEdge, verified: Boolean) {
        if (!verified) return
        edgeByPackage.getOrPut(edge.packageName) { linkedMapOf() }[edge.key] = edge
    }

    @Synchronized override fun screens(packageName: String): List<ScreenState> =
        screenByPackage[packageName]?.values?.toList().orEmpty()

    @Synchronized override fun transitions(packageName: String): List<TransitionEdge> =
        edgeByPackage[packageName]?.values?.toList().orEmpty()
}

class SharedPreferencesAppMappingStore(
    context: Context,
    private val maxScreensPerApp: Int = 80,
    private val maxTransitionsPerApp: Int = 240,
) : AppMappingStore {
    private val prefs = context.applicationContext.getSharedPreferences("android_brain_v5_app_mapping", Context.MODE_PRIVATE)

    override fun recordScreen(screen: ScreenState, verified: Boolean) {
        if (!verified) return
        val updated = (screens(screen.packageName).filterNot { it.screenId == screen.screenId } + screen)
            .sortedWith(compareByDescending<ScreenState> { it.confidence }.thenByDescending { it.lastVerifiedAtMs })
            .take(maxScreensPerApp)
        prefs.edit().putString(screenKey(screen.packageName), encodeScreens(updated).toString()).apply()
    }

    override fun recordTransition(edge: TransitionEdge, verified: Boolean) {
        if (!verified) return
        val updated = (transitions(edge.packageName).filterNot { it.key == edge.key } + edge)
            .sortedWith(compareByDescending<TransitionEdge> { it.confidence }.thenByDescending { it.lastVerifiedAtMs })
            .take(maxTransitionsPerApp)
        prefs.edit().putString(edgeKey(edge.packageName), encodeEdges(updated).toString()).apply()
    }

    override fun screens(packageName: String): List<ScreenState> {
        val raw = prefs.getString(screenKey(packageName), null) ?: return emptyList()
        return runCatching { decodeScreens(JSONArray(raw), packageName) }.getOrDefault(emptyList())
    }

    override fun transitions(packageName: String): List<TransitionEdge> {
        val raw = prefs.getString(edgeKey(packageName), null) ?: return emptyList()
        return runCatching { decodeEdges(JSONArray(raw), packageName) }.getOrDefault(emptyList())
    }

    private fun screenKey(packageName: String) = "screens:$packageName"
    private fun edgeKey(packageName: String) = "edges:$packageName"

    private fun encodeScreens(items: List<ScreenState>) = JSONArray().also { array ->
        items.forEach { screen ->
            array.put(JSONObject()
                .put("screenId", screen.screenId)
                .put("semanticSignature", screen.semanticSignature)
                .put("visualSignature", screen.visualSignature ?: JSONObject.NULL)
                .put("activityHint", screen.activityHint ?: JSONObject.NULL)
                .put("version", screen.lastVerifiedAppVersion ?: JSONObject.NULL)
                .put("confidence", screen.confidence)
                .put("firstSeenAtMs", screen.firstSeenAtMs)
                .put("lastVerifiedAtMs", screen.lastVerifiedAtMs))
        }
    }

    private fun decodeScreens(array: JSONArray, packageName: String): List<ScreenState> = buildList {
        for (index in 0 until array.length()) {
            val obj = array.getJSONObject(index)
            add(ScreenState(
                screenId = obj.getString("screenId"),
                packageName = packageName,
                activityHint = obj.optString("activityHint").takeIf { it.isNotBlank() && it != "null" },
                semanticSignature = obj.getString("semanticSignature"),
                visualSignature = obj.optString("visualSignature").takeIf { it.isNotBlank() && it != "null" },
                lastVerifiedAppVersion = obj.optString("version").takeIf { it.isNotBlank() && it != "null" },
                confidence = obj.getDouble("confidence"),
                firstSeenAtMs = obj.getLong("firstSeenAtMs"),
                lastVerifiedAtMs = obj.getLong("lastVerifiedAtMs"),
            ))
        }
    }

    private fun encodeEdges(items: List<TransitionEdge>) = JSONArray().also { array ->
        items.forEach { edge ->
            array.put(JSONObject()
                .put("from", edge.fromScreenId)
                .put("action", edge.actionKey)
                .put("to", edge.toScreenId)
                .put("success", edge.successCount)
                .put("failure", edge.failureCount)
                .put("medianLatencyMs", edge.medianLatencyMs)
                .put("confidence", edge.confidence)
                .put("lastVerifiedAtMs", edge.lastVerifiedAtMs))
        }
    }

    private fun decodeEdges(array: JSONArray, packageName: String): List<TransitionEdge> = buildList {
        for (index in 0 until array.length()) {
            val obj = array.getJSONObject(index)
            add(TransitionEdge(
                packageName = packageName,
                fromScreenId = obj.getString("from"),
                actionKey = obj.getString("action"),
                toScreenId = obj.getString("to"),
                successCount = obj.getInt("success"),
                failureCount = obj.getInt("failure"),
                medianLatencyMs = obj.getLong("medianLatencyMs"),
                confidence = obj.getDouble("confidence"),
                lastVerifiedAtMs = obj.getLong("lastVerifiedAtMs"),
            ))
        }
    }
}
