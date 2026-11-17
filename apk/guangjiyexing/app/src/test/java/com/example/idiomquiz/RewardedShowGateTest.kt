package com.example.idiomquiz

import com.example.idiomquiz.ads.RewardedShowGate
import org.junit.Assert.assertEquals
import org.junit.Test

class RewardedShowGateTest {
    @Test fun loadedVideoWaitsForInterstitialCloseAndShowsOnlyOnce() {
        val gate = RewardedShowGate()
        var shows = 0
        gate.ready { shows++ }
        assertEquals(0, shows)
        gate.open(); gate.open(); gate.ready { shows++ }
        assertEquals(1, shows)
    }
    @Test fun slowLoadShowsAfterCloseButCancellationNeverShows() {
        val gate = RewardedShowGate()
        var shows = 0
        gate.open(); gate.ready { shows++ }
        assertEquals(1, shows)
        val cancelled = RewardedShowGate()
        cancelled.ready { shows++ }; cancelled.cancel(); cancelled.open()
        cancelled.ready { shows++ }
        assertEquals(1, shows)
    }
}
