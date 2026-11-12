package com.example.idiomquiz

import com.example.idiomquiz.data.AdEventOutbox
import com.example.idiomquiz.data.UserApiException
import com.example.idiomquiz.data.isTerminalRewardError
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class AdEventOutboxTest {
    private val store = linkedMapOf<String, String>()
    private var time = 1_000L
    private fun outbox() = AdEventOutbox({ store.toMap() }, { key, value ->
        if (value == null) store.remove(key) else store[key] = value
    }, { time })
    private fun payload(event: String = "shown") = JSONObject().put("event", event)

    @Test fun missingDisplayProofRetriesButInvalidProofIsTerminal() {
        assertFalse(UserApiException(409, "ECPM_DISPLAY_BINDING_REQUIRED", "missing").isTerminalRewardError())
        assertTrue(UserApiException(409, "ECPM_PROOF_BINDING_MISMATCH", "wrong").isTerminalRewardError())
        assertTrue(UserApiException(422, "INVALID_ECPM_PROOF", "invalid").isTerminalRewardError())
        assertTrue(UserApiException(404, null, "missing session").isTerminalRewardError())
        assertFalse(UserApiException(503, null, "unavailable").isTerminalRewardError())
    }

    @Test fun failedUploadSurvivesRecreationAndOnlyOriginalMemberCanReplay() = runBlocking {
        outbox().enqueue("alice", "pending_secondary_alice_1", "ads/secondary-events", payload())
        assertTrue(outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, _ -> throw IOException() })
        var sent = 0
        assertFalse(outbox().flush("bob", AdEventOutbox.SECONDARY_PREFIX) { _, _ -> sent++ })
        assertEquals(0, sent)
        assertEquals(1, store.size)
        assertFalse(outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { path, body ->
            assertEquals("ads/secondary-events", path)
            assertEquals("shown", body.getString("event"))
            sent++
        })
        assertEquals(1, sent)
        assertTrue(store.isEmpty())
    }

    @Test fun displayMetadataFlushSelectsCorrectSessionAndLeavesAdvisoryEvents() = runBlocking {
        val box = outbox()
        box.enqueue("alice", "pending_ad_metadata_a", "ads/a/metadata", payload())
        box.enqueue("alice", "pending_ad_metadata_click", "ads/a/metadata", payload("clicked"))
        box.enqueue("alice", "pending_ad_metadata_b", "ads/b/metadata", payload())
        val sent = mutableListOf<String>()
        assertFalse(box.flush("alice", AdEventOutbox.METADATA_PREFIX, "ads/a/metadata", "shown") { path, body ->
            sent += "$path:${body.getString("event")}"
        })
        assertEquals(listOf("ads/a/metadata:shown"), sent)
        assertEquals(2, store.size)
    }

    @Test fun cancellationDoesNotDeletePendingEvent() = runBlocking {
        outbox().enqueue("alice", "pending_secondary_1", "ads/secondary-events", payload())
        try {
            outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, _ -> throw CancellationException() }
            fail("cancellation must propagate")
        } catch (_: CancellationException) { }
        assertEquals(1, store.size)
    }

    @Test fun expiryPrunesOtherMembersWithoutSendingThem() = runBlocking {
        outbox().enqueue("alice", "pending_secondary_1", "ads/secondary-events", payload())
        time += AdEventOutbox.MAX_AGE_MS
        assertFalse(outbox().flush("bob", AdEventOutbox.SECONDARY_PREFIX) { _, _ -> fail("expired event") })
        assertTrue(store.isEmpty())
    }

    @Test fun batchesEventuallyDrainEvenWithOtherMembersAheadInQueue() = runBlocking {
        repeat(55) { outbox().enqueue("bob", "pending_secondary_b$it", "ads/secondary-events", payload()) }
        repeat(55) { outbox().enqueue("alice", "pending_secondary_a$it", "ads/secondary-events", payload()) }
        var count = 0
        assertTrue(outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, _ -> count++ })
        assertEquals(50, count)
        assertFalse(outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, _ -> count++ })
        assertEquals(55, count)
        assertEquals(55, store.size)
    }

    @Test fun payloadSnapshotCannotBeChangedByLaterSdkMutation() = runBlocking {
        val body = payload()
        outbox().enqueue("alice", "pending_secondary_1", "ads/secondary-events", body)
        body.put("event", "clicked")
        outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, saved -> assertEquals("shown", saved.getString("event")) }
        assertTrue(store.isEmpty())
    }

    @Test fun invalidPayloadDropsWhileTemporaryErrorsRemain() = runBlocking {
        outbox().enqueue("alice", "pending_secondary_invalid", "ads/secondary-events", payload())
        assertFalse(outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, _ ->
            throw UserApiException(422, null, "invalid")
        })
        assertTrue(store.isEmpty())
        outbox().enqueue("alice", "pending_secondary_retry", "ads/secondary-events", payload())
        assertTrue(outbox().flush("alice", AdEventOutbox.SECONDARY_PREFIX) { _, _ ->
            throw UserApiException(503, null, "unavailable")
        })
        assertEquals(1, store.size)
    }
}
