package com.hanlinh.androidbrain.network

import java.net.InetAddress
import java.net.UnknownHostException
import okhttp3.Dns
import okhttp3.OkHttpClient
import okhttp3.dnsoverhttps.DnsOverHttps
import okhttp3.HttpUrl.Companion.toHttpUrl

class FallbackDns(
    private val primary: Dns,
    private val fallback: Dns,
) : Dns {
    override fun lookup(hostname: String): List<InetAddress> {
        return try {
            primary.lookup(hostname).ifEmpty { fallback.lookup(hostname) }
        } catch (_: UnknownHostException) {
            fallback.lookup(hostname)
        }
    }
}

object GatewayDns {
    fun resilient(): Dns {
        val bootstrap = OkHttpClient.Builder().build()

        val google = DnsOverHttps.Builder()
            .client(bootstrap)
            .url("https://dns.google/dns-query".toHttpUrl())
            .bootstrapDnsHosts(
                InetAddress.getByName("8.8.8.8"),
                InetAddress.getByName("8.8.4.4"),
            )
            .build()

        val cloudflare = DnsOverHttps.Builder()
            .client(bootstrap)
            .url("https://cloudflare-dns.com/dns-query".toHttpUrl())
            .bootstrapDnsHosts(
                InetAddress.getByName("1.1.1.1"),
                InetAddress.getByName("1.0.0.1"),
            )
            .build()

        return FallbackDns(Dns.SYSTEM, FallbackDns(google, cloudflare))
    }
}
