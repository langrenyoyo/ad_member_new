package com.example.idiomquiz.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun StartupAccessScreen(onAuthorize: () -> Unit, onExit: () -> Unit) {
    androidx.activity.compose.BackHandler(onBack = onExit)
    Box(Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp), contentAlignment = Alignment.Center) {
        Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Text("开启应用使用情况访问权限", style = MaterialTheme.typography.headlineSmall)
            Text("鸭只易记需要查看手机应用的使用情况，用于使用统计及设备风控。授权后可能读取应用包名、使用时长与打开次数，并在登录后按应用策略上报。请在系统设置中允许鸭只易记访问使用情况。")
            Text("此权限为使用本应用的必要条件。拒绝授权或从设置返回时未开启，应用将退出。")
            Button(onClick = onAuthorize, modifier = Modifier.fillMaxWidth()) { Text("前往授权") }
            OutlinedButton(onClick = onExit, modifier = Modifier.fillMaxWidth()) { Text("拒绝并退出") }
        }
    }
}
