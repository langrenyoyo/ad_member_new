package com.example.idiomquiz.ads

import android.app.Activity
import android.content.Context
import android.util.Log
import android.view.ViewGroup
import android.view.View
import android.widget.FrameLayout
import com.anythink.banner.api.ATBannerListener
import com.anythink.banner.api.ATBannerView
import com.anythink.core.api.ATAdInfo
import com.anythink.core.api.ATAdConst
import android.os.Handler
import android.os.Looper
import com.example.idiomquiz.data.AdSession
import com.anythink.core.api.ATSDK
import com.anythink.core.api.AdError
import com.anythink.splashad.api.ATSplashAd
import com.anythink.splashad.api.ATSplashAdExtraInfo
import com.anythink.splashad.api.ATSplashAdListener
import com.anythink.interstitial.api.ATInterstitial
import com.anythink.interstitial.api.ATInterstitialListener
import com.anythink.rewardvideo.api.ATRewardVideoAd
import com.anythink.rewardvideo.api.ATRewardVideoListener
import com.anythink.nativead.api.ATNative
import com.anythink.nativead.api.ATNativeAdView
import com.anythink.nativead.api.ATNativeEventListener
import com.anythink.nativead.api.ATNativeNetworkListener
import com.anythink.nativead.api.ATNativeDislikeListener
import com.example.idiomquiz.BuildConfig
import com.example.idiomquiz.data.AdPlacement
import com.example.idiomquiz.data.AppBootstrap
import org.json.JSONObject
import org.json.JSONArray
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.CoroutineStart

object AnyThinkAdManager {
    private const val TAG = "IdiomQuizAds"
    private var initialized = false
    private var splashRequested = false
    private var splashAd: ATSplashAd? = null
    private var splashContainer: FrameLayout? = null
    private var splashTimeout: Runnable? = null
    private var splashShowing = false

    fun preloadReporter(): (JSONObject) -> Unit = secondaryEventReporter?.invoke() ?: {}

    fun releaseActivityAds() {
        destroySplash()
        StartupAdCache.clear()
        clearInterstitialPreload()
    }
    private var interstitialAd: ATInterstitial? = null
    private data class WarmInterstitial(val activity: Activity, val unit: String, val ad: ATInterstitial,
        val started: Long = android.os.SystemClock.elapsedRealtime(), var ready: Boolean = false,
        var loaded: (() -> Unit)? = null, var failed: ((String) -> Unit)? = null)
    private var warmInterstitial: WarmInterstitial? = null

    fun clearInterstitialPreload() {
        warmInterstitial?.ad?.destroyAd()
        warmInterstitial = null
    }

    /** Load only; no impression or reward is reported until an explicit show. */
    fun preloadInterstitial(activity: Activity, placement: AdPlacement) {
        if (!initialized || placement.adUnitId.isBlank() || activity.isFinishing || activity.isDestroyed) return
        warmInterstitial?.let {
            if (it.activity === activity && it.unit == placement.adUnitId &&
                android.os.SystemClock.elapsedRealtime() - it.started < 120_000) return
        }
        clearInterstitialPreload()
        val ad = StartupAdCache.take("interstitial", activity, placement.adUnitId) as? ATInterstitial
            ?: ATInterstitial(activity, placement.adUnitId)
        val warm = WarmInterstitial(activity, placement.adUnitId, ad)
        warmInterstitial = warm
        ad.setAdListener(object : ATInterstitialListener {
            override fun onInterstitialAdLoaded() { mainHandler.post {
                warm.ready = true; warm.loaded?.invoke()
            } }
            override fun onInterstitialAdLoadFail(error: AdError) { mainHandler.post {
                if (warmInterstitial === warm) clearInterstitialPreload()
                warm.failed?.invoke("插屏广告加载失败")
            } }
            override fun onInterstitialAdClicked(info: ATAdInfo) = Unit
            override fun onInterstitialAdShow(info: ATAdInfo) = Unit
            override fun onInterstitialAdClose(info: ATAdInfo) = Unit
            override fun onInterstitialAdVideoStart(info: ATAdInfo) = Unit
            override fun onInterstitialAdVideoEnd(info: ATAdInfo) = Unit
            override fun onInterstitialAdVideoError(error: AdError) = Unit
        })
        mainHandler.postDelayed({ if (warmInterstitial === warm) clearInterstitialPreload() }, 120_000L)
        if (ad.isAdReady) warm.ready = true
        else runCatching { ad.load() }.onFailure { if (warmInterstitial === warm) clearInterstitialPreload() }
    }
    private var rewardedAd: ATRewardVideoAd? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    @Volatile private var secondaryEventReporter: (() -> (JSONObject) -> Unit)? = null

