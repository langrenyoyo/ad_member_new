package com.example.idiomquiz.ads

/** Main-thread gate: loading may overlap, fullscreen presentation must not. */
internal class RewardedShowGate {
    private var opened = false
    private var cancelled = false
    private var presented = false
    private var pending: (() -> Unit)? = null

    fun ready(show: () -> Unit) {
        if (cancelled || presented || pending != null) return
        pending = show
        drain()
    }

    fun open() { opened = true; drain() }
    fun cancel() { cancelled = true; pending = null }

    private fun drain() {
        if (!opened || cancelled || presented) return
        val show = pending ?: return
        pending = null
        presented = true
        show()
    }
}
