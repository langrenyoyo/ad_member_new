package com.example.idiomquiz.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.example.idiomquiz.data.*
import org.json.JSONObject

@Composable
internal fun MemberCenterScreen(model: MemberCenterViewModel, onBack: () -> Unit) {
    val state by model.state.collectAsState()
    BackHandler { if (state.detail != null) model.closeDetail() else onBack() }
    Column(Modifier.fillMaxSize().statusBarsPadding().padding(16.dp)) {
        state.recoveryMessage?.let { message ->
            Text(message)
            if (state.recoveryPending) {
                TextButton(enabled = !state.recovering && !state.busy, onClick = { model.retryCampaignRecovery() }) { Text("重试补贴确认") }
            }
        }
        TextButton(onClick = { if (state.detail != null) model.closeDetail() else onBack() }) { Text("返回") }
        Text("会员服务", style = MaterialTheme.typography.headlineSmall)
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
            MemberSection.entries.forEach { section ->
                FilterChip(selected = state.section == section, enabled = !state.busy,
                    onClick = { model.load(section) }, label = { Text(section.title) })
                Spacer(Modifier.width(6.dp))
            }
        }
        if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.notice?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val detail = state.detail
            if (detail != null) {
                DetailContent(state, model, detail)
            } else when (state.section) {
                MemberSection.PROFILE -> state.profile?.let { ProfileForm(it, state.busy, model) }
                MemberSection.PASSWORD -> key(state.formRevision) { PasswordForm(state.busy, model) }
                MemberSection.OBSERVATIONS -> DeviceObservationScreen()
                else -> {
                    OutlinedButton(enabled = !state.busy, onClick = { model.load() }) { Text("刷新") }
                    Text("共 ${state.total} 条")
                    if (state.section == MemberSection.COMMISSIONS) state.commissionSummary?.let { summary ->
                        Text("等级：${listOf("用户", "团长", "历史 V2", "代理").getOrElse(summary.optInt("level")) { "用户" }} · 直属邀请 ${summary.optInt("direct_members")} 人")
                        Text("今日佣金：${summary.optString("today_earned")} 金币（北京时间）")
                        Text("累计佣金：${summary.optString("total_earned")} 金币，已计入钱包余额")
                    }
                    state.items.forEach { item ->
                        OutlinedCard(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                RecordContent(state.section, item)
                                if (state.section in listOf(MemberSection.WITHDRAWALS, MemberSection.CAMPAIGNS, MemberSection.SUBSIDIES)) {
                                    TextButton(enabled = !state.busy, onClick = { model.detail(item.get("id").toString()) }) { Text("查看详情") }
                                }
                            }
                        }
                    }
                    if (state.hasMore) OutlinedButton(enabled = !state.busy, onClick = { model.load(append = true) }) { Text("加载更多") }
                    if (state.section == MemberSection.SUBSIDIES) {
                        Text("普通补贴申请", style = MaterialTheme.typography.titleMedium)
                        Text("已配置补贴活动的游戏，请到补贴活动中申请。")
                        key(state.formRevision) { SubsidyForm(state, model, false) }
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun ProfileForm(profile: JSONObject, busy: Boolean, model: MemberCenterViewModel) {
    val avatarPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { model.upload("avatar", it) }
    }
    var name by remember(profile) { mutableStateOf(profile.optString("name")) }
    var realName by remember(profile) { mutableStateOf(profile.optString("real_name")) }
    var receiveName by remember(profile) { mutableStateOf(profile.optString("receive_name")) }
    var address by remember(profile) { mutableStateOf(profile.optString("address")) }
    var sex by remember(profile) { mutableStateOf(profile.optInt("sex")) }
    Text("会员编号：${profile.opt("id")} · VIP：${profile.opt("vip")}")
    Text("账号：${profile.optString("username")}")
    Text("所属游戏：${profile.opt("game_id")}")
    MemberAvatar(profile.opt("id")?.toString(), Modifier.size(68.dp), profile.optString("image_url"))
    OutlinedButton(enabled = !busy, onClick = { avatarPicker.launch("image/*") }) { Text("更换头像（最多 2MB）") }
    Field("昵称", name, busy) { name = it }
    Field("姓名", realName, busy) { realName = it }
    Field("收款姓名", receiveName, busy) { receiveName = it }
    Field("地址", address, busy) { address = it }
    Row { listOf("未设置", "男", "女").forEachIndexed { index, label ->
        FilterChip(selected = sex == index, enabled = !busy, onClick = { sex = index }, label = { Text(label) })
    } }
    Text("资料中的姓名不代表已完成实名认证，支付宝收款账号请在钱包中绑定。")
    Button(enabled = !busy, onClick = { model.saveProfile(name, realName, receiveName, address, sex) }) { Text("保存资料") }
}

@Composable
private fun PasswordForm(busy: Boolean, model: MemberCenterViewModel) {
    var current by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    Text("修改密码需要当前密码。首次绑定支付宝时，可在账户设置页通过微信或短信验证设置密码；微信用户也可从钱包进入微信验证设密。")
    OutlinedTextField(current, { current = it }, enabled = !busy, label = { Text("当前密码") }, visualTransformation = PasswordVisualTransformation())
    OutlinedTextField(password, { password = it }, enabled = !busy, label = { Text("新密码") }, visualTransformation = PasswordVisualTransformation())
    OutlinedTextField(confirmation, { confirmation = it }, enabled = !busy, label = { Text("确认新密码") }, visualTransformation = PasswordVisualTransformation())
    Button(enabled = !busy, onClick = { model.changePassword(current, password, confirmation) }) { Text("修改密码") }
}

@Composable
private fun Field(label: String, value: String, busy: Boolean, onChange: (String) -> Unit) {
    OutlinedTextField(value, onChange, modifier = Modifier.fillMaxWidth(), enabled = !busy, label = { Text(label) })
}

@Composable
private fun RecordContent(section: MemberSection, item: JSONObject) {
    when (section) {
        MemberSection.GAMES -> Text("${item.optString("name")} · 游戏 ${item.opt("id")}")
        MemberSection.COMMISSIONS -> {
            Text("分佣 ${item.optString("amount")} 金币")
            val commissionName = when (item.optString("kind")) {
                "commission_0" -> "用户分佣"
                "commission_1" -> "团长分佣"
                "commission_2" -> "V2 分佣"
                "commission_3" -> "代理分佣"
                else -> "分佣收益"
            }
            Text("来源会员 ${item.optInt("source_member_id")} · $commissionName")
        }
        MemberSection.TEAM -> {
            Text("会员 ${item.optInt("id")} · ${listOf("用户", "团长", "历史 V2", "代理").getOrElse(item.optInt("level")) { "用户" }}")
        }
        MemberSection.COINS -> {
            Text("变动 ${item.decimal("coin").toPlainString()} 金币")
            Text("${item.decimal("coin_before")} → ${item.decimal("coin_after")}")
            Text(item.optString("remark"))
        }
        MemberSection.WITHDRAWALS -> {
            val record = parseWithdrawal(item)
            Text("¥${centsText(record.amountCents)} · ${withdrawalStatus(item)}")
            Text("消耗金币：${record.coin}")
        }
        MemberSection.ADS -> {
            val placement = when (val value = item.optString("placement")) {
                "rewarded" -> "激励视频"
                "interstitial" -> "插屏广告"
                "banner" -> "横幅广告"
                "splash" -> "开屏广告"
                "native" -> "原生广告"
                else -> value.ifBlank { "广告" }
            }
            val status = when (val value = item.optString("status")) {
                "requested", "issued" -> "已申请"
                "impressed" -> "已展示"
                "completed" -> "已观看完成"
                "rewarded" -> "奖励已到账"
                "pending_verification" -> "等待奖励核验"
                "failed" -> "未完成"
                "expired" -> "已过期"
                else -> value.ifBlank { "状态待确认" }
            }
            Text("$placement · $status")
            Text("实际奖励：${item.decimal("coin_added")} 金币")
        }
        MemberSection.CAMPAIGNS -> {
            Text(item.optString("title"), style = MaterialTheme.typography.titleMedium)
            Text("奖励 ¥${centsText(item.optLong("reward_cents"))} · 剩余名额 ${item.optInt("remaining")}")
        }
        MemberSection.SUBSIDIES -> {
            Text("申请 #${item.opt("id")} · ${when (item.optInt("status")) { 0 -> "待审核"; 1 -> "已通过"; else -> "已驳回" }}")
            Text("补贴金额 ¥${item.decimal("price")}")
            if (item.optString("sub_msg").isNotBlank()) Text(item.optString("sub_msg"))
        }
        else -> Unit
    }
    if (item.has("created_at")) Text(item.optString("created_at"), style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun DetailContent(state: MemberCenterState, model: MemberCenterViewModel, detail: JSONObject) {
    RecordContent(state.section, detail)
    when (state.section) {
        MemberSection.CAMPAIGNS -> {
            Text(detail.optString("instructions"))
            Text("需今日已确认提现 ¥${centsText(detail.optLong("withdrawal_cents"))}，充值 ¥${centsText(detail.optLong("recharge_cents"))}")
            Text("预计审核 ${detail.optInt("review_hours")} 小时")
            val reasons = detail.optJSONArray("reasons")
            if (reasons != null) for (i in 0 until reasons.length()) Text(reasons.getString(i))
            OutlinedButton(enabled = !state.busy, onClick = { model.detail(detail.get("id").toString()) }) { Text("刷新资格") }
            if (detail.optBoolean("eligible")) key(detail.get("id")) { SubsidyForm(state, model, true) }
        }
        MemberSection.WITHDRAWALS -> {
            val payout = detail.optJSONObject("payout")
            Text("收款账号：${payout?.optString("account_masked").orEmpty()}")
            Text("订单号：${payout?.optString("out_biz_no").orEmpty()}")
            payout?.optString("error")?.takeIf { it.isNotBlank() }?.let { Text(it) }
            OutlinedButton(enabled = !state.busy, onClick = { model.detail(detail.get("id").toString()) }) { Text("刷新状态") }
        }
        MemberSection.SUBSIDIES -> {
            Text("收款姓名：${detail.optString("receive_name")}")
            Text("收款账号：${detail.optString("receive_tel")}")
            detail.optJSONObject("campaign")?.let {
                Text("活动：${it.optString("title")}\n审核截止：${it.optString("review_due_at")}")
            }
        }
        else -> Unit
    }
}

@Composable
private fun SubsidyForm(state: MemberCenterState, model: MemberCenterViewModel, campaign: Boolean) {
    var name by remember { mutableStateOf("") }
    var account by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    var slot by remember { mutableStateOf("proof") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { model.upload(slot, it) }
    }
    Field("收款姓名", name, state.busy) { name = it }
    Field("收款账号", account, state.busy) { account = it }
    if (!campaign) Field("提现条件金额（元）", amount, state.busy) { amount = it }
    val slots = if (campaign) listOf("download_image" to "下载截图", "install_image" to "安装来源截图", "recharge_image" to "充值截图")
        else listOf("proof" to "申请凭证")
    slots.forEach { (id, label) ->
        OutlinedButton(enabled = !state.busy, onClick = { slot = id; picker.launch("image/*") }) {
            Text("$label：${if (state.images.containsKey(id)) "已上传，点击更换" else "选择图片（最多 2MB）"}")
        }
    }
    Button(enabled = !state.busy, onClick = { model.applySubsidy(name, account, amount, campaign) }) { Text("提交申请") }
}
