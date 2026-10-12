package com.example.idiomquiz.data

import org.json.JSONObject
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneOffset

/** Boundary conversions for the deployed user API. Coins are decimal, never integer. */
internal fun JSONObject.decimal(key: String, fallback: BigDecimal = BigDecimal.ZERO): BigDecimal =
    opt(key)?.takeUnless { it == JSONObject.NULL }?.toString()?.toBigDecimalOrNull() ?: fallback

internal fun parseServerTime(value: String?): Long? = value?.let {
    runCatching { Instant.parse(it).toEpochMilli() }.getOrElse { _ ->
        // Older SQLite deployments serialize UTC without an offset.
        runCatching { LocalDateTime.parse(it).toInstant(ZoneOffset.UTC).toEpochMilli() }.getOrNull()
    }
}

internal fun DeviceRiskVerification.quotaExhausted(): Boolean = limited && remaining == 0

internal fun parseAlipay(data: JSONObject?): AlipayAccount = AlipayAccount(
    bound = data != null && !data.optString("account_masked").isBlank(),
    accountMasked = data?.optString("account_masked"),
    realNameMasked = data?.optString("real_name"),
    identityVerified = data?.optBoolean("identity_verified", false) ?: false
)

internal fun parseWithdrawalOptions(data: JSONObject): List<WithdrawalOption> {
    val tiers = data.optJSONArray("tiers") ?: return emptyList()
    return (0 until tiers.length()).map { index ->
        val tier = tiers.getJSONObject(index)
        val cents = tier.getLong("amount_cents")
        WithdrawalOption(cents.toString(), cents, tier.decimal("coin_cost"),
            "提现 ${BigDecimal.valueOf(cents, 2).toPlainString()} 元")
    }
}

internal fun parseWithdrawal(data: JSONObject): WithdrawalRecord {
    val payout = data.optJSONObject("payout")
    return WithdrawalRecord(
        id = data.get("id").toString(),
        amountCents = payout?.optLong("amount_cents")
            ?: data.decimal("exchange_value").movePointRight(2).longValueExact(),
        coin = payout?.decimal("coin_cost") ?: data.decimal("coin"),
        state = data.opt("status")?.toString() ?: "unknown",
        createdAt = data.optString("created_at"),
        payoutState = payout?.optString("state"),
        statusLabel = withdrawalStatus(data)
    )
}

internal fun adEventBody(session: AdSession, eventId: String): JSONObject = JSONObject()
    .put("event_id", eventId)
    .put("session_token", session.sessionToken)
