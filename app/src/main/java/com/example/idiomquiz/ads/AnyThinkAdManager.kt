package com.example.idiomquiz.ads

import android.app.Activity
import android.content.Context
import android.util.Log
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
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
import com.example.idiomquiz.BuildConfig
import com.example.idiomquiz.data.AdPlacement
import com.example.idiomquiz.data.AppBootstrap
import org.json.JSONObject

object AnyThinkAdManager {
    private const val TAG = "IdiomQuizAds"
    private var initialized = false
    private var splashRequested = false
    private var splashAd: ATSplashAd? = null
    private var interstitialAd: ATInterstitial? = null
    private var interstitialOnClosed: (() -> Unit)? = null
    private var rewardedAd: ATRewardVideoAd? = null
    private val mainHandler = Handler(Looper.getMainLooper())

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
        Log.i(TAG, "Splash request: initialized=$initialized, requested=$splashRequested, placement=${placement.adUnitId}")
        if (!initialized || splashRequested || placement.adUnitId.isBlank()) return
        splashRequested = true

        lateinit var ad: ATSplashAd
        ad = ATSplashAd(activity, placement.adUnitId, object : ATSplashAdListener {
            override fun onAdLoaded(isTimeout: Boolean) {
                if (isTimeout && !ad.isAdReady) {
                    Log.w(TAG, "Splash ad load timed out")
                    destroySplash()
                    return
                }
                showSplash(activity, ad)
            }

            override fun onAdLoadTimeout() {
                Log.w(TAG, "Splash ad load timeout callback")
                if (ad.isAdReady) showSplash(activity, ad) else destroySplash()
            }

            override fun onNoAdError(error: AdError) {
                Log.w(TAG, "Splash ad load failed: ${error.fullErrorInfo}")
                destroySplash()
            }

            override fun onAdShow(adInfo: ATAdInfo) {
                Log.d(TAG, "Splash ad shown")
            }

            override fun onAdClick(adInfo: ATAdInfo) {
                Log.d(TAG, "Splash ad clicked")
            }

            override fun onAdDismiss(adInfo: ATAdInfo, extraInfo: ATSplashAdExtraInfo) {
                Log.d(TAG, "Splash ad dismissed")
                destroySplash()
            }
        })
        splashAd = ad
        ad.loadAd()
    }

    fun createBannerView(
        context: Context,
        placement: AdPlacement,
        onStatus: (String) -> Unit = {}
    ): ATBannerView {
        onStatus("loading")
        return ATBannerView(context).apply {
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
                    Log.d(TAG, "Banner ad clicked")
                }

                override fun onBannerShow(adInfo: ATAdInfo) {
                    Log.d(TAG, "Banner ad shown")
                }

                override fun onBannerClose(adInfo: ATAdInfo) {
                    Log.d(TAG, "Banner ad closed")
                }

                override fun onBannerAutoRefreshed(adInfo: ATAdInfo) {
                    Log.d(TAG, "Banner ad auto-refreshed")
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

    fun loadInterstitial(context: Context, placement: AdPlacement) {
        if (!initialized || placement.adUnitId.isBlank()) return
        val ad = ATInterstitial(context, placement.adUnitId)
        ad.setAdListener(object : ATInterstitialListener {
            override fun onInterstitialAdLoaded() { Log.d(TAG, "Interstitial loaded") }
            override fun onInterstitialAdLoadFail(error: AdError) { Log.w(TAG, "Interstitial failed: ${error.fullErrorInfo}") }
            override fun onInterstitialAdClicked(adInfo: ATAdInfo) = Unit
            override fun onInterstitialAdShow(adInfo: ATAdInfo) = Unit
            override fun onInterstitialAdClose(adInfo: ATAdInfo) {
                interstitialAd = null
                interstitialOnClosed?.invoke()
                interstitialOnClosed = null
                loadInterstitial(context, placement)
            }
            override fun onInterstitialAdVideoStart(adInfo: ATAdInfo) = Unit
            override fun onInterstitialAdVideoEnd(adInfo: ATAdInfo) = Unit
            override fun onInterstitialAdVideoError(error: AdError) = Unit
        })
        interstitialAd = ad
        ad.load()
    }

    fun showInterstitial(activity: Activity, placement: AdPlacement) {
        showInterstitial(activity, placement, {})
    }

    fun showInterstitial(activity: Activity, placement: AdPlacement, onClosed: () -> Unit): Boolean {
        if (!initialized || placement.adUnitId.isBlank()) return false
        interstitialOnClosed = onClosed
        val ad = interstitialAd
        if (ad?.isAdReady == true) {
            ad.show(activity)
            return true
        }
        interstitialOnClosed = null
        loadInterstitial(activity, placement)
        return false
    }

    /** One request owns one SDK instance; never preload with a finished session. */
    fun showRewarded(
        activity: Activity,
        session: AdSession,
        onReward: (JSONObject) -> Unit,
        onClosed: () -> Unit,
        onShown: () -> Unit,
        onFailure: (String) -> Unit,
        onMetadata: (String, org.json.JSONObject) -> Unit = { _, _ -> }
    ) {
        if (!initialized || rewardedAd != null) {
            onFailure("广告尚未就绪或正在加载")
            return
        }
        val userId = session.takuUserId
        val extraData = session.takuExtraData
        if (userId.isNullOrBlank() || extraData.isNullOrBlank()) {
            onFailure("服务器未返回广告奖励验证参数")
            return
        }
        val ad = ATRewardVideoAd(activity, session.adUnitId)
        rewardedAd = ad
        val lifecycle = RewardedLifecycle()
        fun metadata(event: String, info: ATAdInfo): JSONObject? =
            runCatching {
                val extra = info.extInfoMap.orEmpty()
                fun field(vararg names: String): String = names.firstNotNullOfOrNull { key ->
                    (extra[key] as? String)?.takeIf { it.isNotBlank() }?.take(255)
                } ?: ""
                val payload = org.json.JSONObject().put("network", info.networkName.orEmpty().take(128))
                    .put("source_id", info.adsourceId.orEmpty().take(128)).put("format", info.format.orEmpty().take(64))
                    .put("title", field("title", "ad_title")).put("app_name", field("app_name", "appName"))
                    .put("creative_id", field("creative_id", "creativeId"))
                    .put("extension_keys", org.json.JSONArray(extra.keys.take(50).map { it.take(100) }))
                    .put("e_c", info.encEcpmInfo.orEmpty())
                    .put("e_c_cny", info.rmbEncEcpmInfo.orEmpty())
                    .put("s_id", if (info.secretId > 0) info.secretId.toString() else "")
                    .put("sdk_request_id", info.requestId.orEmpty().take(256))
                    .put("sdk_show_id", info.showId.orEmpty().take(256))
                runCatching { info.getPublisherRevenue(ATAdConst.CURRENCY.RMB) }.getOrNull()
                    ?.takeIf { it.isFinite() && it > 0.0 }
                    ?.let { payload.put("publisher_revenue_cny", it.toString()) }
                onMetadata(event, payload)
                payload
            }.getOrNull()
        lateinit var timeout: Runnable
        fun release() {
            lifecycle.end()
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
                    if (activity.isFinishing || activity.isDestroyed) {
                        fail("页面已关闭")
                        return@post
                    }
                    if (session.expiresAtEpochMillis?.let { it <= System.currentTimeMillis() } == true) {
                        fail("广告会话已过期，请重试")
                        return@post
                    }
                    mainHandler.removeCallbacks(timeout)
                    runCatching { ad.show(activity) }.onFailure { fail("广告展示失败") }
                }
            }
            override fun onRewardedVideoAdFailed(error: AdError) {
                mainHandler.post { fail("广告加载失败：${error.fullErrorInfo}") }
            }
            override fun onRewardedVideoAdPlayStart(adInfo: ATAdInfo) {
                mainHandler.post { if (lifecycle.impression()) { metadata("shown", adInfo); onShown() } }
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
    }

    fun loadNative(context: Context, placement: AdPlacement, onFailure: (String) -> Unit,
                   onReady: (ATNativeAdView) -> Unit) {
        if (!initialized || placement.adUnitId.isBlank()) {
            onFailure("原生广告服务暂不可用")
            return
        }
        lateinit var native: ATNative
        native = ATNative(context, placement.adUnitId, object : ATNativeNetworkListener {
            override fun onNativeAdLoaded() {
                mainHandler.post {
                runCatching {
                val ad = native.getNativeAd() ?: error("No native ad returned")
                val adView = ATNativeAdView(context)
                ad.setNativeEventListener(object : ATNativeEventListener {
                    override fun onAdImpressed(view: ATNativeAdView, info: ATAdInfo) = Unit
                    override fun onAdClicked(view: ATNativeAdView, info: ATAdInfo) = Unit
                    override fun onAdVideoStart(view: ATNativeAdView) = Unit
                    override fun onAdVideoEnd(view: ATNativeAdView) = Unit
                    override fun onAdVideoProgress(view: ATNativeAdView, progress: Int) = Unit
                })
                val container = FrameLayout(context)
                container.layoutParams = FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
                container.addView(TextView(context).apply {
                    text = "广告"
                    layoutParams = FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT
                    )
                })
                adView.layoutParams = FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
                ad.renderAdContainer(adView, container)
                onReady(adView)
                }.onFailure { onFailure("原生广告展示失败，请稍后重试") }
                }
            }
            override fun onNativeAdLoadFail(error: AdError) {
                mainHandler.post { onFailure("原生广告加载失败，请稍后重试") }
            }
        })
        runCatching { native.makeAdRequest() }.onFailure { onFailure("原生广告请求失败，请稍后重试") }
    }

    private fun showSplash(activity: Activity, ad: ATSplashAd) {
        if (activity.isFinishing || activity.isDestroyed || !ad.isAdReady) {
            destroySplash()
            return
        }
        val container = activity.findViewById<ViewGroup>(android.R.id.content)
        if (container == null) {
            destroySplash()
            return
        }
        ad.show(activity, container)
    }

    private fun destroySplash() {
        splashAd?.onDestory()
        splashAd = null
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

    private val SPLASH_TYPES = setOf("splash", "open", "open_screen", "app_open")
    private val BANNER_TYPES = setOf("banner", "home_banner", "bottom_banner")
}
