package com.example.idiomquiz.data

import java.math.BigDecimal
import org.json.JSONObject

internal data class RewardReceipt(val epoch: Long, val sessionId: String, val coin: BigDecimal, val balance: BigDecimal?)

internal fun rewardReceipt(epoch: Long, sessionId: String, response: JSONObject): RewardReceipt? {
    val data = response.optJSONObject("data") ?: return null
    if (!data.optBoolean("rewarded", false) || sessionId.isBlank()) return null
    val coin = data.opt("coin_added")?.toString()?.toBigDecimalOrNull()?.takeIf { it.signum() >= 0 } ?: return null
    val balance = data.opt("coin_balance")?.toString()?.toBigDecimalOrNull()?.takeIf { it.signum() >= 0 }
    return RewardReceipt(epoch, sessionId, coin, balance)
}

/** Same completion may arrive from immediate settlement, retry, and history polling. */
internal class RewardReceiptGate {
    private var epoch: Long? = null
    private val accepted = mutableSetOf<String>()
    fun accept(receipt: RewardReceipt, currentEpoch: Long): Boolean {
        if (receipt.epoch != currentEpoch || receipt.coin.signum() < 0) return false
        if (epoch != currentEpoch) { accepted.clear(); epoch = currentEpoch }
        return accepted.add(receipt.sessionId)
    }
}
