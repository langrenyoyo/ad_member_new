package com.example.idiomquiz.security

/** SDK codes are unrelated to HTTP status or SAF's business success code 200. */
internal object AliyunSdkContract {
    const val SUCCESS = 10000
    const val MIN_INIT_INTERVAL_MS = 2100L

    fun errorMessage(code: Int): String = when (code) {
        10001 -> "设备校验尚未初始化"
        10002 -> "设备校验缺少必要的网络权限"
        10004, 10005, 10006, 10008 -> "设备校验网络异常，请检查网络后重试"
        10009 -> "设备校验服务尚未配置"
        10012 -> "设备校验组件与应用配置不匹配，请联系管理员"
        10013 -> "设备校验原生组件加载失败，请使用受支持的真机"
        else -> "设备校验失败（$code），请稍后重试"
    }

    fun checkedToken(code: Int, token: String?): String {
        check(code == SUCCESS) { errorMessage(code) }
        check(!token.isNullOrBlank() && token.length in 10..16384) { "设备校验未返回有效凭证" }
        // UF weak-network tokens are documented valid inputs; never strip or truncate them.
        return token
    }
}
