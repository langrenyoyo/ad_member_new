package com.example.idiomquiz.ui

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
internal fun OnboardingScreen(state: UiState, model: QuizViewModel, invite: Boolean, usage: Boolean, alipay: Boolean) {
    val context = LocalContext.current
    var inviteCode by rememberSaveable(state.currentUser?.id) { mutableStateOf("") }
    var account by rememberSaveable(state.currentUser?.id) { mutableStateOf("") }
    var name by rememberSaveable(state.currentUser?.id) { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val withdrawing = state.screen == AppScreen.WALLET
    if (withdrawing) androidx.activity.compose.BackHandler(onBack = model::goHome)
    Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (withdrawing) TextButton(onClick = model::goHome) { Text("返回首页") }
        Text(if (withdrawing) "完善提现信息" else "完成账户设置", style = MaterialTheme.typography.headlineSmall)
        Text(if (withdrawing) "提现前请完成以下设置，保存后继续提现。" else "根据当前应用规则，完成以下步骤后继续使用。")
        state.onboardingError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.message?.let { Text(it) }
        state.authError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (state.onboardingBlockCode == "DEVICE_COOLDOWN") {
            Text("设备处于冷却期，恢复时间：${state.blockedUntil ?: "以服务端结果为准"}")
            Button(onClick = model::openWallet, enabled = !state.isBusy) { Text("查看提现记录 / 确认原申请") }
        }
        if (invite) {
            OutlinedTextField(inviteCode, { inviteCode = it }, label = { Text("邀请码") })
            Button(onClick = { model.bindInvite(inviteCode) }, enabled = !state.onboardingBusy) { Text("绑定邀请关系") }
        }
        if (usage) {
            Text("应用使用情况授权：用于向运营后台同步您手机上的应用包名、使用时长和估算打开次数。请在系统设置中自行开启；您可以随时撤销，撤销后当前应用将暂停开放相关功能。")
            Button(onClick = { context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) }) { Text("前往系统授权") }
            TextButton(onClick = model::refreshOnboarding, enabled = !state.onboardingBusy) { Text("已授权，检查并同步") }
        }
        if (alipay) {
            Text("绑定支付宝收款信息（不等于支付宝授权登录或实名认证）")
            Text("首次使用微信登录，请先填写密码和确认密码，再点击微信验证设置密码。提示设置成功后，再保存支付宝。这里填写的是本应用登录密码。")
            OutlinedTextField(account, { account = it }, label = { Text("支付宝账号") })
            OutlinedTextField(name, { name = it }, label = { Text("真实姓名") })
            OutlinedTextField(password, { password = it }, label = { Text("登录密码") }, visualTransformation = PasswordVisualTransformation())
            Button(onClick = { model.bindAlipay(account, name, password) }, enabled = !state.isBusy) { Text(if (state.isBusy) "处理中…" else "保存支付宝") }
        }
        TextButton(onClick = model::refreshOnboarding, enabled = !state.onboardingBusy) { Text("刷新设置状态") }
        TextButton(onClick = model::logout) { Text("退出登录") }
    }
}
