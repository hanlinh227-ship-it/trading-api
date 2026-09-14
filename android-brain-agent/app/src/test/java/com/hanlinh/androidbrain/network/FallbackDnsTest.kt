package com.hanlinh.androidbrain.network

import java.net.InetAddress
import java.net.UnknownHostException
import okhttp3.Dns
import org.junit.Assert.assertEquals
import org.junit.Test

class FallbackDnsTest {
    @Test
    fun usesFallbackWhenPrimaryCannotResolve() {
        val primary = Dns { throw UnknownHostException("blocked") }
        val fallback = Dns { listOf(InetAddress.getByName("203.0.113.7")) }
        val dns = FallbackDns(primary, fallback)

        val result = dns.lookup("android-brain-agent-gateway.hanlinh227.workers.dev")

        assertEquals("203.0.113.7", result.single().hostAddress)
    }

    @Test
    fun keepsPrimaryWhenSystemDnsWorks() {
        val primary = Dns { listOf(InetAddress.getByName("198.51.100.9")) }
        val fallback = Dns { throw AssertionError("fallback should not be used") }
        val dns = FallbackDns(primary, fallback)

        val result = dns.lookup("example.test")

        assertEquals("198.51.100.9", result.single().hostAddress)
    }
}
