package com.example.idiomquiz.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import com.example.idiomquiz.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Release policy is fetched after consent. Mandatory prompts cannot be skipped. */
@Composable
fun StartupUpdatePrompt(): Boolean {
    val context = LocalContext.current
    var checked by rememberSaveable { mutableStateOf(false) }
    var pending by rememberSaveable { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        if (checked) return@LaunchedEffect
        pending = withContext(Dispatchers.IO) {
            runCatching {
                val origin = URL(BuildConfig.USER_API_BASE_URL)
                val connection = URL(origin.protocol, origin.host, origin.port,
                    origin.path.trimEnd('/') + "/app-update?game_id=${BuildConfig.REGISTRATION_GAME_ID}").openConnection() as HttpURLConnection
                connection.connectTimeout = 4000
                connection.readTimeout = 4000
                connection.useCaches = false
                try {
                    val body = connection.inputStream.bufferedReader().use { it.readText() }
                    val info = JSONObject(body)
                    val download = URL(info.getString("download_url"))
                    if (info.optBoolean("enabled") && info.getString("package_name") == BuildConfig.APPLICATION_ID &&
                        info.getInt("version_code") > BuildConfig.VERSION_CODE &&
                        download.protocol == "https" && download.host == origin.host &&
                        download.userInfo == null) body else null
                } finally { connection.disconnect() }
            }.getOrNull()
        }
        checked = true
    }
    pending?.let { raw ->
        val info = JSONObject(raw)
        val forced = info.optBoolean("force_update")
        AlertDialog(
            onDismissRequest = { if (!forced) pending = null },
            properties = androidx.compose.ui.window.DialogProperties(dismissOnBackPress = !forced, dismissOnClickOutside = !forced),
            title = { Text("发现新版本 ${info.optString("version_name")}") },
            text = { Text(info.optString("notes", "新版本已发布，请下载更新。")) },
            confirmButton = { TextButton(onClick = {
                runCatching {
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(info.getString("download_url"))))
                }.onSuccess { if (!forced) pending = null }.onFailure {
                    Toast.makeText(context, "无法打开下载链接，请稍后重试", Toast.LENGTH_SHORT).show()
                }
            }) { Text("立即更新") } },
            dismissButton = { if (!forced) TextButton(onClick = { pending = null }) { Text("稍后再说") } }
        )
    }
    return checked && pending == null
}
