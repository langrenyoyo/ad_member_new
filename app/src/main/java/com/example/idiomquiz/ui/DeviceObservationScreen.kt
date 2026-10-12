package com.example.idiomquiz.ui

import android.Manifest
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.BatteryManager
import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.example.idiomquiz.data.AuthRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
internal fun DeviceObservationScreen() {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val auth = remember { AuthRepository(context) }
    var enabled by remember { mutableStateOf(false) }
    var locationEnabled by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("未开启") }
    var deleting by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        locationEnabled = result[Manifest.permission.ACCESS_FINE_LOCATION] == true || result[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (!locationEnabled) message = "定位未授权，仍可仅上传电量和充电状态"
    }
    Text("设备观测（自愿开启）", style = MaterialTheme.typography.titleMedium)
    Text("开启后，仅在本页前台约每分钟上传电量和充电状态，服务器记录连接 IP；可另行授权上传近期定位，用于设备聚集分析。后台仅观察、不自动封禁。报告保留窗口为 24 小时，离开本页即停止采样。")
    Switch(checked = enabled, onCheckedChange = { enabled = it }, enabled = !deleting)
    Text(if (enabled) "采样已开启" else "采样已关闭")
    TextButton(onClick = {
        if (locationEnabled) locationEnabled = false
        else permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
    }, enabled = !deleting) { Text(if (locationEnabled) "停止上传定位" else "允许上传近期定位") }
    TextButton(onClick = {
        enabled = false; deleting = true
        scope.launch {
            try { auth.memberRequest("DELETE", "device-observations"); message = "已删除观测记录" }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { message = e.message ?: "删除失败，请重试" }
            finally { deleting = false }
        }
    }, enabled = !deleting) { Text("停止并删除观测记录") }
    Text(message)
    LaunchedEffect(enabled, locationEnabled, owner) {
        if (!enabled) return@LaunchedEffect
        owner.lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            while (true) {
                try {
                    val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                    val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
                    val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
                    if (level >= 0 && scale > 0) {
                        val body = JSONObject().put("battery", (level * 100 / scale).coerceIn(0, 100))
                            .put("charging", (battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0)
                        if (locationEnabled && (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                                    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED)) {
                            val manager = context.getSystemService(android.content.Context.LOCATION_SERVICE) as LocationManager
                            val locations = manager.getProviders(true).mapNotNull { provider ->
                                try { manager.getLastKnownLocation(provider) } catch (_: SecurityException) { null }
                            }
                            val location = locations.filter { !it.isFromMockProvider && it.hasAccuracy() && it.accuracy > 0 &&
                                SystemClock.elapsedRealtimeNanos() - it.elapsedRealtimeNanos in 0..120_000_000_000L }.maxByOrNull { it.elapsedRealtimeNanos }
                            location?.let {
                                body.put("latitude", it.latitude).put("longitude", it.longitude).put("accuracy", it.accuracy.toDouble())
                                    .put("location_age_seconds", (SystemClock.elapsedRealtimeNanos()-it.elapsedRealtimeNanos)/1_000_000_000)
                            }
                        }
                        auth.memberRequest("POST", "device-observations", body)
                        message = if (body.has("latitude")) "已上传电量、充电及近期定位" else "已上传电量和充电状态；无有效近期定位"
                    } else message = "无法获取电量，未上传"
                } catch (e: CancellationException) { throw e }
                catch (e: Exception) { message = e.message ?: "上传失败，稍后重试" }
                delay(60_000)
            }
        }
    }
}
