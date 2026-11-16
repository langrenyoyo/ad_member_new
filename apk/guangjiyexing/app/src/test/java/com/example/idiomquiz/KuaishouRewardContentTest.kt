package com.example.idiomquiz

import com.example.idiomquiz.ads.KuaishouRewardContent
import com.kwad.sdk.api.KsRewardVideoAd
import com.kwad.sdk.api.model.KSAdInfoData
import java.lang.reflect.Proxy
import org.junit.Assert.*
import org.junit.Test

class KuaishouRewardContentTest {
    private fun material(title: String = "推广商品", app: String = "推广应用", creative: Long = 12345) =
        KSAdInfoData.obtain().setProductName(title).setAppName(app).setCreativeId(creative)

    private fun ad(read: () -> List<KSAdInfoData>?): KsRewardVideoAd =
        Proxy.newProxyInstance(KsRewardVideoAd::class.java.classLoader, arrayOf(KsRewardVideoAd::class.java)) { _, method, _ ->
            if (method.name == "getKSAdInfoDatas") read() else null
        } as KsRewardVideoAd

    @Test fun publicRewardGetterProvidesNamesAndCreativeWithoutChangingOriginalData() {
        val original = mapOf<String, Any?>("ecpm" to 0.01, "llsid" to "request-123")
        val result = KuaishouRewardContent.enrich(original, ad { listOf(material()) })
        assertEquals("推广商品", result["title"])
        assertEquals("推广应用", result["app_name"])
        assertEquals("12345", result["creative_id"])
        assertEquals(0.01, result["ecpm"])
        assertFalse(original.containsKey("title"))
        assertFalse(result.containsKey("advertiser"))
        assertFalse(result.containsKey("app_package"))
    }

    @Test fun missingOrThrowingGetterKeepsExistingMetadata() {
        val original = mapOf<String, Any?>("title" to "已知名称", "price" to 2)
        assertEquals(original, KuaishouRewardContent.enrich(original, null))
        assertEquals(original, KuaishouRewardContent.enrich(original, ad { error("SDK unavailable") }))
        assertTrue(KuaishouRewardContent.enrich(null, ad { null }).isEmpty())
    }

    @Test fun ambiguousMultipleCreativesAreNotAssignedToOneDisplay() {
        assertTrue(KuaishouRewardContent.enrich(null, ad { listOf(material(), material("另一商品")) }).isEmpty())
        assertTrue(KuaishouRewardContent.enrich(null, ad { emptyList() }).isEmpty())
    }

    @Test fun blankPlaceholdersAndZeroCreativeAreOmitted() {
        assertTrue(KuaishouRewardContent.enrich(null, ad { listOf(material(" null ", "undefined", 0)) }).isEmpty())
    }

    @Test fun earlierValuesArePreservedAndDifferentAdsStayIsolated() {
        val first = KuaishouRewardContent.enrich(null, ad { listOf(material()) })
        val second = KuaishouRewardContent.enrich(null, ad { listOf(material("第二商品", "第二应用", 67890)) })
        assertEquals("推广商品", first["title"])
        assertEquals("第二商品", second["title"])
        assertEquals("67890", second["creative_id"])
        val preserved = KuaishouRewardContent.enrich(mapOf("title" to "已有标题"), ad { listOf(material()) })
        assertEquals("已有标题", preserved["title"])
        assertEquals("推广应用", preserved["app_name"])
    }

    @Test fun lateMaterialIsReadAtCallbacksAndKnownContentSurvivesLaterFailures() {
        var ready = false
        var fail = false
        val source = ad {
            if (fail) error("SDK getter unavailable")
            if (ready) listOf(material()) else emptyList()
        }
        val values = KuaishouRewardContent.enrich(null, source)
        assertFalse(values.containsKey("title"))
        ready = true
        KuaishouRewardContent.refresh(values, "shown")
        assertEquals("推广商品", values["title"])
        fail = true
        KuaishouRewardContent.refresh(values, "closed")
        assertEquals("12345", values["creative_id"])
        assertTrue(values.values.all { it is String })
    }
}
