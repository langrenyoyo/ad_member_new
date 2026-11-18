package com.example.idiomquiz.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
internal fun SystemPasswordScreen(state: UiState, model: QuizViewModel) {
    val context = LocalContext.current
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    androidx.activity.compose.BackHandler { }
    state.message?.let { message ->
        AlertDialog(onDismissRequest = model::clearMessage,
            title = { Text("设置提示") }, text = { Text(message) },
            confirmButton = { TextButton(onClick = model::clearMessage) { Text("知道了") } })
    }
    Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("设置系统密码", style = MaterialTheme.typography.headlineMedium)
        Text("微信登录成功，请先设置本应用的系统密码，完成后进入首页。已设置的账号以后无需重复设置。")
        Text("请设置6～128位密码，不限制字符组合。这不是微信密码或支付宝支付密码。")
        OutlinedTextField(password, { password = it }, modifier = Modifier.fillMaxWidth(),
            label = { Text("系统密码") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
        OutlinedTextField(confirmation, { confirmation = it }, modifier = Modifier.fillMaxWidth(),
            label = { Text("确认系统密码") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
        Button(onClick = { model.setPasswordWithWeChat(context, password, confirmation) },
            enabled = !state.isBusy, modifier = Modifier.fillMaxWidth()) {
            Text(if (state.isBusy) "正在验证并保存…" else "微信验证并完成设置")
        }
        TextButton(onClick = model::logout, enabled = !state.isBusy) { Text("退出登录") }
    }
}
