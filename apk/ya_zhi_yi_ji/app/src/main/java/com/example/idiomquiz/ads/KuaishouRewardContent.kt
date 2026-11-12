package com.example.idiomquiz.ads

import android.util.Log
import com.kwad.sdk.api.KsRewardVideoAd
import com.kwad.sdk.api.model.KSAdInfoData
import java.lang.ref.WeakReference

/** Called by the version-checked TAKU adapter bridge, using this adapter's own ad. */
object KuaishouRewardContent {
    @JvmStatic
    fun enrich(original: Map<String, Any?>?, ad: KsRewardVideoAd?): Map<String, Any?> =
        ContentMap(original, ad).apply { refresh("adapter") }

    /** TAKU retains this map in ATAdInfo. Its entries contain only ordinary metadata values. */
    internal class ContentMap(original: Map<String, Any?>?, ad: KsRewardVideoAd?) :
        LinkedHashMap<String, Any?>(original.orEmpty()) {
        private val source = WeakReference(ad)

        @Synchronized fun refresh(stage: String) {
            val records = runCatching { source.get()?.ksAdInfoDatas }.getOrNull()
            val fields = readSingleMaterial(records)
            fields.forEach { (key, value) ->
                if (AdContentFields.text(get(key), key == "creative_id").isBlank()) put(key, value)
            }
            runCatching {
                Log.i("KsContentBridge", "stage=$stage records=${records?.size ?: -1} title=${containsKey("title")} " +
                    "app=${containsKey("app_name")} creative=${containsKey("creative_id")}")
            }
        }
    }

    internal fun refresh(values: Map<String, Any?>?, stage: String) {
        (values as? ContentMap)?.refresh(stage)
    }

    internal fun readSingleMaterial(records: List<KSAdInfoData>?): Map<String, String> {
        // Some ads contain multiple creatives. Do not attribute an arbitrary creative to the display.
        val material = records?.singleOrNull() ?: return emptyMap()
        return buildMap {
            fun copy(key: String, read: () -> String?) {
                val value = AdContentFields.text(runCatching(read).getOrNull())
                if (value.isNotBlank()) put(key, value)
            }
            copy("title") { material.productName }
            copy("app_name") { material.appName }
            val creative = runCatching { material.creativeId }.getOrNull()
            if (creative != null && creative > 0) put("creative_id", creative.toString())
        }
    }

}
