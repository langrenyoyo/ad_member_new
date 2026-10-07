package com.example.idiomquiz.security

import android.content.Context
import android.os.Build
import java.io.File
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicBoolean

private const val ALIYUN_DEVICE_RISK_TAG = "AliyunDeviceRisk"

data class DeviceSecurityResult(val blocked: Boolean, val flags: List<String>) {
    val headerValue: String get() = if (flags.isEmpty()) "clean" else flags.joinToString(",")
}

object SecurityGuard {
    fun evaluate(context: Context): DeviceSecurityResult {
        val flags = buildList {
            if (isEmulator()) add("emulator")
            if (hasRootIndicators()) add("root")
            if (hasHookIndicators()) add("hook")
        }
        return DeviceSecurityResult(flags.isNotEmpty(), flags)
    }

    private fun isEmulator(): Boolean {
        val value = listOf(Build.FINGERPRINT, Build.MODEL, Build.MANUFACTURER, Build.PRODUCT, Build.BRAND)
            .joinToString(" ").lowercase()
        return value.contains("generic") || value.contains("emulator") || value.contains("simulator") ||
            value.contains("goldfish") || value.contains("ranchu") || value.contains("sdk_gphone") ||
            value.contains("vbox") || value.contains("genymotion") || Build.HARDWARE.lowercase().contains("ranchu")
    }

    private fun hasRootIndicators(): Boolean = listOf(
        "/system/bin/su", "/system/xbin/su", "/sbin/su", "/data/adb/magisk", "/system/app/Superuser.apk"
    ).any { File(it).exists() }

    private fun hasHookIndicators(): Boolean = listOf(
        "de.robv.android.xposed", "org.meowcat.edxposed", "org.lsposed.manager", "com.frida.server"
    ).any { File("/data/data/$it").exists() }
}

/**
 * Optional Aliyun device risk SDK bridge.
 *
 * The SDK is delivered as a private AAR and is intentionally referenced through
 * reflection so the app remains buildable before the AAR and AppKey are supplied.
 */
object AliyunDeviceRiskManager {
    private val initialized = AtomicBoolean(false)
    @Volatile private var initializedAtMillis: Long = 0L
    @Volatile private var lastToken: String? = null
    @Volatile private var lastCode: Int? = null

    fun isAvailable(): Boolean = runCatching {
        Class.forName("net.security.device.api.SecurityDevice")
        Class.forName("net.security.device.api.SecurityToken")
        true
    }.getOrDefault(false)

    fun initialize(context: Context, appKey: String, onComplete: (Int) -> Unit = {}) {
        if (appKey.isBlank() || !isAvailable() || !initialized.compareAndSet(false, true)) return
        runCatching {
            val deviceClass = Class.forName("net.security.device.api.SecurityDevice")
            val instance = deviceClass.getMethod("getInstance").invoke(null)
            val options = hashMapOf<String, String>()
            val listenerClass = Class.forName("net.security.device.api.SecurityInitListener")
            val listener = java.lang.reflect.Proxy.newProxyInstance(
                listenerClass.classLoader,
                arrayOf(listenerClass)
            ) { _, method, args ->
                if (method.name == "onInitFinish") {
                    val code = args?.firstOrNull() as? Int ?: -1
                    lastCode = code
                    initializedAtMillis = System.currentTimeMillis()
                    Log.i(ALIYUN_DEVICE_RISK_TAG, "Aliyun SDK initialized: code=$code")
                    onComplete(code)
                }
                null
            }
            deviceClass.getMethod(
                "initWithOptions",
                Context::class.java,
                String::class.java,
                Map::class.java,
                listenerClass
            ).invoke(instance, context.applicationContext, appKey, options, listener)
        }.onFailure {
            initialized.set(false)
            Log.e(ALIYUN_DEVICE_RISK_TAG, "Aliyun SDK initialization failed", it)
        }
    }

    suspend fun getDeviceToken(bizId: String? = null): String? = withContext(Dispatchers.IO) {
        if (!initialized.get() || !isAvailable()) return@withContext null
        val waitMillis = 2_000L - (System.currentTimeMillis() - initializedAtMillis)
        if (waitMillis > 0) Thread.sleep(waitMillis)
        runCatching {
            val deviceClass = Class.forName("net.security.device.api.SecurityDevice")
            val instance = deviceClass.getMethod("getInstance").invoke(null)
            val token = if (bizId.isNullOrBlank()) {
                deviceClass.getMethod("getDeviceToken").invoke(instance)
            } else {
                deviceClass.getMethod("getDeviceToken", String::class.java).invoke(instance, bizId)
            }
            val tokenValue = token?.javaClass?.getField("token")?.get(token)?.toString()
            lastToken = tokenValue
            tokenValue
        }.onFailure {
            Log.e(ALIYUN_DEVICE_RISK_TAG, "Aliyun device token failed", it)
        }.getOrNull()
    }

    fun token(): String? = lastToken
    fun initCode(): Int? = lastCode
}
