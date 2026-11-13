package com.example.idiomquiz.security

/** Event-derived foreground time, clipped to the report day (not Android's whole-day buckets). */
internal class UsageTimeline(private val start: Long, private val end: Long) {
    data class Value(var durationMs: Long = 0, var opens: Int = 0)
    private val values = linkedMapOf<String, Value>()
    private var active: String? = null
    private var activeSince = start
    private var lastPackage: String? = null
    private var lastEnd = Long.MIN_VALUE

    fun event(packageName: String, time: Long, kind: Int) {
        if (time > end) return
        when (kind) {
            1 -> { // MOVE_TO_FOREGROUND / ACTIVITY_RESUMED
                if (active == packageName || packageName.isBlank()) return
                close(time)
                val continuingActivity = lastPackage == packageName && lastEnd != Long.MIN_VALUE && time - lastEnd in 0..1000
                if (time >= start && !continuingActivity) values.getOrPut(packageName) { Value() }.opens++
                active = packageName
                activeSince = time
                lastPackage = packageName
            }
            2 -> if (active == packageName) close(time) // MOVE_TO_BACKGROUND / ACTIVITY_PAUSED
            16, 26 -> { close(time); lastPackage = null } // screen off / shutdown
        }
    }

    private fun close(time: Long) {
        active?.let { name ->
            val elapsed = (minOf(time, end) - maxOf(activeSince, start)).coerceAtLeast(0)
            if (elapsed > 0) values.getOrPut(name) { Value() }.durationMs += elapsed
            lastEnd = time
        }
        active = null
    }

    fun finish(): Map<String, Value> {
        close(end)
        return values
    }
}
