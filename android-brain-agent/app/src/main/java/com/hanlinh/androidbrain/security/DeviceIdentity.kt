package com.hanlinh.androidbrain.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec

object DeviceIdentity {
    const val KEY_ALIAS = "android_brain_device_identity_v1"

    fun getOrCreateKeyPair(): KeyPair {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existingPrivate = keyStore.getKey(KEY_ALIAS, null)
        val existingPublic = keyStore.getCertificate(KEY_ALIAS)?.publicKey
        if (existingPrivate is java.security.PrivateKey && existingPublic != null) {
            return KeyPair(existingPublic, existingPrivate)
        }

        val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY,
        )
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setUserAuthenticationRequired(false)
            .build()
        generator.initialize(spec)
        return generator.generateKeyPair()
    }

    fun deviceId(): String {
        val publicBytes = getOrCreateKeyPair().public.encoded
        val digest = MessageDigest.getInstance("SHA-256").digest(publicBytes)
        return digest.take(16).joinToString("") { "%02x".format(it) }
    }

    fun publicKeyBase64(): String = Base64.encodeToString(getOrCreateKeyPair().public.encoded, Base64.NO_WRAP)

    fun signPairingChallenge(deviceId: String, challenge: String): String {
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(getOrCreateKeyPair().private)
        signer.update(PairingProof.payload(deviceId, challenge))
        val p1363 = PairingProof.derToP1363(signer.sign())
        return Base64.encodeToString(p1363, Base64.NO_WRAP)
    }
}
