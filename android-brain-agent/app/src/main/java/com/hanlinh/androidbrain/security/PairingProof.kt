package com.hanlinh.androidbrain.security

import java.io.ByteArrayOutputStream

object PairingProof {
    fun payload(deviceId: String, challenge: String): ByteArray =
        "android-brain-pair-v2\n$deviceId\n$challenge".toByteArray(Charsets.UTF_8)

    fun derToP1363(der: ByteArray): ByteArray {
        var p = 0
        require(der[p++].toInt() and 0xff == 0x30) { "Not a DER sequence" }
        val sequenceLength = readLength(der, p)
        p = sequenceLength.next
        require(sequenceLength.length == der.size - p) { "Unexpected DER sequence length" }

        require(der[p++].toInt() and 0xff == 0x02) { "Missing r integer" }
        val rLength = readLength(der, p)
        p = rLength.next
        val r = der.copyOfRange(p, p + rLength.length)
        p += rLength.length

        require(der[p++].toInt() and 0xff == 0x02) { "Missing s integer" }
        val sLength = readLength(der, p)
        p = sLength.next
        val s = der.copyOfRange(p, p + sLength.length)
        p += sLength.length
        require(p == der.size) { "Trailing DER data" }

        return toFixed32(r) + toFixed32(s)
    }

    fun p1363ToDer(raw: ByteArray): ByteArray {
        require(raw.size == 64) { "P-256 signature must be 64 bytes" }
        val r = normalizeInteger(raw.copyOfRange(0, 32))
        val s = normalizeInteger(raw.copyOfRange(32, 64))
        val payload = ByteArrayOutputStream().apply {
            write(0x02); writeLength(this, r.size); write(r)
            write(0x02); writeLength(this, s.size); write(s)
        }.toByteArray()
        return ByteArrayOutputStream().apply {
            write(0x30); writeLength(this, payload.size); write(payload)
        }.toByteArray()
    }

    private data class LengthResult(val length: Int, val next: Int)

    private fun readLength(data: ByteArray, offset: Int): LengthResult {
        val first = data[offset].toInt() and 0xff
        if (first < 0x80) return LengthResult(first, offset + 1)
        val count = first and 0x7f
        require(count in 1..4) { "Unsupported DER length" }
        var value = 0
        repeat(count) { i -> value = (value shl 8) or (data[offset + 1 + i].toInt() and 0xff) }
        return LengthResult(value, offset + 1 + count)
    }

    private fun writeLength(out: ByteArrayOutputStream, length: Int) {
        if (length < 0x80) {
            out.write(length)
            return
        }
        val bytes = mutableListOf<Int>()
        var value = length
        while (value > 0) {
            bytes.add(0, value and 0xff)
            value = value ushr 8
        }
        out.write(0x80 or bytes.size)
        bytes.forEach(out::write)
    }

    private fun toFixed32(input: ByteArray): ByteArray {
        var first = 0
        while (first < input.lastIndex && input[first] == 0.toByte()) first++
        val stripped = input.copyOfRange(first, input.size)
        require(stripped.size <= 32) { "ECDSA integer too large" }
        return ByteArray(32 - stripped.size) + stripped
    }

    private fun normalizeInteger(input: ByteArray): ByteArray {
        var first = 0
        while (first < input.lastIndex && input[first] == 0.toByte()) first++
        val stripped = input.copyOfRange(first, input.size)
        return if ((stripped[0].toInt() and 0x80) != 0) byteArrayOf(0) + stripped else stripped
    }
}
