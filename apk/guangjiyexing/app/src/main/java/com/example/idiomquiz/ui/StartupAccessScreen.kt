package com.example.idiomquiz.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun StartupAccessScreen(onAuthorize: () -> Unit, onExit: () -> Unit) {
    androidx.activity.compose.BackHandler(onBack = onExit)
    Box(Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp), contentAlignment = Alignment.Center) {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Text("开启应用使用情况访问权限", style = MaterialTheme.typography.headlineSmall)
            Text("为提供应用使用统计及设备风控，禾合将在您同意并开启系统权限后，读取当前手机用户空间内可见的已安装应用名称、包名和版本，以及今天各应用的前台使用时长、估算打开次数，并在登录后上传至禾合后台，与您的账号关联。")
            Text("登录后进入应用或返回前台时同步，在前台期间约每分钟更新。打开次数根据系统前台切换记录估算，不等于点击图标次数。您可随时在系统设置的“使用情况访问权限”中关闭授权，关闭后停止采集。")
            Text("此权限为使用本应用的必要条件。拒绝授权或从设置返回时未开启，应用将退出。")
            Button(onClick = onAuthorize, modifier = Modifier.fillMaxWidth()) { Text("同意采集并前往授权") }
            OutlinedButton(onClick = onExit, modifier = Modifier.fillMaxWidth()) { Text("拒绝并退出") }
        }
    }
}
