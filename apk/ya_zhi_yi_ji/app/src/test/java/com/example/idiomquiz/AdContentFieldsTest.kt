package com.example.idiomquiz

import com.example.idiomquiz.ads.AdContentFields
import com.example.idiomquiz.ads.AdContentSnapshot
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class AdContentFieldsTest {
    @Test fun emptyEarlyReadDoesNotPreventContentAtImpression() {
        var loaded = false
        val snapshot = AdContentSnapshot {
            if (loaded) JSONObject().put("title", "实际广告").put("app_package", "com.example.ad") else JSONObject()
        }
        assertEquals("", snapshot.refresh().getString("title"))
        loaded = true
        assertEquals("实际广告", snapshot.refresh().getString("title"))
        loaded = false
        assertEquals("com.example.ad", snapshot.refresh().getString("app_package"))
    }

    @Test fun changingSdkObjectAndReturnedSnapshotCannotRewritePreviousEvent() {
        val sdk = JSONObject().put("title", "第一条素材")
        val snapshot = AdContentSnapshot { sdk }
        val shown = snapshot.refresh()
        sdk.put("title", "更新后的素材")
        assertEquals("更新后的素材", snapshot.refresh().getString("title"))
        assertEquals("第一条素材", shown.getString("title"))
        shown.put("title", "调用者修改")
        assertEquals("更新后的素材", snapshot.refresh().getString("title"))
    }

    @Test fun getterFailureKeepsKnownDataAndDifferentAdsAreIsolated() {
        var fail = false
        val first = AdContentSnapshot {
            if (fail) error("SDK getter unavailable") else JSONObject().put("title", "原素材")
        }
        first.refresh()
        fail = true
        assertEquals("原素材", first.refresh().getString("title"))
        assertEquals("", AdContentSnapshot { JSONObject() }.refresh().getString("title"))
    }

    @Test fun copiesOnlyWhitelistedScalarsAndRejectsNullPlaceholders() {
        val fields = AdContentFields.fromMap(mapOf(
            "title" to " null ", "ad_title" to " 真实标题 ", "appName" to JSONObject().put("token", "secret"),
            "creativeId" to 12345L, "session_token" to "must-not-copy", "appPackage" to "undefined"
        ))
        assertEquals("真实标题", fields.getString("title"))
        assertEquals("", fields.getString("app_name"))
        assertEquals("", fields.getString("app_package"))
        assertEquals("12345", fields.getString("creative_id"))
        assertFalse(fields.has("session_token"))
    }

    @Test fun directPlacementWinsButMissingTitleUsesMaterial() {
        val content = AdContentFields.merge(
            JSONObject().put("network_placement_id", "actual-placement"),
            AdContentFields.fromMap(mapOf("placement_id" to "fallback-placement", "title" to " ")),
            JSONObject().put("title", "素材标题").put("advertiser", "广告主")
        )
        assertEquals("actual-placement", content.getString("network_placement_id"))
        assertEquals("素材标题", content.getString("title"))
        assertEquals("广告主", content.getString("advertiser"))
        assertEquals(255, AdContentFields.fromMap(mapOf("title" to "a".repeat(300))).getString("title").length)
    }
}