    fun setSecondaryEventReporter(reporter: () -> (JSONObject) -> Unit) {
        secondaryEventReporter = reporter
    }

    val isInitialized: Boolean
        get() = initialized

    fun initialize(context: Context, bootstrap: AppBootstrap): Boolean {
        Log.i(
            TAG,
            "Ad bootstrap: gameStatus=${bootstrap.gameStatus}, adStatus=${bootstrap.adStatus}, " +
                "enabled=${bootstrap.adsEnabled}, placements=${bootstrap.placements.joinToString { "${it.placement}/${it.adType}/${it.adUnitId}" }}"
        )
        if (!bootstrap.isAdAvailable()) {
            Log.i(TAG, "Ads skipped: game or ad configuration is disabled")
            return false
        }

        val appId = bootstrap.adAppId.orEmpty().trim()
            .ifEmpty { BuildConfig.ANYTHINK_APP_ID.trim() }
        val appKey = bootstrap.adAppKey.orEmpty().trim()
            .ifEmpty { BuildConfig.ANYTHINK_APP_KEY.trim() }
        if (appId.isEmpty() || appKey.isEmpty()) {
            Log.i(TAG, "Ads skipped: server or build AnyThink appId/appKey are not configured")
            return false
        }
        if (initialized) return true

        return runCatching {
            ATSDK.init(context.applicationContext, appId, appKey)
            initialized = true
            Log.i(TAG, "AnyThink initialized with bootstrap ad credentials")
        }.onFailure { error ->
            Log.e(TAG, "AnyThink initialization failed", error)
        }.isSuccess
    }

    fun loadAndShowSplash(activity: Activity, placement: AdPlacement) {
        val reporter = secondaryEventReporter?.invoke()
        Log.i(TAG, "Splash request: initialized=$initialized, requested=$splashRequested, placement=${placement.adUnitId}")
        if (!initialized || splashRequested || placement.adUnitId.isBlank()) return
        splashRequested = true
        var impressionId: String? = null

        lateinit var ad: ATSplashAd
        val listener = object : ATSplashAdListener {
            override fun onAdLoaded(isTimeout: Boolean) {
                mainHandler.post {
                if (splashAd !== ad) return@post
                if (isTimeout && !ad.isAdReady) {
                    Log.w(TAG, "Splash ad load timed out")
                    destroySplash()
                    return@post
                }
                showSplash(activity, ad)
                }
            }

            override fun onAdLoadTimeout() {
                mainHandler.post {
                if (splashAd !== ad) return@post
                Log.w(TAG, "Splash ad load timeout callback")
                if (ad.isAdReady) showSplash(activity, ad) else destroySplash()
                }
            }

            override fun onNoAdError(error: AdError) {
                Log.w(TAG, "Splash ad load failed: ${error.fullErrorInfo}")
                mainHandler.post { if (splashAd === ad) destroySplash() }
            }

            override fun onAdShow(adInfo: ATAdInfo) {
                Log.d(TAG, "Splash ad shown")
                impressionId = UUID.randomUUID().toString()
                reportSecondaryEvent(reporter, placement, impressionId!!, "shown", adInfo)
            }

            override fun onAdClick(adInfo: ATAdInfo) {
                Log.d(TAG, "Splash ad clicked")
                impressionId?.let { reportSecondaryEvent(reporter, placement, it, "clicked", adInfo) }
            }

            override fun onAdDismiss(adInfo: ATAdInfo, extraInfo: ATSplashAdExtraInfo) {
                Log.d(TAG, "Splash ad dismissed")
                mainHandler.post {
                    if (splashAd === ad) destroySplash()
                    runCatching { impressionId?.let { reportSecondaryEvent(reporter, placement, it, "closed", adInfo) } }
                }
            }
        }
        ad = StartupAdCache.take("splash", activity, placement.adUnitId) as? ATSplashAd
            ?: ATSplashAd(activity, placement.adUnitId, listener, 5000)
        ad.setAdListener(listener)
        splashAd = ad
        splashTimeout = Runnable { if (splashAd === ad) destroySplash() }
        mainHandler.postDelayed(splashTimeout!!, 15_000)
        runCatching { if (ad.isAdReady) showSplash(activity,ad) else ad.loadAd() }
            .onFailure { destroySplash() }
    }

