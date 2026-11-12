package com.example.idiomquiz

import com.example.idiomquiz.ui.onboardingBlocks
import com.example.idiomquiz.ui.onboardingFailureCode
import org.junit.Assert.*
import org.junit.Test

class OnboardingGateTest {
    @Test fun missingBackendDoesNotBypassOnboarding() {
        assertTrue(com.example.idiomquiz.ui.onboardingFailureMessage(404, "Not Found").contains("联系管理员"))
        assertTrue(onboardingBlocks(false, onboardingFailureCode(404, null), false, false, false))
    }
    @Test fun transientFailurePreservesLoadedAccess() {
        assertNull(onboardingFailureCode(null, null))
        assertNull(onboardingFailureCode(503, null))
        assertFalse(onboardingBlocks(true, null, false, false, false))
        assertTrue(onboardingBlocks(false, null, false, false, false))
    }
    @Test fun explicitDenialStillBlocks() {
        assertEquals("DEVICE_COOLDOWN", onboardingFailureCode(403, "DEVICE_COOLDOWN"))
        assertTrue(onboardingBlocks(true, "DEVICE_COOLDOWN", false, false, false))
        assertTrue(onboardingBlocks(true, "ACCESS_DENIED", false, false, false))
    }
    @Test fun revokedPermissionAndOtherRequirementsRemainGated() {
        assertTrue(onboardingBlocks(true, null, false, true, false))
        assertTrue(onboardingBlocks(true, null, true, false, false))
        assertTrue(onboardingBlocks(true, null, false, false, true))
    }
}
