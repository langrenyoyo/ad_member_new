package com.example.idiomquiz.security

import android.content.Context
import android.os.Build
import android.os.SystemClock
import com.example.idiomquiz.BuildConfig
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.lang.reflect.Proxy

/** Reflection keeps the optional, console-distributed AAR out of SDK-free builds. */
object AliyunDeviceRiskManager {
    private const val CONSENT_VERSION = 1
    private var initialization: CompletableDeferred<Int>? = null
    private var initStartedAt = 0L

    fun hasConsent(context: Context): Boolean = context.applicationContext
        .getSharedPreferences("device_risk_consent", Context.MODE_PRIVATE)
        .getInt("version", 0) == CONSENT_VERSION

    fun acceptConsent(context: Context) {
        context.applicationContext.getSharedPreferences("device_risk_consent", Context.MODE_PRIVATE)
            .edit().putInt("version", CONSENT_VERSION).apply()
    }

    fun isAvailable(): Boolean = runCatching {
        listOf("SecurityDevice", "SecurityToken", "SecurityInitListener").forEach {
            Class.forName("net.security.device.api.$it")
        }
        true
    }.getOrDefault(false)

    fun requireConfigured() {
        check(BuildConfig.ALIYUN_DEVICE_RISK_APP_KEY.isNotBlank()) { "设备校验服务尚未配置，请联系管理员" }
        check(isAvailable()) { "当前应用未安装设备校验组件，请更新应用" }
        check(Build.SUPPORTED_ABIS.any { it == "arm64-v8a" || it == "armeabi-v7a" || it == "armeabi" }) {
            "设备校验需要 ARM 真机，不支持当前设备架构"
        }
    }

    @Synchronized
    private fun initialize(context: Context): CompletableDeferred<Int> {
        initialization?.let { return it }
        val completion = CompletableDeferred<Int>()
        initialization = completion
        initStartedAt = SystemClock.elapsedRealtime()
        try {
            val deviceClass = Class.forName("net.security.device.api.SecurityDevice")
            val listenerClass = Class.forName("net.security.device.api.SecurityInitListener")
            val listener = Proxy.newProxyInstance(listenerClass.classLoader, arrayOf(listenerClass)) { proxy, method, args ->
                when (method.name) {
                    "onInitFinish" -> { completion.complete((args?.firstOrNull() as? Number)?.toInt() ?: -1); null }
                    "hashCode" -> System.identityHashCode(proxy)
                    "equals" -> proxy === args?.firstOrNull()
                    "toString" -> "AliyunInitListener"
                    else -> null
                }
            }
            // Keep basic/changeable IDs, exclude immutable IDs and extra app/Wi-Fi information.
            val excluded = deviceClass.getField("NO_IDENTIFY_DEVICE_DATA").getInt(null) or
                deviceClass.getField("NO_EXTRA_DEVICE_DATA").getInt(null)
            val options = hashMapOf("IPv6" to "0", "DataType" to excluded.toString())
            deviceClass.getMethod("initWithOptions", Context::class.java, String::class.java,
                Map::class.java, listenerClass).invoke(deviceClass.getMethod("getInstance").invoke(null),
                context.applicationContext, BuildConfig.ALIYUN_DEVICE_RISK_APP_KEY, options, listener)
        } catch (_: Exception) {
            completion.completeExceptionally(IllegalStateException("设备校验组件初始化失败，请检查应用配置"))
        } catch (_: LinkageError) {
            completion.completeExceptionally(IllegalStateException("设备校验组件无法加载，请更新应用"))
        }
        // Even on failure, do not reinitialize an SDK which requires once-per-process init.
        return completion
    }

    suspend fun getDeviceToken(context: Context, bizId: String): String = withContext(Dispatchers.IO) {
        check(hasConsent(context)) { "请先同意设备安全检测说明" }
        require(bizId.isNotBlank()) { "设备校验业务编号不能为空" }
        requireConfigured()
        val code = withTimeoutOrNull(10_000) { initialize(context).await() }
            ?: error("设备校验初始化超时，请检查网络后重试")
        check(code == AliyunSdkContract.SUCCESS) { AliyunSdkContract.errorMessage(code) }
        val wait = AliyunSdkContract.MIN_INIT_INTERVAL_MS - (SystemClock.elapsedRealtime() - initStartedAt)
        if (wait > 0) delay(wait)
        val result = try {
            val type = Class.forName("net.security.device.api.SecurityDevice")
            type.getMethod("getDeviceToken", String::class.java)
                .invoke(type.getMethod("getInstance").invoke(null), bizId)
        } catch (_: Exception) { error("设备校验凭证获取失败，请稍后重试") }
        catch (_: LinkageError) { error("设备校验组件无法加载，请更新应用") }
        check(result != null) { "设备校验未返回凭证" }
        val tokenCode = (result.javaClass.getField("code").get(result) as Number).toInt()
        val token = result.javaClass.getField("token").get(result) as? String
        AliyunSdkContract.checkedToken(tokenCode, token)
    }
}
