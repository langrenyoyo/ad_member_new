package com.example.idiomquiz

import com.example.idiomquiz.ui.adFailureMessage
import org.junit.Assert.assertEquals
import org.junit.Test

class AdFailureMessageTest {
    @Test fun absentOrBlankConfigurationUsesSafeDefault() {
        for (value in listOf(null, "", "  ", "x".repeat(201))) {
            assertEquals("暂时无法获得广告", adFailureMessage(value))
        }
    }
    @Test fun usesConfiguredCopy() {
        assertEquals("请稍后再试", adFailureMessage(" 请稍后再试 "))
    }
}
