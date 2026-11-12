package com.example.idiomquiz

import com.example.idiomquiz.ads.awaitAdClose
import com.example.idiomquiz.ads.enterAfterInterstitial
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class EntryInterstitialTest {
    @Test fun entryWaitsForCloseAndDuplicateCallbacksDoNotEnterTwice() = runBlocking {
        var close: () -> Unit = {}
        var failed: (String) -> Unit = {}
        var loads = 0
        var entries = 0
        val job = launch(start = CoroutineStart.UNDISPATCHED) {
            enterAfterInterstitial({ true }, {
                loads++
                awaitAdClose({ it() }) { closed, failure ->
                    close = closed
                    failed = failure
                    val dispose: () -> Unit = {}
                    dispose
                }
            }, { entries++ })
        }
        assertEquals(1, loads)
        assertEquals(0, entries)
        close()
        close()
        failed("late callback")
        job.join()
        assertEquals(1, entries)
    }

    @Test fun noConfigurationNoFillTimeoutAndSdkFailureStillAllowEntry() = runBlocking {
        for (failure in listOf(null, "no fill", "timeout", "SDK setup failed")) {
            var entries = 0
            enterAfterInterstitial({ true }, {
                if (failure != null) error(failure)
            }, { entries++ })
            assertEquals(1, entries)
        }
    }

    @Test fun leavingPageOrChangingAccountPreventsLateNavigation() = runBlocking {
        for (availableAtStart in listOf(true, false)) {
            var current = availableAtStart
            var loads = 0
            var entries = 0
            enterAfterInterstitial({ current }, { loads++; current = false }, { entries++ })
            assertEquals(if (availableAtStart) 1 else 0, loads)
            assertEquals(0, entries)
        }
    }

    @Test fun cancellationReleasesAdAndNeverOpensEntryFromLateCallback() = runBlocking {
        var close: () -> Unit = {}
        var disposed = false
        var entries = 0
        val job = launch(start = CoroutineStart.UNDISPATCHED) {
            enterAfterInterstitial({ true }, {
                awaitAdClose({ it() }) { closed, _ ->
                    close = closed
                    val dispose: () -> Unit = { disposed = true }
                    dispose
                }
            }, { entries++ })
        }
        job.cancel()
        job.join()
        close()
        assertTrue(disposed)
        assertEquals(0, entries)
    }

    @Test fun cancellationIsNotTreatedAsAnAdFailure() = runBlocking {
        var entries = 0
        val result = runCatching {
            enterAfterInterstitial({ true }, { throw CancellationException("session changed") }, { entries++ })
        }
        assertTrue(result.exceptionOrNull() is CancellationException)
        assertEquals(0, entries)
    }
}
