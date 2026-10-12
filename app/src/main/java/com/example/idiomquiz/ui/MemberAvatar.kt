package com.example.idiomquiz.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import com.example.idiomquiz.BuildConfig
import com.example.idiomquiz.R
import com.example.idiomquiz.data.AuthRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

@Composable
internal fun MemberAvatar(memberId: String?, modifier: Modifier, imagePath: String? = null) {
    val context = LocalContext.current
    val bitmap by produceState<android.graphics.Bitmap?>(null, memberId, imagePath) {
        value = null
        if (memberId == null) return@produceState
        try {
            val path = imagePath ?: AuthRepository(context).memberRequest("GET", "me")
                .getJSONObject("data").optString("image_url")
            if (path.isBlank()) return@produceState
            value = withContext(Dispatchers.IO) {
                val base = URL(BuildConfig.USER_API_BASE_URL)
                val url = URL(base, path)
                require(url.protocol == "https" ||
                    (url.protocol == base.protocol && url.host == base.host && url.port == base.port))
                val connection = url.openConnection() as HttpURLConnection
                connection.connectTimeout = 10000
                connection.readTimeout = 10000
                connection.instanceFollowRedirects = false
                try {
                    check(connection.responseCode == 200) { "Avatar HTTP ${connection.responseCode}" }
                    val bytes = connection.inputStream.use { stream ->
                        val output = java.io.ByteArrayOutputStream()
                        val buffer = ByteArray(8192)
                        while (true) {
                            val count = stream.read(buffer)
                            if (count < 0) break
                            require(output.size() + count <= 8 * 1024 * 1024)
                            output.write(buffer, 0, count)
                        }
                        output.toByteArray()
                    }
                    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                    val options = BitmapFactory.Options().apply { inSampleSize = 1 }
                    while (maxOf(bounds.outWidth, bounds.outHeight) / options.inSampleSize > 512) {
                        options.inSampleSize *= 2
                    }
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
                } finally { connection.disconnect() }
            }
        } catch (error: CancellationException) { throw error }
        catch (error: Exception) {
            if (BuildConfig.DEBUG) android.util.Log.d("MemberAvatar", "Avatar load failed: ${error.javaClass.simpleName}")
            value = null
        }
    }
    val loaded = bitmap
    if (loaded != null) Image(loaded.asImageBitmap(), "头像", modifier, contentScale = ContentScale.Crop)
    else Image(painterResource(R.drawable.icon_avatar), "默认头像", modifier)
}
