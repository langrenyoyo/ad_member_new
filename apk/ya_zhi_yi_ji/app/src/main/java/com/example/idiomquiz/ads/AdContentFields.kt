package com.example.idiomquiz.ads

import org.json.JSONObject

/** Only copy known content fields, never serialize opaque SDK objects or tracking payloads. */
internal object AdContentFields {
    private val aliases = linkedMapOf(
        "title" to listOf("title", "ad_title", "adTitle"),
        "app_name" to listOf("app_name", "appName"),
        "app_package" to listOf("app_package", "package_name", "appPackage", "appPackageName"),
        "creative_id" to listOf("creative_id", "creativeId"),
        "advertiser" to listOf("advertiser", "advertiser_name", "advertiserName"),
        "network_placement_id" to listOf("network_placement_id", "placement_id", "networkPlacementId")
    )

    fun text(value: Any?, numeric: Boolean = false): String {
        val raw = when {
            value is String -> value
            numeric && value is Number -> value.toString()
            else -> return ""
        }.trim()
        return raw.takeUnless { it.equals("null", true) || it.equals("undefined", true) }.orEmpty().take(255)
    }

    fun fromMap(values: Map<String, *>): JSONObject = JSONObject().apply {
        aliases.forEach { (field, names) ->
            val numeric = field in setOf("creative_id", "network_placement_id")
            put(field, names.firstNotNullOfOrNull { text(values[it], numeric).takeIf(String::isNotBlank) }.orEmpty())
        }
    }

    /** First non-empty value wins; an unavailable later SDK getter cannot erase known content. */
    fun merge(vararg sources: JSONObject): JSONObject = JSONObject().apply {
        aliases.keys.forEach { field ->
            put(field, sources.firstNotNullOfOrNull {
                text(it.opt(field), field in setOf("creative_id", "network_placement_id")).takeIf(String::isNotBlank)
            }.orEmpty())
        }
    }
}

/** Re-read a single native ad at render and event time without retaining mutable SDK maps. */
internal class AdContentSnapshot(private val read: () -> JSONObject) {
    private var known = JSONObject()

    fun refresh(): JSONObject {
        val latest = runCatching(read).getOrElse { JSONObject() }
        known = AdContentFields.merge(latest, known)
        return JSONObject(known.toString())
    }
}
