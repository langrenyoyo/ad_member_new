package com.example.idiomquiz

import com.example.idiomquiz.data.parseRegistrationPolicy
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class RegistrationPolicyTest {
    @Test fun registrationInviteAndBusinessInviteAreIndependent() {
        val policy = parseRegistrationPolicy(JSONObject("""{"require_registration_invite":true,"require_invite":false}"""))
        assertTrue(policy.requireRegistrationInvite)
        assertFalse(policy.requireInvite)
    }

    @Test fun optionalRegistrationInviteDoesNotDisableBusinessRequirement() {
        val policy = parseRegistrationPolicy(JSONObject("""{"require_registration_invite":false,"require_invite":true}"""))
        assertFalse(policy.requireRegistrationInvite)
        assertTrue(policy.requireInvite)
    }

    @Test(expected = org.json.JSONException::class)
    fun missingRegistrationRuleIsNotTreatedAsOptional() {
        parseRegistrationPolicy(JSONObject("""{"require_invite":false}"""))
    }
}
