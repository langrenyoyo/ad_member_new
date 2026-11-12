package com.example.idiomquiz.security

import android.content.Context
import android.os.Build
import java.io.File


data class DeviceSecurityResult(val blocked: Boolean, val flags: List<String>) {
    val headerValue: String get() = if (flags.isEmpty()) "clean" else flags.joinToString(",")
}

object SecurityGuard {
    fun evaluate(context: Context): DeviceSecurityResult {
        val flags = buildList {
            if (isEmulator()) add("emulator")
            if (hasRootIndicators()) add("root")
            if (hasHookIndicators()) add("hook")
            if (android.provider.Settings.Global.getInt(context.contentResolver, android.provider.Settings.Global.DEVELOPMENT_SETTINGS_ENABLED, 0) == 1) add("developer")
            if (android.provider.Settings.Secure.getInt(context.contentResolver, android.provider.Settings.Secure.ACCESSIBILITY_ENABLED, 0) == 1) add("accessibility")
            if (android.provider.Settings.Global.getInt(context.contentResolver, "bluetooth_on", 0) == 1) add("bluetooth")
        }
        return DeviceSecurityResult(flags.any { it in setOf("emulator", "root", "hook") }, flags)
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
