package com.example.idiomquiz

import com.example.idiomquiz.data.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.math.BigDecimal

class ApiContractTest {
    @Test fun withdrawalStateDoesNotConfuseReviewWithPayment() {
        fun label(json: String) = parseWithdrawal(JSONObject(json)).statusLabel
        assertEquals("审核通过", label("""{"id":1,"status":1,"plan_status":0}"""))
        assertEquals("审核通过", label("""{"id":1,"status":1,"plan_status":1}"""))
        assertEquals("已转账（历史记录）", label("""{"id":1,"status":1,"plan_status":1,"transferred_at":"2026-10-12T00:00:00Z"}"""))
        assertEquals("打款处理中", label("""{"id":1,"status":1,"plan_status":1,"transferred_at":"2026-10-12T00:00:00Z","payout":{"state":"processing"}}"""))
        assertEquals("已驳回", label("""{"id":1,"status":2}"""))
        assertEquals("状态待确认", label("""{"id":1,"status":1,"payout":{"state":"unexpected"}}"""))
    }
    @Test fun fractionalCoinsSurviveApiParsing() {
        val wallet = JSONObject("""{"coin":0.151,"reward":0.001}""")
        assertEquals(BigDecimal("0.151"), wallet.decimal("coin"))
        assertEquals(BigDecimal("0.001"), wallet.decimal("reward"))
    }

    @Test fun restrictedDeviceWithRemainingQuotaCanRequestAd() {
        assertFalse(DeviceRiskVerification("check", true, 5).quotaExhausted())
        assertTrue(DeviceRiskVerification("check", true, 0).quotaExhausted())
        assertFalse(DeviceRiskVerification("check", false, null).quotaExhausted())
    }

    @Test fun sqliteUtcTimestampMatchesOffsetTimestamp() {
        assertEquals(parseServerTime("2026-10-08T11:45:00Z"), parseServerTime("2026-10-08T11:45:00"))
        assertNull(parseServerTime("invalid"))
    }

    @Test fun readsDeployedWithdrawalAndBindingShapes() {
        val options = parseWithdrawalOptions(JSONObject("""{"tiers":[{"amount_cents":100,"coin_cost":"0.15"}]}"""))
        assertEquals(1, options.size)
        assertEquals(100L, options.single().amountCents)
        assertEquals(BigDecimal("0.15"), options.single().coin)
        assertTrue(parseAlipay(JSONObject("""{"account_masked":"ab***yz","real_name":"test","identity_verified":false}""")).bound)
        assertFalse(parseAlipay(null).bound)
        val record = parseWithdrawal(JSONObject("""{"id":9,"status":1,"payout":{"amount_cents":100,"coin_cost":"0.15","state":"processing"}}"""))
        assertEquals(100L, record.amountCents)
        assertEquals(BigDecimal("0.15"), record.coin)
    }

    @Test fun failureEventIncludesSessionCredential() {
        val session = AdSession("ads_test", "req_test", "placement", "session-credential", true,
            BigDecimal("0.01"), null, "42", "ads_test.proof")
        val body = adEventBody(session, "failure-event")
        assertEquals("session-credential", body.getString("session_token"))
        assertEquals("failure-event", body.getString("event_id"))
    }
}
