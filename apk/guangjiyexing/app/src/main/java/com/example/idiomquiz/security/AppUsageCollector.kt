package com.example.idiomquiz.security

import kotlinx.coroutines.ensureActive
import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Process
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.ZoneId

object AppUsageCollector {
    private const val CONSENT_VERSION = 2
    fun consented(context: Context): Boolean = context.getSharedPreferences("app_usage_consent", Context.MODE_PRIVATE)
        .getInt("version", 0) == CONSENT_VERSION

    fun acceptConsent(context: Context) {
        context.getSharedPreferences("app_usage_consent", Context.MODE_PRIVATE).edit()
            .putInt("version", CONSENT_VERSION).apply()
    }

    fun granted(context: Context): Boolean {
        val ops = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        return ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName) == AppOpsManager.MODE_ALLOWED
    }

    suspend fun collect(context: Context): JSONObject {
        val zone = ZoneId.of("Asia/Shanghai")
        val day = LocalDate.now(zone)
        val allowed = consented(context) && granted(context)
        val body = JSONObject().put("granted", allowed).put("report_date", day.toString())
        val items = JSONArray()
        if (allowed) {
            val manager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val start = day.atStartOfDay(zone).toInstant().toEpochMilli()
            val end = System.currentTimeMillis()
            val timeline = UsageTimeline(start, end)
            // Read yesterday's events only to carry a foreground session across midnight.
            val events = manager.queryEvents(start - 86_400_000, end)
            val event = UsageEvents.Event()
            while (events.hasNextEvent()) {
                kotlinx.coroutines.currentCoroutineContext().ensureActive()
                events.getNextEvent(event)
                timeline.event(event.packageName.orEmpty(), event.timeStamp, event.eventType)
            }
            timeline.finish().entries.sortedByDescending { it.value.durationMs }.take(1000).forEach { (name, value) ->
                items.put(JSONObject().put("package_name", name)
                    .put("duration_ms", value.durationMs.coerceIn(0, 86_400_000))
                    .put("opens", value.opens.coerceAtMost(100000)))
            }
            val installed = JSONArray()
            val packages = context.packageManager
            @Suppress("DEPRECATION")
            val apps = packages.getInstalledPackages(0).sortedBy { it.packageName }
            apps.take(5000).forEach { app ->
                kotlinx.coroutines.currentCoroutineContext().ensureActive()
                val info = app.applicationInfo
                installed.put(JSONObject().put("package_name", app.packageName)
                    .put("app_name", (info?.let { packages.getApplicationLabel(it).toString() } ?: app.packageName).take(255))
                    .put("version_name", app.versionName.orEmpty().take(255))
                    .put("system_app", info != null && info.flags and ApplicationInfo.FLAG_SYSTEM != 0))
            }
            // Recheck before returning sensitive data if permission was revoked during collection.
            if (!granted(context) || !consented(context)) return JSONObject().put("granted", false)
                .put("report_date", day.toString()).put("items", JSONArray())
            body.put("installed_apps", installed).put("inventory_scope", "current_profile_visible")
                .put("inventory_truncated", apps.size > 5000).put("consent_version", CONSENT_VERSION)
                .put("collected_at", java.time.Instant.ofEpochMilli(end).toString())
                .put("usage_source", "foreground_events_v1")
        }
        return body.put("items", items)
    }
}
