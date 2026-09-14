package com.hanlinh.androidbrain.security

import android.util.Base64
import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.PublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import org.json.JSONObject

object EcJwk {
    fun publicKeyFromJwk(jwkJson: String): PublicKey {
        val jwk = JSONObject(jwkJson)
        require(jwk.optString("kty") == "EC") { "unsupported key type" }
        require(jwk.optString("crv") == "P-256") { "unsupported curve" }
        val x = BigInteger(1, Base64.decode(jwk.getString("x"), Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING))
        val y = BigInteger(1, Base64.decode(jwk.getString("y"), Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING))
        val parameters = AlgorithmParameters.getInstance("EC").apply { init(ECGenParameterSpec("secp256r1")) }
            .getParameterSpec(ECParameterSpec::class.java)
        return KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(ECPoint(x, y), parameters))
    }
}
