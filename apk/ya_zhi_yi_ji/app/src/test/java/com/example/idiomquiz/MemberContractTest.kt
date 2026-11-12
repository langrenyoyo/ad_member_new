package com.example.idiomquiz

import com.example.idiomquiz.data.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.math.BigDecimal

class MemberContractTest {
    @Test fun paginationUsesActualReturnedRows() {
        val page = parseMemberPage(JSONObject("""{"data":{"total":23,"items":[{"id":21},{"id":22}]}}"""), 20)
        assertEquals(22, page.nextOffset)
        assertTrue(page.hasMore)
        assertFalse(parseMemberPage(JSONObject("""{"data":{"total":23,"items":[]}}"""), 23).hasMore)
    }
    @Test fun malformedPageIsAnErrorRatherThanEmptyHistory() {
        assertThrows(Exception::class.java) { parseMemberPage(JSONObject("""{"data":{}}""")) }
    }
    @Test fun subsidyAmountsRejectNegativeAndFractionalCents() {
        assertEquals(BigDecimal("12.30"), moneyInput("12.30"))
        listOf("0", "-1", "1.001", "NaN", "").forEach { value ->
            assertThrows(IllegalArgumentException::class.java) { moneyInput(value) }
        }
        assertEquals("0.01", centsText(1))
    }
    @Test fun passwordMatchesServerAsciiPolicyAndConfirmation() {
        validateNewPassword("abc12345", "abc12345")
        assertThrows(IllegalArgumentException::class.java) { validateNewPassword("中文中文1234", "中文中文1234") }
        assertThrows(IllegalArgumentException::class.java) { validateNewPassword("abc12345", "other") }
    }
    @Test fun payoutStateTakesPrecedenceOverReviewStatus() {
        assertEquals("打款处理中", withdrawalStatus(JSONObject("""{"status":1,"payout":{"state":"processing"}}""")))
        assertEquals("已到账", withdrawalStatus(JSONObject("""{"status":1,"payout":{"state":"succeeded"}}""")))
        assertEquals("已驳回", withdrawalStatus(JSONObject("""{"status":2,"payout":null}""")))
    }
}
