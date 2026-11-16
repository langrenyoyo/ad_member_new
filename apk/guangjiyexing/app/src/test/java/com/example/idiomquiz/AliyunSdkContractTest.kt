package com.example.idiomquiz

import com.example.idiomquiz.security.AliyunSdkContract
import org.junit.Assert.*
import org.junit.Test

class AliyunSdkContractTest {
    @Test fun acceptsDocumentedSuccessAndRejectsZeroAndHttpSuccess() {
        val token = "Tk-test-valid-device-token"
        assertEquals(token, AliyunSdkContract.checkedToken(10000, token))
        for (code in listOf(0, 200, 10001, 10012)) {
            assertThrows(IllegalStateException::class.java) { AliyunSdkContract.checkedToken(code, token) }
        }
    }

    @Test fun weakNetworkTokenIsPreservedWithoutTruncation() {
        val token = "UF" + "a+/=".repeat(800)
        assertEquals(token, AliyunSdkContract.checkedToken(10000, token))
    }

    @Test fun rejectsMissingAndOversizeTokensEvenOnSuccess() {
        for (token in listOf(null, "", "short", "a".repeat(16385))) {
            assertThrows(IllegalStateException::class.java) { AliyunSdkContract.checkedToken(10000, token) }
        }
    }

    @Test fun respectsMainlandCollectionIntervalAndReadableMismatchError() {
        assertTrue(AliyunSdkContract.MIN_INIT_INTERVAL_MS > 2000)
        assertTrue(AliyunSdkContract.errorMessage(10012).contains("不匹配"))
    }
}