    fun createBannerView(
        context: Context,
        placement: AdPlacement,
        onStatus: (String) -> Unit = {}
    ): ATBannerView {
        val reporter = secondaryEventReporter?.invoke()
        onStatus("loading")
        return ((context as? Activity)?.let { StartupAdCache.take("banner", it, placement.adUnitId) as? ATBannerView }
            ?: ATBannerView(context)).apply {
            var impressionId: String? = null
            var latestAdInfo: ATAdInfo? = null
            setPlacementId(placement.adUnitId)
            setBannerAdListener(object : ATBannerListener {
                override fun onBannerLoaded() {
                    Log.d(TAG, "Banner ad loaded: ${placement.adUnitId}")
                    onStatus("loaded")
                }

                override fun onBannerFailed(error: AdError) {
                    Log.w(TAG, "Banner ad load failed: ${error.fullErrorInfo}")
                    onStatus("failed: ${error.fullErrorInfo}")
                }

                override fun onBannerClicked(adInfo: ATAdInfo) {
                    latestAdInfo = adInfo
                    Log.d(TAG, "Banner ad clicked")
                    impressionId?.let { reportSecondaryEvent(reporter, placement, it, "clicked", adInfo) }
                }

                override fun onBannerShow(adInfo: ATAdInfo) {
                    latestAdInfo = adInfo
                    Log.d(TAG, "Banner ad shown")
                    impressionId = UUID.randomUUID().toString()
                    reportSecondaryEvent(reporter, placement, impressionId!!, "shown", adInfo)
                }

                override fun onBannerClose(adInfo: ATAdInfo) {
                    latestAdInfo = adInfo
                    Log.d(TAG, "Banner ad closed")
                    impressionId?.let { reportSecondaryEvent(reporter, placement, it, "closed", adInfo) }
                    impressionId = null
                }

                override fun onBannerAutoRefreshed(adInfo: ATAdInfo) {
                    latestAdInfo = adInfo
                    Log.d(TAG, "Banner ad auto-refreshed")
                    impressionId = UUID.randomUUID().toString()
                    reportSecondaryEvent(reporter, placement, impressionId!!, "shown", adInfo)
                }

                override fun onBannerAutoRefreshFail(error: AdError) {
                    Log.w(TAG, "Banner ad auto-refresh failed: ${error.fullErrorInfo}")
                }
            })
            loadAd()
        }
    }

    fun destroyBannerView(view: ATBannerView) {
        view.destroy()
    }

