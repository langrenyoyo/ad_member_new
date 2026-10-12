package com.example.idiomquiz

import com.example.idiomquiz.data.SessionFence
import kotlinx.coroutines.CancellationException
import org.junit.Assert.*
import org.junit.Test

class SessionFenceTest {
    @Test fun lateRefreshCannotRestoreLoggedOutCredentials() {
        val fence = SessionFence()
        var token: String? = "old"
        val request = fence.snapshot()
        fence.replace { token = null }
        assertThrows(CancellationException::class.java) {
            fence.withCurrent(request) { token = "late refresh" }
        }
        assertNull(token)
    }

    @Test fun oldLoginAndOldFailureCannotOverwriteNewAccount() {
        val fence = SessionFence()
        var account = "first"
        val first = fence.snapshot()
        fence.replace { account = "second" }
        assertThrows(CancellationException::class.java) {
            fence.withCurrent(first) { account = "late first login" }
        }
        assertThrows(CancellationException::class.java) {
            fence.withCurrent(first) { fence.replace { account = "" } }
        }
        assertEquals("second", account)
    }

    @Test fun sameSessionAllowsRepeatedRefreshCommits() {
        val fence = SessionFence()
        val epoch = fence.snapshot()
        var token = "initial"
        fence.withCurrent(epoch) { token = "rotated" }
        assertEquals("rotated", fence.withCurrent(epoch) { token })
    }
}
