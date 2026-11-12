package com.example.idiomquiz.ui

/** A transport failure must not replace a previously loaded policy with a business denial. */
internal fun onboardingBlocks(loaded: Boolean, blockCode: String?, invite: Boolean, usage: Boolean, alipay: Boolean): Boolean =
    !loaded || blockCode != null || invite || usage || alipay

internal fun onboardingFailureCode(status: Int?, code: String?): String? = when (status) {
    401 -> "SESSION_EXPIRED"
    403 -> code ?: "ACCESS_DENIED"
    else -> null
}

internal fun onboardingFailureMessage(status: Int?, message: String?): String = when (status) {
    404 -> "服务暂不支持账户设置，请联系管理员更新服务后重试。"
    else -> message ?: "账户设置加载失败，请稍后重试。"
}
