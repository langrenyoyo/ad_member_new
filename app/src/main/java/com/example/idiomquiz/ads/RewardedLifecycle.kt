package com.example.idiomquiz.ads

/** Main-thread state for a single server session; duplicate SDK events are ignored. */
internal class RewardedLifecycle {
    var ended = false
        private set
    private var showing = false
    private var rewardSent = false
    private var impressionSent = false

    fun loaded(): Boolean {
        if (ended || showing) return false
        showing = true
        return true
    }

    fun impression(): Boolean {
        if (ended || impressionSent) return false
        impressionSent = true
        return true
    }

    fun reward(): Boolean {
        if (ended || rewardSent) return false
        rewardSent = true
        return true
    }

    fun end(): Boolean {
        if (ended) return false
        ended = true
        return true
    }
}
