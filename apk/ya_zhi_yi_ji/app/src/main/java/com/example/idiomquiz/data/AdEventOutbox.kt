package com.example.idiomquiz.data

import kotlinx.coroutines.CancellationException
import org.json.JSONObject

/** SDK events survive process death and logout; login tokens never enter this queue. */
internal class AdEventOutbox(
    private val entries: () -> Map<String, *>,
    private val save: (String, String?) -> Unit,
    private val now: () -> Long = System::currentTimeMillis
) {
    fun enqueue(memberId: String, key: String, path: String, payload: JSONObject) {
        save(key, JSONObject().put("member_id", memberId).put("created", now())
            .put("path", path).put("payload", JSONObject(payload.toString())).toString())
    }

    /** Returns true while this member still has retryable work. Other members are never sent. */
    suspend fun flush(memberId: String, prefix: String, path: String? = null, event: String? = null,
                      send: suspend (String, JSONObject) -> Unit): Boolean {
        var retry = false
        var sent = 0
        for ((key, raw) in entries().filterKeys { it.startsWith(prefix) }) {
            val record = runCatching { JSONObject(raw as String) }.getOrNull()
            val created = record?.optLong("created", 0) ?: 0
            if (record == null || created <= 0 || now() - created >= MAX_AGE_MS) {
                save(key, null)
                continue
            }
            if (record.optString("member_id") != memberId) continue
            val payload = record.optJSONObject("payload")
            // Compatibility with the original secondary queue, which did not store a path.
            val endpoint = record.optString("path").ifBlank {
                if (prefix == SECONDARY_PREFIX) "ads/secondary-events" else ""
            }
            if (endpoint.isBlank() || payload == null) { save(key, null); continue }
            if (path != null && endpoint != path) continue
            if (event != null && payload.optString("event") != event) continue
            if (sent++ >= 50) { retry = true; continue }
            try {
                send(endpoint, payload)
                save(key, null)
            } catch (error: CancellationException) {
                throw error
            } catch (error: UserApiException) {
                if (error.statusCode in listOf(400, 404, 409, 422)) save(key, null)
                else retry = true
            } catch (_: Exception) {
                retry = true
            }
        }
        return retry
    }

    companion object {
        const val SECONDARY_PREFIX = "pending_secondary_"
        const val METADATA_PREFIX = "pending_ad_metadata_"
        const val MAX_AGE_MS = 24 * 60 * 60 * 1000L
    }
}

/** A missing display binding can arrive later; proof rejection and expired sessions cannot. */
internal fun UserApiException.isTerminalRewardError(): Boolean =
    statusCode in listOf(404, 409, 422) && errorCode != "ECPM_DISPLAY_BINDING_REQUIRED"