    /** Entry ads are independent of rewarded sessions and never award coins. */
    suspend fun showEntryInterstitial(activity: Activity, placement: AdPlacement, isCurrent: () -> Boolean) {
        check(initialized && interstitialAd == null && rewardedAd == null) { "广告尚未就绪或正在展示" }
        check(placement.adUnitId.isNotBlank()) { "未配置插屏广告" }
        if (!isCurrent() || activity.isFinishing || activity.isDestroyed) {
            throw kotlinx.coroutines.CancellationException("广告页面或登录状态已变更")
        }
        awaitAdClose(dispose = { cancel ->
            if (Looper.myLooper() == Looper.getMainLooper()) cancel() else mainHandler.post { cancel() }
        }) { closed, failed ->
            loadAndShowInterstitial(activity, placement, isCurrent, closed, failed, loadTimeoutMs = 3_000L)
        }
    }

    /** One user request owns all three fullscreen ads; no cooldown-triggered extras. */
    suspend fun showRewardedGroup(
        activity: Activity,
        session: AdSession,
        interstitial: AdPlacement,
        isCurrent: () -> Boolean,
        onReward: (JSONObject) -> Unit,
        onRewardClosed: () -> Unit,
        onShown: () -> Unit,
        onMetadata: (String, JSONObject) -> Unit
    ) {
        check(initialized && interstitialAd == null && rewardedAd == null) { "广告尚未就绪或正在展示" }
        check(interstitial.adUnitId.isNotBlank()) { "未配置插屏广告，无法展示广告组" }
        fun checkOwner() {
            if (!isCurrent() || activity.isFinishing || activity.isDestroyed) {
                throw kotlinx.coroutines.CancellationException("广告页面或登录状态已变更")
            }
        }
        val dispose: (() -> Unit) -> Unit = { cancel ->
            if (Looper.myLooper() == Looper.getMainLooper()) cancel() else mainHandler.post { cancel() }
        }
        coroutineScope {
            val gate = RewardedShowGate()
            val reward = async(start = CoroutineStart.UNDISPATCHED) {
                awaitAdClose(dispose) { closed, failed ->
                    showRewarded(activity, session, onReward,
                        onClosed = { onRewardClosed(); closed() }, onShown, failed, onMetadata, isCurrent,
                        deferShow = gate::ready)
                }
            }
            try {
                checkOwner()
                awaitAdClose(dispose) { closed, failed ->
                    loadAndShowInterstitial(activity, interstitial, isCurrent, closed, failed)
                }
                checkOwner()
                preloadInterstitial(activity, interstitial)
                gate.open()
                reward.await()
                checkOwner()
                awaitAdClose(dispose) { closed, failed ->
                    loadAndShowInterstitial(activity, interstitial, isCurrent, closed, failed)
                }
            } finally {
                gate.cancel()
                reward.cancel()
            }
        }
    }

