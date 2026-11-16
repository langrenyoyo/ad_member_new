package com.example.idiomquiz.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Person
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.example.idiomquiz.BuildConfig
import com.example.idiomquiz.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

private val memberRecordDateFormatter = DateTimeFormatter.ofPattern("MM.dd HH:mm", Locale.CHINA)
    .withZone(ZoneId.of("Asia/Shanghai"))

private fun formatMemberRecordTime(value: String): String {
    val raw = value.trim()
    if (raw.isEmpty()) return "时间未知"
    val epochMillis = raw.toLongOrNull()?.let { if (kotlin.math.abs(it) < 100_000_000_000L) it * 1000L else it }
    if (epochMillis != null) return runCatching { memberRecordDateFormatter.format(Instant.ofEpochMilli(epochMillis)) }.getOrDefault(raw)
    return runCatching { memberRecordDateFormatter.format(Instant.parse(raw)) }
        .recoverCatching { java.time.OffsetDateTime.parse(raw).toInstant().let(memberRecordDateFormatter::format) }
        .recoverCatching { LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC).let(memberRecordDateFormatter::format) }
        .getOrDefault(raw)
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
internal fun MemberCenterScreen(model: MemberCenterViewModel, entryModel: QuizViewModel, appState: UiState, onBack: () -> Unit) {
    val state by model.state.collectAsState()
    val activity = LocalContext.current.findActivity()
    DisposableEffect(entryModel) { onDispose { entryModel.cancelEntryAd() } }
    val goBack = {
        entryModel.cancelEntryAd()
        if (state.detail != null) model.closeDetail() else onBack()
    }
    BackHandler(onBack = goBack)
    val recordFilter = state.subsidyStatus ?: -1
    val contentScrollState = key(state.section, state.detail?.optString("id")) { rememberScrollState() }
    var coinFilter by remember(state.section) { mutableIntStateOf(0) }
    val campaignId = state.detail?.optString("id")
    var campaignReceiveName by remember(campaignId) { mutableStateOf("") }
    var campaignReceiveAccount by remember(campaignId) { mutableStateOf("") }
    val showCampaignSubmit = state.section == MemberSection.CAMPAIGNS &&
        state.detail != null
    val showApprovedSubsidyCheck = state.section == MemberSection.SUBSIDIES &&
        state.detail?.optInt("status") == 1
    val pageTitle = when {
        state.detail != null && state.section == MemberSection.CAMPAIGNS -> "提交资料"
        state.detail != null && state.section == MemberSection.SUBSIDIES -> "申请详情"
        state.section == MemberSection.SUBSIDIES -> "补贴申请"
        state.section == MemberSection.CAMPAIGNS -> "补贴活动"
        else -> state.section.title
    }
    Column(Modifier.fillMaxSize().background(if (showCampaignSubmit) MobanGoldPage else androidx.compose.ui.graphics.Brush.verticalGradient(listOf(MaterialTheme.colorScheme.background, MaterialTheme.colorScheme.background))).statusBarsPadding()) {
        ReferenceToolbar(title = pageTitle, onBack = goBack,
            actions = {
                if (state.section == MemberSection.CAMPAIGNS && state.detail != null) {
                    TextButton(enabled = !state.busy, onClick = { model.load(MemberSection.SUBSIDIES) }) { Text("申请记录", color = MaterialTheme.colorScheme.primary) }
                }
                if (state.section == MemberSection.SUBSIDIES && state.detail == null) {
                    TextButton(enabled = !state.busy, onClick = { model.load(MemberSection.CAMPAIGNS) }) { Text("活动", color = MaterialTheme.colorScheme.primary) }
                }
                if (state.section == MemberSection.TEAM) {
                    TextButton(onClick = entryModel::openInvite) { Text("邀请码", color = MaterialTheme.colorScheme.primary) }
                }
                if (state.section == MemberSection.COMMISSIONS) {
                    TextButton(enabled = !state.busy, onClick = { model.load(MemberSection.TEAM) }) { Text("直属团队", color = MaterialTheme.colorScheme.primary) }
                }
            })
        state.recoveryMessage?.let { message ->
            Text(message, Modifier.padding(horizontal = 22.dp, vertical = 6.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (state.recoveryPending) {
                TextButton(enabled = !state.recovering && !state.busy, onClick = { model.retryCampaignRecovery() }) { Text("重试补贴确认") }
            }
        }
        if (state.busy || appState.adBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (appState.adBusy) Text("正在加载插屏…")
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.notice?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
        if (!appState.adBusy) Column(Modifier.weight(1f).verticalScroll(contentScrollState).padding(horizontal = 22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val detail = state.detail
            if (detail != null) {
                DetailContent(state, model, detail, entryModel, appState, campaignReceiveName, campaignReceiveAccount,
                    onReceiveNameChange = { campaignReceiveName = it },
                    onReceiveAccountChange = { campaignReceiveAccount = it })
            } else when (state.section) {
                MemberSection.PROFILE -> state.profile?.let { ProfileForm(it, state.busy, model) }
                MemberSection.PASSWORD -> key(state.formRevision) { PasswordForm(state.busy, model) }
                MemberSection.OBSERVATIONS -> DeviceObservationScreen()
                else -> {
                    if (state.section == MemberSection.SUBSIDIES) {
                        Text("06 / HEHE DAILY", Modifier.padding(top = 20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.labelLarge)
                        Text("每一步进度，\n都清楚记录。", Modifier.padding(top = 18.dp),
                            style = MaterialTheme.typography.headlineLarge, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                        Text("审核结果与金币发放记录分开核对", Modifier.padding(top = 10.dp, bottom = 20.dp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            listOf(-1 to "全部", 0 to "待审核", 1 to "已通过", 2 to "未通过").forEach { (value, label) ->
                                Column(Modifier.weight(1f).clickable(enabled = !state.busy) {
                                    model.load(MemberSection.SUBSIDIES, status = value.takeIf { it >= 0 })
                                }.padding(vertical = 12.dp), horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                                    Text(label, color = if (recordFilter == value) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                                    Spacer(Modifier.height(8.dp))
                                    Box(Modifier.fillMaxWidth().height(2.dp).background(
                                        if (recordFilter == value) MaterialTheme.colorScheme.primary else Color.Transparent))
                                }
                            }
                        }
                        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    } else {
                        Text(when (state.section) {
                            MemberSection.CAMPAIGNS -> "先看清条件，再提交凭证。"
                            MemberSection.TEAM -> "每一位同行，都值得记住。"
                            MemberSection.COMMISSIONS -> "邀请与收益，以服务端记录为准。"
                            else -> "查看账户服务与处理记录。"
                        }, Modifier.padding(top = 14.dp, bottom = 8.dp), style = MaterialTheme.typography.headlineSmall,
                            fontWeight = androidx.compose.ui.text.font.FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Text("共 ${state.total} 条", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            TextButton(enabled = !state.busy, onClick = { model.load(status = state.subsidyStatus) }) { Text("刷新", color = MaterialTheme.colorScheme.primary) }
                        }
                    }
                    if (state.section == MemberSection.COINS) {
                        Text("当前可用金币", Modifier.padding(top = 14.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text((appState.serverCoin ?: appState.appBootstrap?.coin ?: java.math.BigDecimal.ZERO)
                            .stripTrailingZeros().toPlainString(), style = MaterialTheme.typography.displaySmall, color = MaterialTheme.colorScheme.primary)
                        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
                            listOf(0 to "全部", 1 to "收入", 2 to "支出").forEach { (value, label) ->
                                TextButton(onClick = { coinFilter = value }) {
                                    Text(label, color = if (coinFilter == value) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                    if (state.section == MemberSection.COMMISSIONS) state.commissionSummary?.let { summary ->
                        val level = listOf("用户", "团长", "历史 V2", "代理").getOrElse(summary.optInt("level")) { "用户" }
                        Text("累计佣金 · 金币", Modifier.padding(top = 18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(summary.optString("total_earned", "0"), style = MaterialTheme.typography.displaySmall,
                            color = MaterialTheme.colorScheme.primary, fontWeight = androidx.compose.ui.text.font.FontWeight.Medium)
                        Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("今日佣金", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text("${summary.optString("today_earned", "0")} 金币", style = MaterialTheme.typography.titleLarge,
                                    color = MaterialTheme.colorScheme.onSurface)
                            }
                            Column(horizontalAlignment = androidx.compose.ui.Alignment.End) {
                                Text("直属邀请", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text("${summary.optInt("direct_members")} 人", style = MaterialTheme.typography.titleLarge,
                                    color = MaterialTheme.colorScheme.onSurface)
                            }
                        }
                        MemberDetailRow("当前身份", level)
                        Text("佣金已计入钱包余额，无需单独领取。", Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (state.section == MemberSection.TEAM) {
                        Row(Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Text("直属邀请", Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall,
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                            Text(if (state.total == 0) "暂无记录" else "共 ${state.total} 人", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (state.items.isEmpty()) {
                            Column(Modifier.fillMaxWidth().padding(top = 8.dp)
                                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(6.dp))
                                .padding(horizontal = 20.dp, vertical = 28.dp),
                                horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                                Box(Modifier.size(64.dp).background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(50)),
                                    contentAlignment = androidx.compose.ui.Alignment.Center) {
                                    Icon(Icons.Filled.Person, contentDescription = null, modifier = Modifier.size(34.dp),
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Text("还没有邀请记录", Modifier.padding(top = 16.dp), style = MaterialTheme.typography.titleLarge,
                                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                                Text("直属成员与已产生收益会在这里记录。", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                                OutlinedButton(onClick = entryModel::openInvite, modifier = Modifier.align(androidx.compose.ui.Alignment.Start).padding(top = 16.dp)) {
                                    Text("查看我的邀请码", color = MaterialTheme.colorScheme.primary, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                                }
                            }
                        }
                    }
                    val visibleItems = if (state.section == MemberSection.COINS && coinFilter != 0) {
                        state.items.filter { (it.decimal("coin").signum() > 0) == (coinFilter == 1) }
                    } else state.items
                    if (visibleItems.isEmpty() && !state.busy && state.error == null && state.section != MemberSection.TEAM) {
                        val emptyMessage = when (state.section) {
                            MemberSection.GAMES -> "暂无可用游戏"
                            MemberSection.COINS -> when {
                                state.total == 0 -> "暂无金币流水"
                                state.hasMore -> "当前页没有符合条件的流水，可继续加载"
                                coinFilter == 1 -> "暂无收入记录"
                                coinFilter == 2 -> "暂无支出记录"
                                else -> "暂无金币流水"
                            }
                            MemberSection.WITHDRAWALS -> "暂无提现记录"
                            MemberSection.ADS -> "暂无广告记录"
                            MemberSection.CAMPAIGNS -> "暂时没有补贴活动"
                            MemberSection.SUBSIDIES -> "暂无申请记录"
                            MemberSection.COMMISSIONS -> "暂无佣金记录"
                            else -> "暂无记录"
                        }
                        Text(emptyMessage, Modifier.fillMaxWidth().padding(vertical = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    visibleItems.forEach { item ->
                        if (state.section == MemberSection.SUBSIDIES) {
                            SubsidyRecordRow(item) { model.detail(item.get("id").toString()) }
                        } else {
                            Column(Modifier.fillMaxWidth().clickable(enabled = state.section in listOf(MemberSection.WITHDRAWALS, MemberSection.CAMPAIGNS)) {
                                model.detail(item.get("id").toString())
                            }.padding(vertical = 16.dp)) {
                                RecordContent(state.section, item)
                                if (state.section in listOf(MemberSection.WITHDRAWALS, MemberSection.CAMPAIGNS)) {
                                    Text("查看详情  →", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.primary)
                                }
                            }
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        }
                    }
                    if (state.section == MemberSection.TEAM && state.items.isNotEmpty()) {
                        OutlinedButton(onClick = entryModel::openInvite, modifier = Modifier.fillMaxWidth()) {
                            Text("查看我的邀请码", color = MaterialTheme.colorScheme.primary)
                        }
                    }
                    if (state.hasMore) OutlinedButton(enabled = !state.busy, onClick = { model.load(append = true) }, modifier = Modifier.fillMaxWidth()) { Text("加载更多") }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
        if (showApprovedSubsidyCheck) {
            Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 4.dp) {
                Button(onClick = { entryModel.openMemberSection(MemberSection.COINS) },
                    modifier = Modifier.navigationBarsPadding().padding(horizontal = 22.dp, vertical = 10.dp).fillMaxWidth().height(54.dp)) {
                    Text("核对金币明细  →")
                }
            }
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
    Text("修改密码需要输入当前系统密码。微信首次登录时设置系统密码；绑定支付宝时使用已有密码验证，无需重新设置。")
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
private fun CampaignApplicationFields(
    state: MemberCenterState,
    model: MemberCenterViewModel,
    receiveName: String,
    receiveAccount: String,
    onReceiveNameChange: (String) -> Unit,
    onReceiveAccountChange: (String) -> Unit
) {
    var slot by remember { mutableStateOf("download_image") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { model.upload(slot, it) }
    }
    HorizontalDivider(Modifier.padding(vertical = 20.dp), color = MaterialTheme.colorScheme.outlineVariant)
    Text("上传凭证", style = MaterialTheme.typography.titleMedium,
        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
    Text("补贴金额以元展示，审核通过后按后台配置发放金币。",
        Modifier.padding(top = 8.dp, bottom = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        listOf("download_image" to "下载截图", "install_image" to "安装来源截图", "recharge_image" to "充值截图")
            .forEach { (id, label) ->
                Column(Modifier.weight(1f), horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                    OutlinedButton(enabled = !state.busy, onClick = { slot = id; picker.launch("image/*") },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 110.dp), shape = RoundedCornerShape(10.dp),
                        contentPadding = PaddingValues(6.dp)) {
                        Column(horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                            Text(if (state.images.containsKey(id)) "✓" else "+", style = MaterialTheme.typography.headlineSmall)
                            Text(label, style = MaterialTheme.typography.labelSmall,
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                            Text(if (state.images.containsKey(id)) "点击更换" else "选择图片", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
    }
    listOf("download_image" to "下载截图", "install_image" to "安装来源截图", "recharge_image" to "充值截图").forEach { (id, label) ->
        state.images[id]?.let { EvidencePreview(label, it) }
    }
    Row(Modifier.fillMaxWidth().padding(top = 22.dp, bottom = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text("申请信息", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge,
            fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
        Text("请核对无误", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
    }
    Field("收款姓名", receiveName, state.busy, onReceiveNameChange)
    Field("收款账号", receiveAccount, state.busy, onReceiveAccountChange)
}

@Composable
private fun SubsidyRecordRow(item: JSONObject, onClick: () -> Unit) {
    val status = item.optInt("status", -1)
    val statusLabel = when (status) { 0 -> "待审核"; 1 -> "已通过"; 2 -> "未通过"; else -> "待确认" }
    val statusColor = when (status) {
        0 -> Color(0xFF9A762F)
        1 -> Color(0xFF638369)
        2 -> Color(0xFFB4514D)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val statusBg = when (status) {
        0 -> MaterialTheme.colorScheme.secondaryContainer
        1 -> Color(0xFFE6F0E7)
        2 -> Color(0xFFFFE6E2)
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val dateParts = formatMemberRecordTime(item.optString("created_at")).substringBefore(' ')
        .split('.').takeIf { it.size == 2 }
    val month = dateParts?.getOrNull(0).orEmpty()
    val day = dateParts?.getOrNull(1).orEmpty()
    val title = item.optJSONObject("campaign")?.optString("title")?.takeIf(String::isNotBlank)
        ?: "补贴申请 #${item.opt("id")}"
    val hint = if (status == 1) "查看审核与实际金币到账记录  →" else "查看提交信息与处理进度  →"
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 18.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Column(Modifier.width(48.dp)) {
                Text(day.ifBlank { "--" }, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.titleMedium)
                Text("${month.ifBlank { "--" }}月", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
            Text(statusLabel, Modifier.background(statusBg, RoundedCornerShape(5.dp))
                .padding(horizontal = 10.dp, vertical = 6.dp), color = statusColor,
                style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.weight(1f))
            Text("¥${item.decimal("price").setScale(2, java.math.RoundingMode.HALF_UP).toPlainString()}",
                color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.headlineSmall,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Medium)
        }
        Text(title, Modifier.padding(start = 48.dp, top = 10.dp),
            style = MaterialTheme.typography.titleMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface, maxLines = 2, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
        Text(hint, Modifier.padding(start = 48.dp, top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodySmall)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
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
            val coin = item.decimal("coin")
            val title = when (item.optInt("type", -1)) {
                302 -> "补贴审核到账"
                else -> item.optString("remark").ifBlank { "金币变动" }
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold)
                Text("${if (coin.signum() > 0) "+" else ""}${coin.toPlainString()}",
                    color = if (coin.signum() > 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.titleLarge)
            }
            item.optString("remark").takeIf { it.isNotBlank() && it != title }?.let {
                Text(it, Modifier.padding(top = 5.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("变动后余额 ${item.decimal("coin_after").toPlainString()} 金币",
                Modifier.padding(top = 5.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
        MemberSection.WITHDRAWALS -> {
            val record = parseWithdrawal(item)
            Text("¥${centsText(record.amountCents)} · ${withdrawalStatus(item)}")
            Text("消耗金币：${record.coin}")
        }
        MemberSection.ADS -> {
            Text(formatMemberRecordTime(item.optString("watched_at")))
            Text("${item.decimal("coin_added").stripTrailingZeros().toPlainString()} 金币")
        }
        MemberSection.CAMPAIGNS -> {
            Text(item.optString("title"), style = MaterialTheme.typography.titleMedium)
            Text("奖励 ¥${centsText(item.optLong("reward_cents"))} · 剩余名额 ${item.optInt("remaining")}")
        }
        MemberSection.SUBSIDIES -> {
            val status = item.optInt("status", -1)
            val statusLabel = when (status) { 0 -> "待审核"; 1 -> "已通过"; 2 -> "未通过"; else -> "状态待确认" }
            val campaignTitle = item.optJSONObject("campaign")?.optString("title")?.takeIf(String::isNotBlank)
            Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(campaignTitle ?: "补贴申请 #${item.opt("id")}", Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold)
                Text(statusLabel, color = when (status) {
                    0 -> Color(0xFF9A762F)
                    1 -> Color(0xFF638369)
                    2 -> Color(0xFFB4514D)
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                })
            }
            Row(Modifier.fillMaxWidth().padding(top = 5.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text("补贴金额", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("¥${item.decimal("price").toPlainString()}", color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.titleMedium)
            }
            item.optJSONObject("campaign")?.optString("review_due_at")?.takeIf(String::isNotBlank)?.let {
                Text("审核目标时间：$it", Modifier.padding(top = 5.dp), color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall)
            }
            item.optString("sub_msg").takeIf(String::isNotBlank)?.let {
                Text(it, Modifier.padding(top = 5.dp), color = if (status == 2) Color(0xFF9D504A) else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        else -> Unit
    }
    if (section != MemberSection.ADS && item.has("created_at")) Text(formatMemberRecordTime(item.optString("created_at")), style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun DetailContent(
    state: MemberCenterState,
    model: MemberCenterViewModel,
    detail: JSONObject,
    entryModel: QuizViewModel,
    appState: UiState,
    campaignReceiveName: String,
    campaignReceiveAccount: String,
    onReceiveNameChange: (String) -> Unit,
    onReceiveAccountChange: (String) -> Unit
) {
    if (state.section != MemberSection.CAMPAIGNS) {
        Text(when (state.section) {
            MemberSection.SUBSIDIES -> when (detail.optInt("status")) { 0 -> "申请审核中"; 1 -> "审核已通过"; else -> "申请未通过" }
            MemberSection.WITHDRAWALS -> withdrawalStatus(detail)
            else -> "申请详情"
        }, Modifier.padding(top = 14.dp), style = MaterialTheme.typography.headlineMedium,
            fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
        RecordContent(state.section, detail)
    }
    when (state.section) {
        MemberSection.CAMPAIGNS -> {
            ReferencePanel(radius = 16.dp, padding = 16.dp) {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Image(androidx.compose.ui.res.painterResource(com.example.idiomquiz.R.drawable.moban_avatar), null, Modifier.size(34.dp))
                    Text("ID：${appState.currentUser?.id ?: "—"}", Modifier.padding(start = 10.dp),
                        style = MaterialTheme.typography.titleMedium)
                }
                Text(detail.optString("title", "补贴活动"), style = MaterialTheme.typography.titleMedium)
                Text("今日已用 ${detail.optInt("used")} 人　剩余名额 ${detail.optInt("remaining")} 人",
                    Modifier.fillMaxWidth().background(AppPalette.PrimarySoft, RoundedCornerShape(12.dp)).padding(12.dp))
                Text("领取必知：补贴 ¥${centsText(detail.optLong("reward_cents"))}，需满足提现 ¥${centsText(detail.optLong("withdrawal_cents"))}、充值 ¥${centsText(detail.optLong("recharge_cents"))}。",
                    Modifier.fillMaxWidth().background(AppPalette.Background, RoundedCornerShape(12.dp)).padding(12.dp),
                    style = MaterialTheme.typography.bodyMedium)
                if (detail.optBoolean("eligible")) key(detail.get("id")) {
                    CampaignApplicationFields(state, model, campaignReceiveName, campaignReceiveAccount,
                        onReceiveNameChange, onReceiveAccountChange)
                } else {
                    Text(if (detail.optBoolean("enabled")) "暂未满足申请条件" else "活动暂不可申请", color = MaterialTheme.colorScheme.error)
                }
                val reasons = detail.optJSONArray("reasons")
                if (reasons != null) for (i in 0 until reasons.length()) {
                    Text(reasons.getString(i), style = MaterialTheme.typography.bodySmall)
                }
                Text("今日已确认提现：¥${centsText(detail.optLong("confirmed_withdrawal_cents"))}", style = MaterialTheme.typography.bodySmall)
                OutlinedButton(enabled = !state.busy, onClick = { model.detail(detail.get("id").toString()) }) { Text("刷新资格") }
            }
            Button(
                onClick = { model.applySubsidy(campaignReceiveName, campaignReceiveAccount, "", true) },
                enabled = detail.optBoolean("eligible") && !state.busy && campaignReceiveName.isNotBlank() && campaignReceiveAccount.isNotBlank() &&
                    listOf("download_image", "install_image", "recharge_image").mapNotNull(state.images::get).distinct().size == 3,
                modifier = Modifier.padding(horizontal = 12.dp).fillMaxWidth().heightIn(min = 52.dp), shape = RoundedCornerShape(26.dp)
            ) { Text(if (detail.optBoolean("eligible")) "确认提交申请" else "暂未满足申请条件", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold) }
            ReferencePanel(radius = 16.dp, padding = 16.dp) {
                Text("提交的图片请仔细核对后再提交", style = MaterialTheme.typography.titleMedium)
                Text(detail.optString("instructions").takeIf(String::isNotBlank) ?: "按活动要求完成体验并保留相关凭证。")
                Text("1、分别上传下载截图、安装来源和充值截图，三张图片不能重复。")
                Text("2、审核目标为 ${detail.optInt("review_hours")} 小时，以实际审核结果为准。")
                Text("3、审核通过后按后台比例发放金币，请到金币明细核对到账。")
            }
        }
        MemberSection.WITHDRAWALS -> {
            val payout = detail.optJSONObject("payout")
            val record = parseWithdrawal(detail)
            Text("¥${centsText(record.amountCents)}", Modifier.padding(top = 12.dp),
                style = MaterialTheme.typography.displaySmall, color = MaterialTheme.colorScheme.primary)
            Text("提现处理进度", Modifier.padding(top = 20.dp, bottom = 8.dp), style = MaterialTheme.typography.titleLarge,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            val payoutState = payout?.optString("state").orEmpty()
            val progress = when (payoutState) {
                "succeeded" -> listOf("申请已提交" to true, "审核已通过" to true, "渠道已确认到账" to true)
                "failed", "rejected" -> listOf("申请已提交" to true, "处理未完成" to true)
                "processing" -> listOf("申请已提交" to true, "审核已通过" to true, "渠道打款处理中" to false)
                "queued" -> listOf("申请已提交" to true, "审核已通过" to true, "等待渠道打款" to false)
                "pending_review" -> listOf("申请已提交" to true, "等待审核" to false)
                else -> listOf("提现申请记录" to true, "渠道状态待确认" to false)
            }
            progress.forEachIndexed { index, (label, active) ->
                SubsidyTimeline(label, if (index == 0) formatMemberRecordTime(detail.optString("created_at")) else "", active,
                    isLast = index == progress.lastIndex)
            }
            MemberDetailRow("冻结金币", "${record.coin} 金币")
            MemberDetailRow("收款人", detail.optString("receive_name").ifBlank { "未提供" })
            MemberDetailRow("收款账号", payout?.optString("account_masked")?.takeIf(String::isNotBlank) ?: "以绑定账户为准")
            payout?.optString("out_biz_no")?.takeIf(String::isNotBlank)?.let { MemberDetailRow("提现订单号", it) }
            payout?.optString("provider_order_id")?.takeIf(String::isNotBlank)?.let { MemberDetailRow("渠道订单号", it) }
            payout?.optString("error")?.takeIf { it.isNotBlank() }?.let {
                Text("处理说明：$it", Modifier.padding(top = 14.dp), color = Color(0xFF9D504A))
            }
            OutlinedButton(enabled = !state.busy, onClick = { model.detail(detail.get("id").toString()) }) { Text("刷新状态") }
        }
        MemberSection.SUBSIDIES -> {
            val status = detail.optInt("status")
            Text("补贴金额 ¥${detail.decimal("price").toPlainString()}", Modifier.padding(top = 12.dp),
                style = MaterialTheme.typography.displaySmall,
                color = if (status == 1) Color(0xFF638369) else MaterialTheme.colorScheme.primary)
            Text(when (status) { 0 -> "审核处理中"; 1 -> "审核已通过"; 2 -> "审核未通过"; else -> "状态待确认" },
                Modifier.padding(bottom = 8.dp), style = MaterialTheme.typography.titleLarge,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                color = when (status) { 0 -> Color(0xFF9A762F); 1 -> Color(0xFF638369); 2 -> Color(0xFFB4514D); else -> MaterialTheme.colorScheme.onSurfaceVariant })
            MemberDetailRow("收款姓名", detail.optString("receive_name"))
            MemberDetailRow("收款账号", detail.optString("receive_tel"))
            detail.optJSONObject("campaign")?.let {
                MemberDetailRow("申请活动", it.optString("title"))
                val dueAt = it.optString("review_due_at").takeIf(String::isNotBlank)
                if (dueAt != null) MemberDetailRow("审核目标时间", dueAt + if (it.optBoolean("overdue")) " · 已超过目标时间" else "")
                MemberDetailRow("申请条件", "提现 ¥${centsText(it.optLong("withdrawal_cents"))} · 充值 ¥${centsText(it.optLong("recharge_cents"))}")
            }
            Text("处理进度", Modifier.padding(top = 24.dp, bottom = 8.dp), style = MaterialTheme.typography.titleLarge,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            SubsidyTimeline("申请已提交", formatMemberRecordTime(detail.optString("created_at")), active = true,
                isLast = false)
            if (status == 0) SubsidyTimeline("等待审核", "审核完成后会更新状态", active = false, isLast = true)
            else SubsidyTimeline(if (status == 1) "审核已通过" else "审核未通过",
                formatMemberRecordTime(detail.optString("audited_at").ifBlank { detail.optString("updated_at") }), active = true,
                isLast = true)
            val evidence = detail.optJSONObject("campaign")?.optJSONObject("evidence")
            val evidenceLabels = listOf("download_image" to "下载截图", "install_image" to "安装来源截图", "recharge_image" to "充值截图")
            if (evidence != null) {
                Text("申请凭证", Modifier.padding(top = 22.dp), style = MaterialTheme.typography.titleLarge,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                evidenceLabels.forEach { (key, label) ->
                    val url = evidence.optString(key).takeIf(String::isNotBlank)
                    if (url == null) MemberDetailRow(label, "无记录") else EvidencePreview(label, url)
                }
            } else {
                val pics = detail.optString("pics").split(',').filter(String::isNotBlank)
                if (pics.isNotEmpty()) {
                    Text("申请凭证", Modifier.padding(top = 22.dp), style = MaterialTheme.typography.titleLarge,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                    pics.forEachIndexed { index, url -> EvidencePreview("凭证 ${index + 1}", url.trim()) }
                }
            }
            if (status == 1) {
                Text("审核通过后的金币按审核时配置比例发放，请以钱包余额和金币流水为准。",
                    Modifier.padding(top = 18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else if (status == 2) {
                Text(detail.optString("sub_msg"), Modifier.padding(top = 14.dp), color = Color(0xFF9D504A))
            }
        }
        else -> Unit
    }
}

@Composable
private fun EvidencePreview(label: String, path: String) {
    var loading by remember(path) { mutableStateOf(true) }
    val bitmap by produceState<Bitmap?>(null, path) {
        value = withContext(Dispatchers.IO) { loadEvidenceBitmap(path) }
        loading = false
    }
    var expanded by remember(path) { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        val loaded = bitmap
        if (loaded == null) {
            Box(Modifier.padding(top = 8.dp).size(112.dp).background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp)),
                contentAlignment = androidx.compose.ui.Alignment.Center) {
                Text(if (loading) "正在加载" else "暂时无法预览", color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall)
            }
        } else {
            Image(loaded.asImageBitmap(), contentDescription = "$label，点按查看大图",
                modifier = Modifier.padding(top = 8.dp).size(112.dp).clickable { expanded = true },
                contentScale = ContentScale.Crop)
        }
    }
    if (expanded && bitmap != null) {
        Dialog(onDismissRequest = { expanded = false }) {
            Surface(shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.surface) {
                Column(Modifier.padding(12.dp)) {
                    Text(label, style = MaterialTheme.typography.titleMedium)
                    Image(bitmap!!.asImageBitmap(), contentDescription = label,
                        modifier = Modifier.fillMaxWidth().heightIn(max = 520.dp).clickable { expanded = false },
                        contentScale = ContentScale.Fit)
                }
            }
        }
    }
}

private fun loadEvidenceBitmap(path: String): Bitmap? {
    val base = URL(BuildConfig.USER_API_BASE_URL)
    val url = URL(base, path)
    require(url.host == base.host && url.port == base.port &&
        (url.protocol == "https" || url.protocol == base.protocol))
    val connection = url.openConnection() as HttpURLConnection
    connection.connectTimeout = 10000
    connection.readTimeout = 10000
    connection.instanceFollowRedirects = false
    return try {
        if (connection.responseCode != HttpURLConnection.HTTP_OK) return null
        val bytes = connection.inputStream.use { stream ->
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                if (output.size() + count > 8 * 1024 * 1024) return null
                output.write(buffer, 0, count)
            }
            output.toByteArray()
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        val options = BitmapFactory.Options().apply { inSampleSize = 1 }
        while (maxOf(bounds.outWidth, bounds.outHeight) / options.inSampleSize > 1200) options.inSampleSize *= 2
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
    } catch (error: CancellationException) {
        throw error
    } catch (_: Exception) {
        null
    } finally {
        connection.disconnect()
    }
}

@Composable
private fun SubsidyTimeline(title: String, detail: String, active: Boolean, isLast: Boolean) {
    Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = androidx.compose.ui.Alignment.Top) {
        Column(Modifier.width(12.dp).defaultMinSize(minHeight = 28.dp), horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
            Box(Modifier.padding(top = 5.dp).size(12.dp).background(
                if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(50)))
            if (!isLast) Box(Modifier.width(1.dp).weight(1f).background(MaterialTheme.colorScheme.outlineVariant))
        }
        Column(Modifier.padding(start = 14.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium,
                fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            if (detail.isNotBlank()) Text(detail, Modifier.padding(top = 4.dp),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun MemberDetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, color = MaterialTheme.colorScheme.onSurface)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun SubsidyForm(state: MemberCenterState, model: MemberCenterViewModel) {
    var name by remember { mutableStateOf("") }
    var account by remember { mutableStateOf("") }
    var amount by remember { mutableStateOf("") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { model.upload("proof", it) }
    }
    Field("收款姓名", name, state.busy) { name = it }
    Field("收款账号", account, state.busy) { account = it }
    Field("提现条件金额（元）", amount, state.busy) { amount = it }
    Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("申请凭证", style = MaterialTheme.typography.titleMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            Text(if (state.images.containsKey("proof")) "凭证已上传，可点击更换" else "支持 PNG、JPEG、WebP，最大 2MB",
                Modifier.padding(top = 4.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
        OutlinedButton(enabled = !state.busy, onClick = { picker.launch("image/*") }) {
            Text(if (state.images.containsKey("proof")) "更换图片" else "选择图片", color = MaterialTheme.colorScheme.primary)
        }
    }
    state.images["proof"]?.let { EvidencePreview("申请凭证", it) }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    Button(enabled = !state.busy, onClick = { model.applySubsidy(name, account, amount, false) },
        modifier = Modifier.fillMaxWidth().height(54.dp), colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) {
        Text("确认提交申请", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
    }
}
