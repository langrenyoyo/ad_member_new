package com.example.idiomquiz.ads

import android.app.Activity
import android.os.SystemClock
import com.anythink.core.api.ATAdStatusInfo
import com.anythink.core.api.ATAdInfo
import com.anythink.banner.api.ATBannerView
import com.anythink.interstitial.api.ATInterstitial
import com.anythink.nativead.api.ATNative
import com.anythink.rewardvideo.api.ATRewardVideoAd
import com.anythink.splashad.api.ATSplashAd
import com.example.idiomquiz.data.AppBootstrap
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlin.coroutines.coroutineContext
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

/** Main-thread SDK cache loading, without rendering or awarding an impression. */
object StartupAdCache {
    private data class Entry(val owner: Activity, val unit: String, val ad: Any,
        val status: () -> ATAdStatusInfo, val destroy: () -> Unit,
        val created: Long = SystemClock.elapsedRealtime())
    private val entries = mutableMapOf<String, Entry>()

    fun take(kind: String, activity: Activity, unit: String): Any? {
        val entry = entries.remove(kind) ?: return null
        if (entry.owner !== activity || entry.unit != unit || SystemClock.elapsedRealtime()-entry.created > 120_000) {
            runCatching(entry.destroy); return null
        }
        return entry.ad
    }

    fun clear() {
        val old=entries.values.toList();entries.clear()
        old.forEach { runCatching(it.destroy) }
    }

    suspend fun load(activity: Activity, bootstrap: AppBootstrap, report: (JSONObject)->Unit, progress: (Int)->Unit) {
        clear()
        val runId=UUID.randomUUID().toString()
        val start=SystemClock.elapsedRealtime()
        val pending=mutableMapOf<String, Pair<String, ()->ATAdStatusInfo>>()
        var completed=0
        fun finish(kind:String,unit:String,status:String,info:ATAdInfo?=null) {
            val payload=JSONObject().put("event","preload").put("impression_id", "$runId-$kind")
                .put("game_id",bootstrap.gameId).put("ad_type",kind).put("ad_unit_id",unit)
                .put("status",status).put("duration_ms",SystemClock.elapsedRealtime()-start)
                .put("occurred_at",Instant.now().toString())
            // Each format owns a UUID, so outbox retries cannot replace another format.
            payload.put("impression_id",UUID.nameUUIDFromBytes("$runId:$kind".toByteArray()).toString())
            if(info!=null) payload.put("source_id",info.adsourceId.orEmpty().take(128))
                .put("network",info.networkName.orEmpty().take(128))
                .put("e_c",info.encEcpmInfo.orEmpty().take(8192))
                .put("e_c_cny",info.rmbEncEcpmInfo.orEmpty().take(8192))
                .put("s_id",if(info.secretId>0) info.secretId.toString() else "")
            runCatching { report(payload) }
            completed++;progress(completed)
        }
        try {
            for(kind in listOf("splash","rewarded","interstitial","banner","native")) {
                val unit=bootstrap.placements.firstOrNull { it.placement==kind || it.adType==kind }?.adUnitId.orEmpty()
                if(unit.isBlank()) {finish(kind,unit,"unconfigured");continue}
                runCatching {
                    val entry=when(kind) {
                        "splash" -> { val ad=ATSplashAd(activity,unit,null,5000)
                            Entry(activity,unit,ad,{ad.checkAdStatus()},{ad.onDestory()}).also { ad.loadAd() } }
                        // Isolated quote cache: no reward session exists at startup.
                        // Never reuse these ads for a later user's reward transaction.
                        "rewarded" -> {val ad=ATRewardVideoAd(activity,unit,
                            com.anythink.core.api.ATAdCreateConfig.Builder().setMultiton(true).build())
                            Entry(activity,unit,ad,{ad.checkAdStatus()},{ad.destroyAd()}).also { ad.load() } }
                        "interstitial" -> {val ad=ATInterstitial(activity,unit)
                            Entry(activity,unit,ad,{ad.checkAdStatus()},{ad.destroyAd()}).also { ad.load() } }
                        "banner" -> {val ad=ATBannerView(activity);ad.setPlacementId(unit)
                            Entry(activity,unit,ad,{ad.checkAdStatus()},{ad.destroy()}).also { ad.loadAd() } }
                        else -> {val ad=ATNative(activity,unit,null)
                            Entry(activity,unit,ad,{ad.checkAdStatus()},{ad.destroyAd()}).also { ad.makeAdRequest() } }
                    }
                    entries[kind]=entry;pending[kind]=unit to entry.status
                    android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                        if(entries[kind]===entry) {entries.remove(kind);runCatching(entry.destroy)}
                    },120_000)
                }.onFailure { finish(kind,unit,"failed") }
            }
            while(pending.isNotEmpty()) {
                coroutineContext.ensureActive()
                if(activity.isFinishing || activity.isDestroyed) break
                val elapsed=SystemClock.elapsedRealtime()-start
                for((kind,pair) in pending.toMap()) {
                    val status=runCatching {pair.second()}.getOrNull()
                    val outcome=when {
                        status?.isReady==true -> "loaded"
                        elapsed>=10_000 -> "timeout"
                        elapsed>=2000 && status?.isLoading==false -> "failed"
                        else -> null
                    } ?: continue
                    finish(kind,pair.first,outcome,if(outcome=="loaded")status?.getATTopAdInfo() else null)
                    pending.remove(kind)
                    if(outcome!="loaded" || kind=="rewarded") entries.remove(kind)?.let {runCatching(it.destroy)}
                }
                if(pending.isNotEmpty())delay(150)
            }
        } finally {
            if(pending.isNotEmpty())clear()
        }
    }
}