    private fun loadAndShowInterstitial(
        activity: Activity,
        placement: AdPlacement,
        isCurrent: () -> Boolean,
        onClosed: () -> Unit,
        onFailure: (String) -> Unit,
        loadTimeoutMs: Long = 60_000L
    ): () -> Unit {
        val warm = warmInterstitial?.takeIf { it.activity === activity && it.unit == placement.adUnitId &&
            android.os.SystemClock.elapsedRealtime() - it.started < 120_000 }
        if (warm == null) clearInterstitialPreload() else warmInterstitial = null
        val ad = warm?.ad ?: ATInterstitial(activity, placement.adUnitId)
        val requestedAt = android.os.SystemClock.elapsedRealtime()
        val reporter = secondaryEventReporter?.invoke()
        interstitialAd = ad
        val lifecycle = RewardedLifecycle()
        var impressionId: String? = null
        lateinit var timeout: Runnable
        fun release() {
            if (!lifecycle.end()) return
            mainHandler.removeCallbacks(timeout)
            warm?.loaded = null
            warm?.failed = null
            if (interstitialAd === ad) interstitialAd = null
            runCatching { ad.destroyAd() }
        }
        fun fail(message: String) {
            if (lifecycle.ended) return
            release()
            onFailure(message)
        }
        timeout = Runnable { fail("插屏广告加载或展示超时，请重试") }
        val listener = object : ATInterstitialListener {
            override fun onInterstitialAdLoaded() {
                mainHandler.post {
                    if (interstitialAd !== ad || !lifecycle.loaded()) return@post
                    if (!isCurrent() || activity.isFinishing || activity.isDestroyed) {
                        fail("广告页面或登录状态已变更")
                        return@post
                    }
                    // Keep the watchdog until the SDK actually confirms the show.
                    Log.d(TAG, "Interstitial ready after ${android.os.SystemClock.elapsedRealtime() - requestedAt}ms; preloaded=${warm != null}")
                    runCatching { ad.show(activity) }.onFailure { fail("插屏广告展示失败") }
                }
            }
            override fun onInterstitialAdLoadFail(error: AdError) {
                mainHandler.post { fail("插屏广告加载失败：${error.fullErrorInfo}") }
            }
            override fun onInterstitialAdClicked(adInfo: ATAdInfo) {
                impressionId?.let { reportSecondaryEvent(reporter, placement, it, "clicked", adInfo) }
            }
            override fun onInterstitialAdShow(adInfo: ATAdInfo) {
                mainHandler.post {
                    if (lifecycle.impression()) {
                        mainHandler.removeCallbacks(timeout)
                        Log.d(TAG, "Interstitial shown after ${android.os.SystemClock.elapsedRealtime() - requestedAt}ms")
                        impressionId = UUID.randomUUID().toString()
                        reportSecondaryEvent(reporter, placement, impressionId!!, "shown", adInfo)
                    }
                }
            }
            override fun onInterstitialAdClose(adInfo: ATAdInfo) {
                mainHandler.post {
                    if (lifecycle.ended) return@post
                    release()
                    onClosed()
                    impressionId?.let { reportSecondaryEvent(reporter, placement, it, "closed", adInfo) }
                }
            }
            override fun onInterstitialAdVideoStart(adInfo: ATAdInfo) = Unit
            override fun onInterstitialAdVideoEnd(adInfo: ATAdInfo) = Unit
            override fun onInterstitialAdVideoError(error: AdError) {
                mainHandler.post { fail("插屏广告播放失败：${error.fullErrorInfo}") }
            }
        }
        ad.setAdListener(listener)
        warm?.loaded = { listener.onInterstitialAdLoaded() }
        warm?.failed = { fail(it) }
        mainHandler.postDelayed(timeout, loadTimeoutMs)
        if (warm != null) {
            if (warm.ready || ad.isAdReady) listener.onInterstitialAdLoaded()
        } else runCatching { ad.load() }.onFailure { fail("插屏广告加载失败") }
        return { release() }
    }

