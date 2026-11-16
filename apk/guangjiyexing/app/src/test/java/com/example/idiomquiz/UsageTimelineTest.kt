package com.example.idiomquiz

import com.example.idiomquiz.security.UsageTimeline
import org.junit.Assert.*
import org.junit.Test

class UsageTimelineTest {
    @Test fun clipsMidnightAndCountsOnlyTodaysEntries() {
        val timeline = UsageTimeline(10_000, 20_000)
        timeline.event("a", 9_000, 1)
        timeline.event("a", 12_000, 2)
        timeline.event("b", 14_000, 1)
        val result = timeline.finish()
        assertEquals(2_000L, result.getValue("a").durationMs)
        assertEquals(0, result.getValue("a").opens)
        assertEquals(6_000L, result.getValue("b").durationMs)
        assertEquals(1, result.getValue("b").opens)
    }

    @Test fun mergesActivityTransitionsButCountsReturnFromOtherApp() {
        val timeline = UsageTimeline(0, 10_000)
        timeline.event("a", 100, 1)
        timeline.event("a", 200, 1)
        timeline.event("a", 1_000, 2)
        timeline.event("a", 1_100, 1)
        timeline.event("b", 2_000, 1)
        timeline.event("a", 2_500, 1)
        val result = timeline.finish()
        assertEquals(2, result.getValue("a").opens)
        assertEquals(9_300L, result.getValue("a").durationMs)
        assertEquals(500L, result.getValue("b").durationMs)
    }

    @Test fun screenOffAndShutdownStopDuration() {
        val timeline = UsageTimeline(0, 10_000)
        timeline.event("a", 0, 1)
        timeline.event("", 1_000, 16)
        timeline.event("a", 1_100, 1)
        timeline.event("", 2_000, 26)
        assertEquals(1_900L, timeline.finish().getValue("a").durationMs)
        assertEquals(2, timeline.finish().getValue("a").opens)
    }

    @Test fun ignoresUnmatchedPauseAndFutureEvents() {
        val timeline = UsageTimeline(0, 10_000)
        timeline.event("a", 500, 2)
        timeline.event("a", 1_000, 1)
        timeline.event("b", 2_000, 2)
        timeline.event("a", 20_000, 2)
        assertEquals(9_000L, timeline.finish().getValue("a").durationMs)
        assertTrue(UsageTimeline(0, 10_000).finish().isEmpty())
    }
}
