package com.example.idiomquiz.ui

internal const val DEFAULT_AD_UNAVAILABLE_MESSAGE = "暂时无法获得广告"

internal fun adFailureMessage(configured: String?): String =
    configured?.trim()?.takeIf { it.isNotEmpty() && it.length <= 200 }
        ?: DEFAULT_AD_UNAVAILABLE_MESSAGE