    /** One request owns one SDK instance; never preload with a finished session. */
    fun showRewarded(
        activity: Activity,
        session: AdSession,
        onReward: (JSONObject) -> Unit,
        onClosed: () -> Unit,
        onShown: () -> Unit,
        onFailure: (String) -> Unit,
        onMetadata: (String, org.json.JSONObject) -> Unit = { _, _ -> },
        isCurrent: () -> Boolean = { true },
        deferShow: ((() -> Unit) -> Unit) = { it() }
    ): () -> Unit {
        if (!initialized || rewardedAd != null) {
            onFailure("广告尚未就绪或正在加载")
            return {}
        }
        val userId = session.takuUserId
        val extraData = session.takuExtraData
        if (userId.isNullOrBlank() || extraData.isNullOrBlank()) {
            onFailure("服务器未返回广告奖励验证参数")
            return {}
        }
        val ad = ATRewardVideoAd(activity, session.adUnitId)
        rewardedAd = ad
        val lifecycle = RewardedLifecycle()
        fun metadata(event: String, info: ATAdInfo): JSONObject? =
            runCatching {
                KuaishouRewardContent.refresh(info.extInfoMap, event)
                val extra = info.extInfoMap.orEmpty()
                val payload = org.json.JSONObject().put("network", info.networkName.orEmpty().take(128))
                    .put("source_id", info.adsourceId.orEmpty().take(128)).put("format", info.format.orEmpty().take(64))
                    .put("extension_keys", org.json.JSONArray(extra.keys.take(50).map { it.take(100) }))
                    .put("e_c", info.encEcpmInfo.orEmpty())
                    .put("e_c_cny", info.rmbEncEcpmInfo.orEmpty())
                    .put("s_id", if (info.secretId > 0) info.secretId.toString() else "")
                    .put("sdk_request_id", info.requestId.orEmpty().take(256))
                    .put("sdk_show_id", info.showId.orEmpty().take(256))
                val content = contentFields(info)
                content.keys().forEach { payload.put(it, content.get(it)) }
                onMetadata(event, payload)
                payload
            }.getOrNull()
        lateinit var timeout: Runnable
        fun release() {
            if (!lifecycle.end()) return
            mainHandler.removeCallbacks(timeout)
            if (rewardedAd === ad) rewardedAd = null
            ad.destroyAd()
        }
        fun fail(message: String) {
            if (lifecycle.ended) return
            release()
            onFailure(message)
        }
        timeout = Runnable { fail("广告加载超时，请重试") }
        ad.setLocalExtra(mapOf(
            ATAdConst.KEY.USER_ID to userId,
            ATAdConst.KEY.USER_CUSTOM_DATA to extraData
        ))
        ad.setAdListener(object : ATRewardVideoListener {
            override fun onRewardedVideoAdLoaded() {
                mainHandler.post {
                    if (rewardedAd !== ad || !lifecycle.loaded()) return@post
                    mainHandler.removeCallbacks(timeout)
                    deferShow show@{
                    if (lifecycle.ended) return@show
                    if (!isCurrent() || activity.isFinishing || activity.isDestroyed) {
                        fail("页面已关闭或登录状态已变更")
                        return@show
                    }
                    if (session.expiresAtEpochMillis?.let { it <= System.currentTimeMillis() } == true) {
                        fail("广告会话已过期，请重试")
                        return@show
                    }
                    mainHandler.postDelayed(timeout, 15_000L)
                    runCatching { ad.show(activity) }.onFailure { fail("广告展示失败") }
                    }
                }
            }
            override fun onRewardedVideoAdFailed(error: AdError) {
                mainHandler.post { fail("广告加载失败：${error.fullErrorInfo}") }
            }
            override fun onRewardedVideoAdPlayStart(adInfo: ATAdInfo) {
                mainHandler.post { if (lifecycle.impression()) { mainHandler.removeCallbacks(timeout); metadata("shown", adInfo); onShown() } }
            }
            override fun onRewardedVideoAdPlayEnd(adInfo: ATAdInfo) = Unit
            override fun onRewardedVideoAdPlayFailed(error: AdError, adInfo: ATAdInfo) {
                mainHandler.post { fail("广告播放失败：${error.fullErrorInfo}") }
            }
            override fun onRewardedVideoAdClosed(adInfo: ATAdInfo) {
                mainHandler.post {
                    if (lifecycle.ended) return@post
                    metadata("closed", adInfo)
                    release()
                    onClosed()
                }
            }
            override fun onRewardedVideoAdPlayClicked(adInfo: ATAdInfo) {
                mainHandler.post { if (!lifecycle.ended) metadata("clicked", adInfo) }
            }
            override fun onReward(adInfo: ATAdInfo) {
                mainHandler.post {
                    if (lifecycle.reward()) {
                        val evidence = metadata("reward", adInfo) ?: JSONObject()
                        onReward(evidence)
                    }
                }
            }
        })
        mainHandler.postDelayed(timeout, 60_000L)
        runCatching { ad.load() }.onFailure { fail("广告加载失败") }
        return { release() }
    }

