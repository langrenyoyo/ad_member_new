package com.example.idiomquiz

import com.example.idiomquiz.ads.RewardedLifecycle
import org.junit.Assert.*
import org.junit.Test

class RewardedLifecycleTest {
    @Test fun loadTriggersOneShowAndRewardIsReportedOnce() {
        val session = RewardedLifecycle()
        assertTrue(session.loaded())
        assertFalse(session.loaded())
        assertTrue(session.impression())
        assertFalse(session.impression())
        assertTrue(session.reward())
        assertFalse(session.reward())
        assertTrue(session.end())
        assertFalse(session.end())
    }

    @Test fun timeoutOrClosedSessionIgnoresLateSdkCallbacks() {
        val old = RewardedLifecycle()
        old.end()
        assertFalse(old.loaded())
        assertFalse(old.impression())
        assertFalse(old.reward())
        assertTrue(RewardedLifecycle().loaded())
    }
}
