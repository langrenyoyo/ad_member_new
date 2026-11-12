package com.example.idiomquiz.ads

import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import com.anythink.nativead.api.ATNativeAdView
import com.anythink.nativead.api.ATNativePrepareInfo
import com.anythink.nativead.api.NativeAd
import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.WeakHashMap

/** Bind SDK-owned interaction views; never synthesize an impression or a click. */
internal object NativeAdRenderer {
    private data class Resources(val ad: NativeAd, val job: Job, val release: () -> Unit)
    private val resources = WeakHashMap<ATNativeAdView, Resources>()

    fun content(ad: NativeAd): JSONObject {
        val material = runCatching { ad.adMaterial }.getOrNull()
        val app = runCatching { material?.adAppInfo }.getOrNull()
        val common = JSONObject()
            .put("title", runCatching { material?.title }.getOrNull())
            .put("app_name", runCatching { app?.appName }.getOrNull())
            .put("app_package", runCatching { app?.appPackageName }.getOrNull())
            .put("advertiser", runCatching { material?.advertiserName }.getOrNull())
        val network = AdContentFields.fromMap(runCatching { material?.networkInfoMap }.getOrNull().orEmpty())
        // The existing Kuaishou adapter exposes KsNativeAd through NativeAd.getObject().
        // Feed templates can expose a different object; use only the public typed native API.
        val ks = runCatching { ad.`object` as? com.kwad.sdk.api.KsNativeAd }.getOrNull()
        val native = JSONObject()
            .put("title", runCatching { ks?.productName }.getOrNull())
            .put("app_name", runCatching { ks?.appName }.getOrNull())
            .put("app_package", runCatching { ks?.appPackageName }.getOrNull())
        return AdContentFields.merge(common, native, network)
    }

    fun destroy(view: ATNativeAdView) {
        resources.remove(view)?.let { item ->
            item.job.cancel()
            runCatching { item.ad.clear(view) }
            runCatching { item.ad.destory() }
            item.release()
        }
    }

    fun render(context: Context, ad: NativeAd, view: ATNativeAdView, release: () -> Unit) {
        val job = SupervisorJob()
        resources[view] = Resources(ad, job, release)
        val scope = CoroutineScope(job + Dispatchers.Main.immediate)
        fun dp(value: Int) = (value * context.resources.displayMetrics.density).toInt()
        if (ad.isNativeExpress) {
            ad.renderAdContainer(view, null)
            ad.prepare(view, ATNativePrepareInfo())
            return
        }
        val material = requireNotNull(ad.adMaterial) { "Native material unavailable" }
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(12), dp(12), dp(12))
            layoutParams = FrameLayout.LayoutParams(-1, -2)
        }
        fun label(value: String, size: Float = 14f) = TextView(context).apply {
            text = value
            textSize = size
            setTextColor(0xff48352a.toInt())
            layoutParams = LinearLayout.LayoutParams(-1, -2)
            container.addView(this)
        }
        fun addSdkView(child: View) {
            (child.parent as? ViewGroup)?.removeView(child)
            container.addView(child, LinearLayout.LayoutParams(-1, dp(180)))
        }
        val title = label(material.title.orEmpty(), 18f)
        val description = label(material.descriptionText.orEmpty())
        val image = ImageView(context).apply { scaleType = ImageView.ScaleType.CENTER_CROP }
        val media = runCatching { material.getAdMediaView() }.getOrNull()
        if (media != null) addSdkView(media) else {
            val imageUrl = material.mainImageUrl.orEmpty().ifBlank { material.imageUrlList?.firstOrNull().orEmpty() }
            require(imageUrl.isNotBlank()) { "Native media unavailable" }
            addSdkView(image)
            scope.launch {
                val bitmap = withContext(Dispatchers.IO) { loadImage(imageUrl) }
                ensureActive()
                if (bitmap != null) image.setImageBitmap(bitmap)
            }
        }
        val cta = material.callToActionButton ?: label(material.callToActionText.orEmpty().ifBlank { "查看详情" })
            .apply { gravity = Gravity.CENTER; setPadding(0, dp(10), 0, dp(10)) }
        if (cta.parent !== container) {
            (cta.parent as? ViewGroup)?.removeView(cta)
            container.addView(cta, LinearLayout.LayoutParams(-1, -2))
        }
        val adFrom = label("广告 · ${material.adFrom.orEmpty()}", 11f)
        val logo = material.adLogoView
        if (logo != null) {
            (logo.parent as? ViewGroup)?.removeView(logo)
            container.addView(logo, LinearLayout.LayoutParams(dp(40), dp(20)))
        }
        material.adAppInfo?.let { app ->
            label("${app.appName.orEmpty()} · ${app.publisher.orEmpty()} · ${app.appVersion.orEmpty()}", 11f)
            fun link(title: String, target: String?) {
                val uri = target?.let(Uri::parse) ?: return
                if (uri.scheme !in listOf("http", "https")) return
                label(title, 11f).setOnClickListener {
                    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
                }
            }
            link("隐私政策", app.appPrivacyUrl)
            link("应用权限", app.appPermissonUrl)
            link("功能介绍", app.functionUrl)
        }
        ad.renderAdContainer(view, container)
        ad.prepare(view, ATNativePrepareInfo().apply {
            parentView = container
            titleView = title
            descView = description
            mainImageView = media ?: image
            ctaView = cta
            adFromView = adFrom
            if (logo != null) adLogoView = logo
            clickViewList = listOf(title, description, media ?: image, cta)
        })
    }

    private fun loadImage(value: String): android.graphics.Bitmap? = runCatching {
        val url = URL(value)
        require(url.protocol in listOf("https", "http"))
        val connection = url.openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 8_000
            connection.readTimeout = 8_000
            val bytes = connection.inputStream.use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= 4 * 1024 * 1024)
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            val options = BitmapFactory.Options().apply { inSampleSize = 1 }
            while (bounds.outWidth / options.inSampleSize > 1600 || bounds.outHeight / options.inSampleSize > 1600) {
                options.inSampleSize *= 2
            }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        } finally { connection.disconnect() }
    }.getOrNull()
}