    fun loadNative(context: Context, placement: AdPlacement, onFailure: (String) -> Unit,
                   onReady: (ATNativeAdView) -> Unit): () -> Unit {
        if (!initialized || placement.adUnitId.isBlank()) {
            onFailure("原生广告服务暂不可用")
            return {}
        }
        val reporter = secondaryEventReporter?.invoke()
        var cancelled = false
        var loadedView: ATNativeAdView? = null
        lateinit var native: ATNative
        val nativeListener = object : ATNativeNetworkListener {
            override fun onNativeAdLoaded() {
                mainHandler.post {
                if (cancelled) return@post
                runCatching {
                val ad = native.getNativeAd() ?: error("No native ad returned")
                val adView = ATNativeAdView(context)
                loadedView = adView
                var impressionId: String? = null
                val materialContent = AdContentSnapshot { NativeAdRenderer.content(ad) }
                materialContent.refresh()
                ad.setNativeEventListener(object : ATNativeEventListener {
                    override fun onAdImpressed(view: ATNativeAdView, info: ATAdInfo) {
                        if (impressionId == null) impressionId = UUID.randomUUID().toString()
                        reportSecondaryEvent(reporter, placement, impressionId!!, "shown", info, materialContent.refresh())
                    }
                    override fun onAdClicked(view: ATNativeAdView, info: ATAdInfo) {
                        impressionId?.let { reportSecondaryEvent(reporter, placement, it, "clicked", info, materialContent.refresh()) }
                    }
                    override fun onAdVideoStart(view: ATNativeAdView) = Unit
                    override fun onAdVideoEnd(view: ATNativeAdView) = Unit
                    override fun onAdVideoProgress(view: ATNativeAdView, progress: Int) = Unit
                })
                ad.setDislikeCallbackListener(object : ATNativeDislikeListener() {
                    override fun onAdCloseButtonClick(view: ATNativeAdView, info: ATAdInfo) {
                        impressionId?.let { reportSecondaryEvent(reporter, placement, it, "closed", info, materialContent.refresh()) }
                        impressionId = null
                        view.visibility = View.GONE
                    }
                })
                adView.layoutParams = FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
                NativeAdRenderer.render(context, ad, adView) { native.destroyAd() }
                materialContent.refresh()
                onReady(adView)
                }.onFailure {
                    loadedView?.let { NativeAdRenderer.destroy(it) }
                    native.destroyAd()
                    onFailure("原生广告展示失败，请稍后重试")
                }
                }
            }
            override fun onNativeAdLoadFail(error: AdError) {
                mainHandler.post { if (!cancelled) { native.destroyAd(); onFailure("原生广告加载失败，请稍后重试") } }
            }
        }
        native = ((context as? Activity)?.let { StartupAdCache.take("native", it, placement.adUnitId) as? ATNative }
            ?: ATNative(context, placement.adUnitId, nativeListener))
        native.setAdListener(nativeListener)
        runCatching {
            if(native.checkAdStatus().isReady) nativeListener.onNativeAdLoaded() else native.makeAdRequest()
        }.onFailure { onFailure("原生广告请求失败，请稍后重试") }
        return {
            mainHandler.post {
                cancelled = true
                loadedView?.let { NativeAdRenderer.destroy(it) }
                native.destroyAd()
            }
            Unit
        }
    }

