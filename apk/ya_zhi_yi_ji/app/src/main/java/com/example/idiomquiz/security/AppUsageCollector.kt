package com.example.idiomquiz.security

import kotlinx.coroutines.ensureActive
import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Process
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.ZoneId

object AppUsageCollector {
    fun granted(context: Context): Boolean {
        val ops = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        return ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName) == AppOpsManager.MODE_ALLOWED
    }

    suspend fun collect(context: Context): JSONObject {
        val zone = ZoneId.of("Asia/Shanghai")
        val day = LocalDate.now(zone)
        val body = JSONObject().put("granted", granted(context)).put("report_date", day.toString())
        val items = JSONArray()
        if (granted(context)) {
            val manager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val start = day.atStartOfDay(zone).toInstant().toEpochMilli()
            val end = System.currentTimeMillis()
            val opens = mutableMapOf<String, Int>()
            val events = manager.queryEvents(start, end)
            val event = UsageEvents.Event()
            var previous: String? = null
            while (events.hasNextEvent()) {
                kotlinx.coroutines.currentCoroutineContext().ensureActive()
                events.getNextEvent(event)
                if (event.eventType == UsageEvents.Event.MOVE_TO_FOREGROUND) {
                    if (previous != event.packageName) opens[event.packageName] = (opens[event.packageName] ?: 0) + 1
                    previous = event.packageName
                } else if (event.eventType == UsageEvents.Event.MOVE_TO_BACKGROUND && previous == event.packageName) previous = null
            }
            manager.queryAndAggregateUsageStats(start, end).values.sortedByDescending { it.totalTimeInForeground }.take(1000).forEach {
                items.put(JSONObject().put("package_name", it.packageName)
                    .put("duration_ms", it.totalTimeInForeground.coerceIn(0, 86_400_000))
                    .put("opens", (opens[it.packageName] ?: 0).coerceAtMost(100000)))
            }
        }
        return body.put("items", items)
    }
}
