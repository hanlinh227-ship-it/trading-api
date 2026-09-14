package com.hanlinh.androidbrain.network

import android.content.Context
import android.util.Base64
import com.hanlinh.androidbrain.security.DeviceIdentity
import com.hanlinh.androidbrain.security.EcJwk
import com.hanlinh.androidbrain.security.SecureStore
import org.json.JSONObject

data class PairingData(
    val deviceId: String,
    val deviceToken: String,
    val gatewayPublicKeyBase64: String,
)

class PairingRepository(
    context: Context,
    private val client: GatewayClient = GatewayClient(),
) {
    companion object { private const val KEY = "pairing_v1" }
    private val store = SecureStore(context.applicationContext)

    fun pair(): PairingData {
        val deviceId = DeviceIdentity.deviceId()
        val start = client.pairStart(deviceId, DeviceIdentity.publicKeyBase64())
        val complete = client.pairComplete(deviceId, start.code)
        val gatewayKey = EcJwk.publicKeyFromJwk(complete.gatewayPublicKeyJwk)
        val data = PairingData(
            deviceId = deviceId,
            deviceToken = complete.deviceToken,
            gatewayPublicKeyBase64 = Base64.encodeToString(gatewayKey.encoded, Base64.NO_WRAP),
        )
        save(data)
        return data
    }

    fun load(): PairingData? {
        val raw = store.get(KEY) ?: return null
        return try {
            val json = JSONObject(raw)
            PairingData(
                deviceId = json.getString("deviceId"),
                deviceToken = json.getString("deviceToken"),
                gatewayPublicKeyBase64 = json.getString("gatewayPublicKeyBase64"),
            )
        } catch (_: Throwable) { null }
    }

    fun clear() = store.remove(KEY)

    private fun save(data: PairingData) {
        store.put(KEY, JSONObject()
            .put("deviceId", data.deviceId)
            .put("deviceToken", data.deviceToken)
            .put("gatewayPublicKeyBase64", data.gatewayPublicKeyBase64)
            .toString())
    }
}
