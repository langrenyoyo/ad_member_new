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
import com.anythink.core.api.ATShowConfig
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
    private var rewardedAdExtraKey: String? = null
    private var rewardedOnReward: ((Map<String, Any?>) -> Unit)? = null
    private var rewardedOnClosed: (() -> Unit)? = null
    private var rewardedOnShown: (() -> Unit)? = null

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

    fun loadRewarded(
        context: Context,
        placement: AdPlacement,
        takuUserId: String? = null,
        takuExtraData: Any? = null
    ) {
        if (!initialized || placement.adUnitId.isBlank()) return
        val ad = ATRewardVideoAd(context, placement.adUnitId)
        val takuExtra = buildTakuExtra(takuUserId, takuExtraData)
        val extraKey = JSONObject(takuExtra).toString()
        Log.d(TAG, "Rewarded load requested: placement=${placement.adUnitId}, hasLocalExtra=${takuExtra.isNotEmpty()}")
        if (takuExtra.isNotEmpty()) {
            ad.setLocalExtra(takuExtra)
            Log.d(TAG, "Rewarded local extra set: keys=${takuExtra.keys.joinToString()}")
        }
        ad.setAdListener(object : ATRewardVideoListener {
            override fun onRewardedVideoAdLoaded() { Log.d(TAG, "Rewarded loaded") }
            override fun onRewardedVideoAdFailed(error: AdError) { Log.w(TAG, "Rewarded load failed: ${error.fullErrorInfo}") }
            override fun onRewardedVideoAdPlayStart(adInfo: ATAdInfo) {
                if (rewardedAd !== ad) return
                Log.d(TAG, "Rewarded play started")
                rewardedOnShown?.invoke()
                rewardedOnShown = null
            }
            override fun onRewardedVideoAdPlayEnd(adInfo: ATAdInfo) = Unit
            override fun onRewardedVideoAdPlayFailed(error: AdError, adInfo: ATAdInfo) {
                Log.w(TAG, "Rewarded play failed: ${error.fullErrorInfo}")
            }
            override fun onRewardedVideoAdClosed(adInfo: ATAdInfo) {
                if (rewardedAd !== ad) return
                Log.d(TAG, "Rewarded closed")
                rewardedAd = null
                rewardedAdExtraKey = null
                rewardedOnClosed?.invoke()
                rewardedOnClosed = null
                rewardedOnShown = null
                loadRewarded(context, placement, takuUserId, takuExtraData)
            }
            override fun onRewardedVideoAdPlayClicked(adInfo: ATAdInfo) = Unit
            override fun onReward(adInfo: ATAdInfo) {
                if (rewardedAd !== ad) return
                Log.d(TAG, "Reward granted")
                rewardedOnReward?.invoke(adInfo.toRewardExtra())
                rewardedOnReward = null
            }
        })
        rewardedAd = ad
        rewardedAdExtraKey = extraKey
        ad.load()
    }

    fun showRewarded(activity: Activity, placement: AdPlacement) {
        showRewarded(activity, placement, {}, {})
    }

    fun showRewarded(activity: Activity, placement: AdPlacement, onReward: () -> Unit, onClosed: () -> Unit) {
        showRewarded(activity, placement, { onReward() }, onClosed, {})
    }

    fun showRewarded(
        activity: Activity,
        placement: AdPlacement,
        onReward: (Map<String, Any?>) -> Unit,
        onClosed: () -> Unit,
        onShown: () -> Unit
    ) {
        showRewarded(activity, placement, onReward, onClosed, onShown, null, null)
    }

    fun showRewarded(
        activity: Activity,
        placement: AdPlacement,
        onReward: (Map<String, Any?>) -> Unit,
        onClosed: () -> Unit,
        onShown: () -> Unit,
        takuUserId: String?,
        takuExtraData: Any?
    ) {
        if (!initialized || placement.adUnitId.isBlank()) return
        rewardedOnReward = onReward
        rewardedOnClosed = onClosed
        rewardedOnShown = onShown
        val requestedExtraKey = JSONObject(buildTakuExtra(takuUserId, takuExtraData)).toString()
        val ad = rewardedAd
        if (ad != null && rewardedAdExtraKey != requestedExtraKey) {
            Log.d(TAG, "Discarding rewarded cache because session extra changed")
            ad.destroyAd()
            rewardedAd = null
            rewardedAdExtraKey = null
        }
        val currentAd = rewardedAd
        if (currentAd?.isAdReady == true) {
            Log.d(TAG, "Showing cached rewarded ad")
            val ext = buildTakuShowExt(takuUserId, takuExtraData)
            val config = ATShowConfig.Builder().showCustomExt(ext).build()
            currentAd.show(activity, config)
        } else {
            Log.d(TAG, "No matching rewarded cache; loading with session extra")
            loadRewarded(activity, placement, takuUserId, takuExtraData)
        }
    }

    private fun buildTakuExtra(userId: String?, extraData: Any?): Map<String, Any?> = buildMap {
        userId?.takeIf { it.isNotBlank() }?.let {
            put("userID", it)
            put("user_id", it)
        }
        extraData?.let { put("md5", it.toString()) }
    }

    private fun buildTakuShowExt(userId: String?, extraData: Any?): String =
        JSONObject(buildTakuExtra(userId, extraData)).toString()

    private fun ATAdInfo.toRewardExtra(): Map<String, Any?> = buildMap {
        put("id", getShowId())
        put("request_id", getRequestId())
        put("placement_id", getPlacementId())
        put("network_placement_id", getNetworkPlacementId())
        put("adsource_id", getAdsourceId())
        put("network_name", getNetworkName())
        put("ad_network_type", getAdNetworkType())
        put("ecpm", getEcpm())
        put("currency", getCurrency())
        put("reward_user_custom_data", getRewardUserCustomData())
        put("ext_info_map", getExtInfoMap())
    }

    fun loadNative(context: Context, placement: AdPlacement, onReady: (ATNativeAdView) -> Unit) {
        if (!initialized || placement.adUnitId.isBlank()) return
        lateinit var native: ATNative
        native = ATNative(context, placement.adUnitId, object : ATNativeNetworkListener {
            override fun onNativeAdLoaded() {
                val ad = native.getNativeAd() ?: return
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
            }
            override fun onNativeAdLoadFail(error: AdError) { Log.w(TAG, "Native failed: ${error.fullErrorInfo}") }
        })
        native.makeAdRequest()
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
