package com.hanlinh.bybitmonitor.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureTokenStore(context:Context) {
    private val prefs=context.applicationContext.getSharedPreferences("monitor_secure",Context.MODE_PRIVATE)
    private val alias="bybit_monitor_token_aes_v1"
    private val ks=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
    private fun key():SecretKey {
        (ks.getKey(alias,null) as? SecretKey)?.let{return it}
        val kg=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore")
        kg.init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build())
        return kg.generateKey()
    }
    fun save(token:String){val c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());val iv=Base64.encodeToString(c.iv,Base64.NO_WRAP);val ct=Base64.encodeToString(c.doFinal(token.toByteArray()),Base64.NO_WRAP);prefs.edit().putString("iv",iv).putString("ct",ct).apply()}
    fun load():String?=try{val iv=prefs.getString("iv",null)?:return null;val ct=prefs.getString("ct",null)?:return null;val c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(iv,Base64.NO_WRAP)));String(c.doFinal(Base64.decode(ct,Base64.NO_WRAP)))}catch(_:Exception){null}
    fun clear(){prefs.edit().clear().apply()}
}
