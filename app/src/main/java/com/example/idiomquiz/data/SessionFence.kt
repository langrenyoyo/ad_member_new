package com.example.idiomquiz.data

import kotlinx.coroutines.CancellationException

/** Short atomic sections only; never hold this monitor across network suspension. */
internal class SessionFence {
    private var generation = 0L

    @Synchronized fun snapshot(): Long = generation

    @Synchronized fun <T> replace(action: () -> T): T {
        generation++
        return action()
    }

    @Synchronized fun <T> withCurrent(expected: Long, action: () -> T): T {
        if (expected != generation) throw CancellationException("Session changed")
        return action()
    }
}
