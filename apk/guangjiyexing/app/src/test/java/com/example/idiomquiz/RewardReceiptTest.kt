package com.example.idiomquiz

import com.example.idiomquiz.data.*
import java.math.BigDecimal
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class RewardReceiptTest {
    @Test fun displaysSettledAmountWithoutRoundingOrConfusingItWithBalance() {
        val receipt = rewardReceipt(1, "ad-1", JSONObject("""{"data":{"rewarded":true,"coin_added":"0.123456","coin_balance":"98765.432100"}}"""))!!
        assertEquals(BigDecimal("0.123456"), receipt.coin)
        assertEquals(BigDecimal("98765.432100"), receipt.balance)
    }

    @Test fun pendingFailedMissingAndInvalidAmountsNeverProduceSuccessNotice() {
        for (data in listOf("""{"status":"queued"}""", """{"rewarded":false,"coin_added":10}""",
            """{"rewarded":true}""", """{"rewarded":true,"coin_added":null}""",
            """{"rewarded":true,"coin_added":-1}""", """{"rewarded":true,"coin_added":"NaN"}""")) {
            assertNull(rewardReceipt(1, "ad-1", JSONObject().put("data", JSONObject(data))))
        }
    }

    @Test fun zeroRewardIsShownHonestlyAndBalanceIsOptional() {
        val receipt = rewardReceipt(1, "ad-1", JSONObject("""{"data":{"rewarded":true,"coin_added":0}}"""))!!
        assertEquals(BigDecimal.ZERO, receipt.coin)
        assertNull(receipt.balance)
    }

    @Test fun immediateRetryAndHistoryOnlyNotifyOncePerSession() {
        val gate = RewardReceiptGate()
        val receipt = RewardReceipt(1, "ad-1", BigDecimal.ONE, null)
        assertTrue(gate.accept(receipt, 1))
        assertFalse(gate.accept(receipt, 1))
        assertTrue(gate.accept(receipt.copy(sessionId = "ad-2"), 1))
        assertFalse(gate.accept(receipt, 2))
        assertTrue(gate.accept(receipt.copy(epoch = 2), 2))
        assertFalse(gate.accept(receipt, 2))
        assertFalse(gate.accept(receipt.copy(epoch = 2), 2))
    }
}
