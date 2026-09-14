package com.hanlinh.androidbrain.perception

data class NotificationSnapshot(
    val packageName: String,
    val title: String?,
    val text: String?,
    val postedAtMs: Long,
)
