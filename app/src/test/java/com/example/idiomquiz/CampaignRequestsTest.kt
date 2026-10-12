package com.example.idiomquiz

import com.example.idiomquiz.data.CampaignRequests
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class CampaignRequestsTest {
    @Test fun delayedRecoveryCannotClearTheNextSubmission() = runBlocking {
        withTimeout(5000) {
            val queue = CampaignRequests()
            var pending: String? = "A"
            val sent = mutableListOf<String>()
            val started = CompletableDeferred<Unit>()
            val finishA = CompletableDeferred<Unit>()
            val startedB = CompletableDeferred<Unit>()
            val finishB = CompletableDeferred<Unit>()
            val recover = launch {
                queue.exclusive {
                    queue.recoverLocked({ pending }, {
                        sent += it
                        started.complete(Unit)
                        finishA.await()
                    }, { pending = null }, { false })
                }
            }
            started.await()
            val submit = launch(start = CoroutineStart.UNDISPATCHED) {
                queue.exclusive {
                    assertNull(pending)
                    pending = "B"
                    sent += "B"
                    startedB.complete(Unit)
                    finishB.await()
                    // Simulate an uncertain new request: preserve B for later recovery.
                }
            }
            assertFalse(startedB.isCompleted)
            assertEquals("A", pending)
            finishA.complete(Unit)
            startedB.await()
            recover.join()
            assertEquals("B", pending)
            assertEquals(listOf("A", "B"), sent)
            finishB.complete(Unit)
            submit.join()
        }
    }

    @Test fun networkFailureAndCancellationPreservePendingAndUnlockQueue() = runBlocking {
        withTimeout(5000) {
            val queue = CampaignRequests()
            var pending: String? = "A"
            try {
                queue.exclusive {
                    queue.recoverLocked({ pending }, { throw IOException("offline") }, { pending = null }, { false })
                }
                fail("Expected IOException")
            } catch (_: IOException) { }
            assertEquals("A", pending)
            val started = CompletableDeferred<Unit>()
            val job = launch {
                queue.exclusive {
                    queue.recoverLocked({ pending }, { started.complete(Unit); awaitCancellation() }, { pending = null }, { false })
                }
            }
            started.await()
            job.cancelAndJoin()
            assertEquals("A", pending)
            queue.exclusive {
                queue.recoverLocked({ pending }, { assertEquals("A", it) }, { pending = null }, { false })
            }
            assertNull(pending)
        }
    }

    @Test fun definiteRejectionClearsAndEmptyRecoverySendsNothing() = runBlocking {
        val queue = CampaignRequests()
        var pending: String? = "A"
        var sent = 0
        try {
            queue.exclusive {
                queue.recoverLocked({ pending }, { sent++; throw IllegalArgumentException("rejected") },
                    { pending = null }, { it is IllegalArgumentException })
            }
            fail("Expected rejection")
        } catch (_: IllegalArgumentException) { }
        queue.exclusive { queue.recoverLocked({ pending }, { sent++ }, { fail("No pending request") }, { false }) }
        assertEquals(1, sent)
        assertNull(pending)
    }
}
