package com.example.idiomquiz

import com.example.idiomquiz.ads.awaitAdClose
import com.example.idiomquiz.ads.runRewardedAdGroup
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.*
import org.junit.Test

class RewardedAdGroupTest {
    private class Ad(val type: String, val close: () -> Unit, val fail: (String) -> Unit) {
        var cancelled = false
    }

    private class Sdk {
        val ads = mutableListOf<Ad>()
        suspend fun show(type: String) = awaitAdClose(dispose = { it() }) { close, fail ->
            val ad = Ad(type, close, fail)
            ads += ad
            val cancel: () -> Unit = { ad.cancelled = true }
            cancel
        }
        suspend fun group() = runRewardedAdGroup(
            showInterstitial = { show("interstitial") },
            showRewarded = { show("rewarded") }
        )
    }

    @Test fun eachCloseStartsExactlyOneNextAdAndGroupWaitsForLastClose() = runBlocking {
        val sdk = Sdk()
        val group = launch(start = CoroutineStart.UNDISPATCHED) { sdk.group() }
        assertEquals(listOf("interstitial"), sdk.ads.map { it.type })
        val first = sdk.ads[0]
        first.close()
        first.close()
        first.fail("late error")
        yield()
        assertEquals(listOf("interstitial", "rewarded"), sdk.ads.map { it.type })
        assertTrue(group.isActive)
        sdk.ads[1].close()
        yield()
        assertEquals(listOf("interstitial", "rewarded", "interstitial"), sdk.ads.map { it.type })
        assertTrue(group.isActive)
        first.close() // A stale callback cannot finish the tail interstitial.
        yield()
        assertTrue(group.isActive)
        sdk.ads[2].close()
        group.join()
        assertFalse(group.isActive)
        assertEquals(3, sdk.ads.size)
    }

    @Test fun failureAtAnyStageStopsInsteadOfSkippingOrStartingAnotherGroup() = runBlocking {
        for (failedStage in 0..2) {
            val sdk = Sdk()
            var failure: Throwable? = null
            val group = launch(start = CoroutineStart.UNDISPATCHED) {
                failure = runCatching { sdk.group() }.exceptionOrNull()
            }
            repeat(failedStage) { sdk.ads.last().close(); yield() }
            sdk.ads.last().fail("no fill or timeout")
            group.join()
            assertEquals("no fill or timeout", failure?.message)
            sdk.ads.last().close()
            yield()
            assertEquals(failedStage + 1, sdk.ads.size)
        }
    }

    @Test fun cancellationDisposesCurrentAdAndIgnoresLateCallbacksAtEveryStage() = runBlocking {
        for (cancelledStage in 0..2) {
            val sdk = Sdk()
            val group = launch(start = CoroutineStart.UNDISPATCHED) { sdk.group() }
            repeat(cancelledStage) { sdk.ads.last().close(); yield() }
            group.cancel()
            group.join()
            val current = sdk.ads.last()
            assertTrue(current.cancelled)
            current.close()
            current.fail("late SDK failure")
            yield()
            assertEquals(cancelledStage + 1, sdk.ads.size)
        }
    }

    @Test fun cancellationAfterCloseBeforeResumeDoesNotStartNextAd() = runBlocking {
        val sdk = Sdk()
        val group = launch(start = CoroutineStart.UNDISPATCHED) { sdk.group() }
        sdk.ads[0].close()
        group.cancel()
        group.join()
        assertEquals(1, sdk.ads.size)
    }

    @Test fun oldCallbacksCannotAdvanceNewGroup() = runBlocking {
        val sdk = Sdk()
        val old = launch(start = CoroutineStart.UNDISPATCHED) { sdk.group() }
        val oldAd = sdk.ads.single()
        old.cancel()
        old.join()
        val fresh = launch(start = CoroutineStart.UNDISPATCHED) { sdk.group() }
        oldAd.close()
        oldAd.fail("late")
        yield()
        assertEquals(2, sdk.ads.size)
        assertTrue(fresh.isActive)
        fresh.cancel()
        fresh.join()
    }

    @Test fun synchronousSdkFailureStopsGroup() = runBlocking {
        var rewardCalls = 0
        val failure = runCatching {
            runRewardedAdGroup(
                showInterstitial = {
                    awaitAdClose(dispose = { it() }) { _, _ -> error("SDK setup failed") }
                },
                showRewarded = { rewardCalls++ }
            )
        }.exceptionOrNull()
        assertEquals("SDK setup failed", failure?.message)
        assertEquals(0, rewardCalls)
    }
}