    private fun showSplash(activity: Activity, ad: ATSplashAd) {
        if (splashAd !== ad || splashShowing) return
        if (activity.isFinishing || activity.isDestroyed || !ad.isAdReady) {
            destroySplash()
            return
        }
        val container = activity.findViewById<ViewGroup>(android.R.id.content)
        if (container == null) {
            destroySplash()
            return
        }
        val overlay = FrameLayout(activity)
        splashContainer = overlay
        splashShowing = true
        container.addView(overlay, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        runCatching { ad.show(activity, overlay) }.onFailure { destroySplash() }
    }

    private fun destroySplash() {
        val ad = splashAd
        splashAd = null
        splashShowing = false
        splashTimeout?.let { mainHandler.removeCallbacks(it) }
        splashTimeout = null
        val overlay = splashContainer
        splashContainer = null
        (overlay?.parent as? ViewGroup)?.removeView(overlay)
        overlay?.removeAllViews()
        runCatching { ad?.onDestory() }
    }

    private fun AppBootstrap.isAdAvailable(): Boolean =
        gameStatus == 1 && adStatus == 1 && adsEnabled

    fun splashPlacement(bootstrap: AppBootstrap): AdPlacement? =
        bootstrap.placements.firstOrNull { it.matchesType(SPLASH_TYPES) }

    fun bannerPlacement(bootstrap: AppBootstrap): AdPlacement? =
        bootstrap.placements.firstOrNull { it.matchesType(BANNER_TYPES) }

    fun nativePlacement(bootstrap: AppBootstrap): AdPlacement? =
        bootstrap.placements.firstOrNull { it.matchesType(setOf("native")) }

    fun interstitialPlacement(bootstrap: AppBootstrap): AdPlacement? =
        bootstrap.placements.firstOrNull { it.matchesType(setOf("interstitial")) }

    fun rewardedPlacement(bootstrap: AppBootstrap): AdPlacement? =
        bootstrap.placements.firstOrNull { it.matchesType(setOf("rewarded", "reward_video", "video")) }

    private fun AdPlacement.matchesType(types: Set<String>): Boolean =
        placement.lowercase() in types || adType.lowercase() in types

    private fun contentFields(info: ATAdInfo): JSONObject {
        val direct = JSONObject().put("network_placement_id",
            AdContentFields.text(runCatching { info.networkPlacementId }.getOrNull()))
        val extension = AdContentFields.fromMap(runCatching { info.extInfoMap }.getOrNull().orEmpty())
        return AdContentFields.merge(direct, extension)
    }

    private fun reportSecondaryEvent(reporter: ((JSONObject) -> Unit)?, placement: AdPlacement,
                                     impressionId: String, event: String, info: ATAdInfo,
                                     materialContent: JSONObject? = null) {
        val type = when {
            placement.matchesType(SPLASH_TYPES) -> "splash"
            placement.matchesType(BANNER_TYPES) -> "banner"
            placement.matchesType(setOf("interstitial")) -> "interstitial"
            placement.matchesType(setOf("native")) -> "native"
            else -> return
        }
        val extra = info.extInfoMap.orEmpty()
        val payload = JSONObject()
            .put("impression_id", impressionId)
            .put("placement", type)
            .put("ad_type", type)
            .put("ad_unit_id", placement.adUnitId.take(255))
            .put("event", event)
            .put("occurred_at", Instant.now().toString())
            .put("network", info.networkName.orEmpty().take(128))
            .put("source_id", info.adsourceId.orEmpty().take(128))
            .put("format", info.format.orEmpty().take(64))
            .put("extension_keys", JSONArray(extra.keys.take(50).map { it.take(100) }))
            .put("e_c", info.encEcpmInfo.orEmpty().take(8192))
            .put("e_c_cny", info.rmbEncEcpmInfo.orEmpty().take(8192))
            .put("s_id", if (info.secretId > 0) info.secretId.toString() else "")
            .put("sdk_request_id", info.requestId.orEmpty().take(256))
            .put("sdk_show_id", info.showId.orEmpty().take(256))
        val content = AdContentFields.merge(contentFields(info), materialContent ?: JSONObject())
        content.keys().forEach { payload.put(it, content.get(it)) }
        runCatching { reporter?.invoke(payload) }
            .onFailure { Log.w(TAG, "Secondary ad event dispatch failed: type=$type, event=$event", it) }
    }

    private val SPLASH_TYPES = setOf("splash", "open", "open_screen", "app_open")
    private val BANNER_TYPES = setOf("banner", "home_banner", "bottom_banner")
}
