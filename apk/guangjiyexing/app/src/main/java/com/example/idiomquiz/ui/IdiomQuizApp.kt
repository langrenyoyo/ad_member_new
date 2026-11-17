@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.idiomquiz.ui

import androidx.lifecycle.repeatOnLifecycle

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.util.Log
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.Image
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.snapshotFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.distinctUntilChanged
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.automirrored.outlined.VolumeOff
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.NotificationsNone
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.CardGiftcard
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.BarChart
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.CheckCircleOutline
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.FormatQuote
import androidx.compose.material.icons.outlined.Insights
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.PlayCircle
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material.icons.outlined.Vibration
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DividerDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.VerticalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.viewinterop.AndroidView
import com.example.idiomquiz.ads.AnyThinkAdManager
import com.example.idiomquiz.R
import com.example.idiomquiz.data.AdPlacement
import com.example.idiomquiz.data.AppSettings
import com.example.idiomquiz.data.AuthProvider
import com.example.idiomquiz.data.IdiomEntity
import com.example.idiomquiz.data.QuizMode
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.roundToInt

private val CardShape = RoundedCornerShape(20.dp)
private const val SPLASH_AD_ENABLED = false

@Composable
fun IdiomQuizApp(state: UiState, viewModel: QuizViewModel) {
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }
    androidx.compose.runtime.DisposableEffect(state.currentUser?.id, state.appBootstrap, context) {
        onDispose { AnyThinkAdManager.clearInterstitialPreload() }
    }
    LaunchedEffect(state.currentUser?.id, state.adSdkReady, state.adBusy, state.appBootstrap) {
        if (state.currentUser != null && state.adSdkReady && !state.adBusy) {
            val activity = context.findActivity()
            val placement = state.appBootstrap?.let(AnyThinkAdManager::interstitialPlacement)
            if (activity != null && placement != null) AnyThinkAdManager.preloadInterstitial(activity, placement)
        }
    }
    if (state.announcementPending) {
        StartupAnnouncement(state, viewModel)
        return
    }
    val onboarding = state.onboarding
    val policy = onboarding?.optJSONObject("policy")
    val needsInvite = policy?.optBoolean("require_invite") == true && onboarding.optInt("parent_id") == 0
    val needsUsage = policy?.optBoolean("require_usage") == true && onboarding.optBoolean("usage_granted") != true
    val needsAlipay = policy?.optBoolean("require_alipay") == true && onboarding.optBoolean("alipay_bound") != true
    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    LaunchedEffect(state.currentUser?.id, lifecycleOwner) {
        if (state.currentUser != null) {
            lifecycleOwner.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.RESUMED) {
                try {
                    while (true) {
                        viewModel.checkUsageOnResume()
                        viewModel.refreshOnboarding()
                        kotlinx.coroutines.delay(60_000)
                    }
                } finally { viewModel.pauseOnboardingRefresh() }
            }
        }
    }
    // Render feedback before the onboarding return so it stays visible at any scroll position.
    if (state.screen == AppScreen.WALLET) {
        state.message?.let { message ->
            AlertDialog(
                onDismissRequest = viewModel::clearMessage,
                title = { Text("操作提示") },
                text = { Text(message) },
                confirmButton = { TextButton(onClick = viewModel::clearMessage) { Text("知道了") } }
            )
        }
    }
    val recoveryWallet = state.onboardingBlockCode == "DEVICE_COOLDOWN" && state.screen == AppScreen.WALLET
    if (state.currentUser != null && !recoveryWallet && onboardingBlocks(onboarding != null,
            state.onboardingBlockCode, needsInvite, needsUsage, needsAlipay, state.screen == AppScreen.WALLET)) {
        OnboardingScreen(state, viewModel, needsInvite, needsUsage, needsAlipay && state.screen == AppScreen.WALLET)
        return
    }

    val rewardNotice = state.rewardNotices.firstOrNull()
    if (rewardNotice != null && !state.adBusy && state.currentUser != null) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissRewardNotice(rewardNotice.sessionId) },
            icon = {
                Icon(Icons.Filled.AccountBalanceWallet, contentDescription = null,
                    tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(40.dp))
            },
            title = { Text("奖励已到账", fontWeight = FontWeight.Bold) },
            text = {
                Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("本次观看广告获得", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("+${rewardNotice.coin.stripTrailingZeros().toPlainString()} 金币",
                        style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary, textAlign = TextAlign.Center)
                    Text("金币已计入您的钱包", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            },
            confirmButton = {
                Button(onClick = { viewModel.dismissRewardNotice(rewardNotice.sessionId) }, modifier = Modifier.fillMaxWidth()) {
                    Text("知道了")
                }
            }
        )
    }

    if (state.showRiskConsent) {
        val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
        AlertDialog(
            onDismissRequest = { viewModel.respondToRiskConsent(false) },
            title = { Text("设备安全检测") },
            text = {
                Column {
                    Text("为识别异常设备和广告作弊，本功能使用阿里云风险识别 SDK。在您同意并再次点击观看广告时，将采集设备型号、系统版本、屏幕信息，以及可获取的 Android ID、OAID、广告标识，并通过网络交由阿里云检测。当前配置关闭不可变设备标识及应用列表、Wi-Fi 等扩展信息采集。不另行申请电话或存储权限。拒绝不影响学习功能。")
                    TextButton(onClick = {
                        runCatching { uriHandler.openUri("https://terms.aliyun.com/legal-agreement/terms/suit_bu1_ali_cloud/suit_bu1_ali_cloud202111120818_92724.html") }
                            .onFailure { viewModel.showMessage("无法打开隐私政策，请检查浏览器") }
                    }) { Text("阿里云风险识别 SDK 隐私政策") }
                }
            },
            confirmButton = { TextButton(onClick = { viewModel.respondToRiskConsent(true) }) { Text("同意") } },
            dismissButton = { TextButton(onClick = { viewModel.respondToRiskConsent(false) }) { Text("暂不开启") } }
        )
    }

    LaunchedEffect(state.appBootstrap, state.adSdkReady) {
        if (!SPLASH_AD_ENABLED) return@LaunchedEffect
        if (!state.adSdkReady) return@LaunchedEffect

        val activity = context.findActivity() ?: return@LaunchedEffect
        val bootstrap = state.appBootstrap ?: return@LaunchedEffect
        val placement = AnyThinkAdManager.splashPlacement(bootstrap) ?: return@LaunchedEffect
        AnyThinkAdManager.loadAndShowSplash(activity, placement)
    }

    LaunchedEffect(state.message, state.screen) {
        if (state.screen == AppScreen.WALLET) return@LaunchedEffect
        state.message?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    val hasBottomBar = state.screen in setOf(
        AppScreen.HOME,
        AppScreen.BENEFITS,
        AppScreen.AD_DEMO,
        AppScreen.INVITE,
        AppScreen.PROFILE
    )

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        bottomBar = {
            if (hasBottomBar && state.initialized) {
                AppBottomBar(state = state, viewModel = viewModel)
            }
        },
        contentWindowInsets = WindowInsets.navigationBars
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            if (!state.initialized) {
                LoadingScreen()
            } else {
                when (state.screen) {
                    AppScreen.HOME -> HomeScreen(state, viewModel)
                    AppScreen.BENEFITS -> BenefitsScreen(state, viewModel)
                    AppScreen.NOTICE -> NoticeScreen(state, viewModel)
                    AppScreen.INVITE -> InviteScreen(state, viewModel)
                    AppScreen.MODE_SELECTION -> ModeSelectionScreen(state, viewModel)
                    AppScreen.QUIZ -> QuizScreen(state, viewModel)
                    AppScreen.RESULT -> ResultScreen(state, viewModel)
                    AppScreen.MISTAKES -> MistakesScreen(state, viewModel)
                    AppScreen.FAVORITES -> FavoritesScreen(state, viewModel)
                    AppScreen.STATS -> StatsScreen(state, viewModel)
                    AppScreen.SETTINGS -> SettingsScreen(state, viewModel)
                    AppScreen.AD_DEMO -> AdDemoScreen(state, viewModel)
                    AppScreen.AD_HISTORY -> AdHistoryScreen(state, viewModel)
                    AppScreen.WALLET -> WalletScreen(state, viewModel)
                    AppScreen.DETAIL -> DetailScreen(state, viewModel)
                    AppScreen.PROFILE -> ProfileScreen(state, viewModel)
                    AppScreen.MEMBER_CENTER -> {
                        val memberModel = viewModel.memberCenterModel(state.currentUser?.id)
                        MemberCenterScreen(memberModel, viewModel, state) {
                            if (state.detailOrigin == AppScreen.BENEFITS) viewModel.openBenefits() else viewModel.openProfile()
                        }
                    }
                    AppScreen.LOGIN -> LoginScreen(state, viewModel)
                }
            }
        }
    }
}

@Composable
private fun StartupAnnouncement(state: UiState, viewModel: QuizViewModel) {
    val context = LocalContext.current
    androidx.activity.compose.BackHandler { context.findActivity()?.finishAndRemoveTask() }
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background))
    AlertDialog(
        onDismissRequest = {},
        properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false),
        title = {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("公告", Modifier.weight(1f))
                IconButton(onClick = viewModel::dismissStartupAnnouncement,
                    enabled = state.registrationPolicy != null && !state.registrationPolicyLoading) {
                    Icon(Icons.Filled.Close, contentDescription = "关闭公告")
                }
            }
        },
        text = {
            Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                when {
                    state.registrationPolicyLoading -> { CircularProgressIndicator(); Text("正在获取公告…") }
                    state.registrationPolicy == null -> {
                        Text("公告加载失败，请检查网络后重试。")
                        TextButton(onClick = viewModel::loadRegistrationPolicy) { Text("重新加载公告") }
                    }
                    else -> Text(state.registrationPolicy.announcement.ifBlank { "暂无公告内容" })
                }
            }
        },
        confirmButton = {}
    )
}

@Composable
private fun LoadingScreen() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding(),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator()
            Spacer(Modifier.height(16.dp))
            Text("正在准备题库", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun AppBottomBar(state: UiState, viewModel: QuizViewModel) {
    NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
        NavigationBarItem(
            selected = state.screen == AppScreen.HOME,
            onClick = viewModel::goHome,
            icon = { Icon(Icons.AutoMirrored.Outlined.MenuBook, contentDescription = "学习") },
            label = { Text("学习") }
        )
        NavigationBarItem(
            selected = state.screen == AppScreen.BENEFITS,
            onClick = viewModel::openBenefits,
            icon = { Icon(Icons.Filled.CardGiftcard, contentDescription = "福利") },
            label = { Text("福利") }
        )
        NavigationBarItem(
            selected = state.screen == AppScreen.AD_DEMO,
            onClick = viewModel::openAdDemo,
            icon = {
                Surface(shape = RoundedCornerShape(18.dp), color = AppPalette.Primary,
                    shadowElevation = 6.dp, modifier = Modifier.size(52.dp)) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(Icons.Filled.CardGiftcard, contentDescription = "奖励", tint = Color.White, modifier = Modifier.size(30.dp))
                    }
                }
            },
            label = { Text("奖励", color = AppPalette.Primary, fontWeight = FontWeight.Bold) }
        )
        NavigationBarItem(
            selected = state.screen == AppScreen.INVITE,
            onClick = viewModel::openInvite,
            icon = { Icon(Icons.Filled.PersonAdd, contentDescription = "邀请") },
            label = { Text("邀请") }
        )
        NavigationBarItem(
            selected = state.screen == AppScreen.PROFILE,
            onClick = viewModel::openProfile,
            icon = { Icon(Icons.Filled.Person, contentDescription = "我的") },
            label = { Text("我的") }
        )
    }
}

@Composable
private fun CatalogueEntry(@Suppress("UNUSED_PARAMETER") number: String, title: String, subtitle: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable(onClick = onClick).padding(vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            if (subtitle.isNotBlank()) Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
        }
        Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "打开$title", tint = MaterialTheme.colorScheme.outline, modifier = Modifier.size(18.dp))
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun BenefitsScreen(state: UiState, viewModel: QuizViewModel) {
    val campaigns = if (state.benefitOnlyEligible) {
        state.benefitCampaigns.filter { it.optBoolean("eligible") }
    } else state.benefitCampaigns
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.weight(1f).statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 18.dp)) {
            Row(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 22.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("福利中心", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                }
                IconButton(onClick = viewModel::openNotice) {
                    Icon(Icons.Filled.NotificationsNone, contentDescription = "公告", tint = MaterialTheme.colorScheme.onSurface)
                }
            }
            Row(Modifier.fillMaxWidth().padding(bottom = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                MemberAvatar(state.currentUser?.id, Modifier.size(36.dp))
                Text(state.currentUser?.let { "ID：${it.id}" } ?: "登录后查看补贴资格",
                    Modifier.weight(1f).padding(start = 10.dp), style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { viewModel.openMemberSection(MemberSection.SUBSIDIES) }) { Text("申请记录") }
            }
            Row(Modifier.fillMaxWidth().padding(bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(Modifier.weight(1f).clickable(onClick = { viewModel.openMemberSection(MemberSection.SUBSIDIES) })
                    .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(12.dp)).padding(14.dp)) {
                    Text("${state.pendingSubsidies} 笔", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold)
                    Text("待审核申请", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                }
                Column(Modifier.weight(1f).clickable(onClick = viewModel::openWallet)
                    .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(12.dp)).padding(14.dp)) {
                    Text((state.serverCoin ?: state.appBootstrap?.coin ?: java.math.BigDecimal.ZERO).stripTrailingZeros().toPlainString(),
                        style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text("可用金币", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                }
            }
            Row(Modifier.fillMaxWidth().clickable(onClick = viewModel::openNotice).padding(vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.NotificationsNone, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Text("当前公告 · 补贴申请须知", Modifier.weight(1f).padding(start = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "查看公告", tint = MaterialTheme.colorScheme.primary)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("补贴活动", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text("已展示 ${state.benefitCampaigns.size} 条", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                listOf(false to "全部", true to "可申请").forEach { (eligibleOnly, label) ->
                    TextButton(onClick = { viewModel.toggleEligibleBenefits(eligibleOnly) }) {
                        Text(label, color = if (state.benefitOnlyEligible == eligibleOnly) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                            fontWeight = if (state.benefitOnlyEligible == eligibleOnly) FontWeight.SemiBold else FontWeight.Normal)
                    }
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant, thickness = 1.dp)
            state.benefitError?.let { error ->
                Text(error, color = MaterialTheme.colorScheme.error)
                TextButton(onClick = { viewModel.openBenefits() }) { Text("重新加载") }
            }
            if (state.benefitLoading && state.benefitCampaigns.isEmpty()) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
            } else if (campaigns.isEmpty()) {
                if (state.benefitCampaigns.isEmpty()) {
                    Column(
                        Modifier.fillMaxWidth().padding(top = 24.dp)
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(20.dp))
                            .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(20.dp))
                            .padding(horizontal = 24.dp, vertical = 40.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Box(Modifier.size(64.dp).background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(50)),
                            contentAlignment = Alignment.Center) {
                            Icon(Icons.Filled.CardGiftcard, contentDescription = null, modifier = Modifier.size(38.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text("活动正在准备中", Modifier.padding(top = 18.dp), style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                        Text("有新活动时会在这里展示。", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedButton(onClick = viewModel::goHome, modifier = Modifier.padding(top = 18.dp)) {
                            Text("去学习", color = MaterialTheme.colorScheme.primary)
                        }
                    }
                } else {
                    Text("没有符合条件的活动", Modifier.padding(vertical = 28.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else campaigns.forEachIndexed { index, campaign ->
                BenefitCampaignRow(index + 1, campaign) { viewModel.showCampaign(campaign.optString("id")) }
            }
            if (state.benefitHasMore && state.benefitCampaigns.isNotEmpty()) {
                OutlinedButton(onClick = viewModel::loadMoreBenefits, enabled = !state.benefitLoading,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp)) {
                    if (state.benefitLoading) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Text("加载更多")
                }
            }
        }
    }
}

@Composable
private fun BenefitCampaignRow(index: Int, campaign: org.json.JSONObject, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = 12.dp).clip(RoundedCornerShape(20.dp))
        .background(MaterialTheme.colorScheme.surface).clickable(onClick = onClick).padding(18.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(index.toString().padStart(2, '0'), Modifier.width(48.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(campaign.optString("title", "补贴活动"), Modifier.weight(1f),
                style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(if (campaign.optBoolean("eligible")) "可申请" else "暂不符合",
                color = if (campaign.optBoolean("eligible")) Color(0xFF648052) else MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("剩余 ${campaign.optInt("remaining")} / ${campaign.optInt("daily_quota")} 个名额",
            Modifier.padding(start = 48.dp, top = 7.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("奖励 ¥${centsText(campaign.optLong("reward_cents"))}",
            Modifier.padding(start = 48.dp, top = 2.dp), color = MaterialTheme.colorScheme.primary)
        campaign.optJSONArray("reasons")?.takeIf { it.length() > 0 }?.let { reasons ->
            Text(reasons.opt(0)?.toString().orEmpty(), Modifier.padding(top = 5.dp), color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        Text("查看活动详情  →", Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun NoticeScreen(state: UiState, viewModel: QuizViewModel) {
    val announcement = state.onboarding?.optJSONObject("policy")?.optString("announcement")
        ?.takeIf { it.isNotBlank() && it != "null" } ?: "暂无公告内容"
    androidx.activity.compose.BackHandler(onBack = viewModel::closeNotice)
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding()
        .verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
        AppTopBar(title = "公告", onBack = viewModel::closeNotice)
        Text("申请须知", Modifier.padding(top = 16.dp),
            style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Medium)
        Text("当前应用公告 · 请以最新内容为准", Modifier.padding(top = 18.dp, bottom = 22.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Text(announcement, Modifier.fillMaxWidth().padding(vertical = 18.dp)
            .background(MaterialTheme.colorScheme.secondaryContainer, RoundedCornerShape(4.dp)).padding(16.dp),
            style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 26.sp)
        NoticeRule("01", "先确认活动资格", "每个活动的提现要求、充值条件和名额可能不同。请先完整阅读活动详情；申请前会重新核对资格。")
        NoticeRule("02", "三份凭证，分别上传", "下载截图、安装来源和充值截图请分别提供。图片应清晰完整，三张凭证不能重复使用同一张图片。")
        NoticeRule("03", "补贴金额与金币到账", "补贴金额以元展示。审核通过后按审核时后台配置比例发放金币，不会转为支付宝现金；请在钱包和金币流水中核对实际记录。")
        NoticeRule("04", "邀请码注册资格", "所有会员都可以查看自己的邀请码；强制注册规则开启时，只有符合规则的团长或代理邀请码可用于注册。")
        Text("认真对待每一步体验。\n禾合，陪你把每一天慢慢记好。",
            Modifier.fillMaxWidth().padding(top = 20.dp, bottom = 28.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge, lineHeight = 26.sp)
        Spacer(Modifier.height(28.dp))
    }
}

@Composable
private fun NoticeRule(number: String, title: String, description: String) {
    Column(Modifier.fillMaxWidth().padding(top = 22.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(number, Modifier.width(42.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.titleMedium)
            Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
        }
        Text(description, Modifier.padding(start = 42.dp, top = 14.dp, bottom = 20.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge, lineHeight = 27.sp)
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun AnyThinkBanner(placement: AdPlacement) {
    AndroidView(
        modifier = Modifier
            .fillMaxWidth()
            .height(50.dp),
        factory = { context ->
            AnyThinkAdManager.createBannerView(context, placement)
        },
        onRelease = AnyThinkAdManager::destroyBannerView
    )
}

internal fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> if (baseContext === this) null else baseContext.findActivity()
    else -> null
}

@Composable
private fun ModeSelectionScreen(state: UiState, viewModel: QuizViewModel) {
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.weight(1f).statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
            AppTopBar(title = "开始学习", onBack = viewModel::goHome)
            Text("选择练习方式", Modifier.padding(top = 16.dp),
                style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            Text("每局 10 题 · 学习积分单独累计", Modifier.padding(top = 12.dp, bottom = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            StudyModeRow("01", "释义选择题", "读释义，选出正确成语", state.selectedMode == QuizMode.DEFINITION) {
                viewModel.selectMode(QuizMode.DEFINITION)
            }
            StudyModeRow("02", "成语填空题", "补全成语，加深记忆", state.selectedMode == QuizMode.FILL_BLANK) {
                viewModel.selectMode(QuizMode.FILL_BLANK)
            }
            Row(Modifier.fillMaxWidth().padding(top = 24.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("难度", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text("按自己的节奏", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                DifficultyChip("全部", null, state.selectedDifficulty, viewModel::selectDifficulty)
                DifficultyChip("简单", 1, state.selectedDifficulty, viewModel::selectDifficulty)
                DifficultyChip("中等", 2, state.selectedDifficulty, viewModel::selectDifficulty)
                DifficultyChip("困难", 3, state.selectedDifficulty, viewModel::selectDifficulty)
            }
            Text("题库分类", Modifier.padding(top = 24.dp, bottom = 10.dp), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = state.selectedCategory == null, onClick = { viewModel.selectCategory(null) }, label = { Text("全部") })
                state.categories.forEach { category ->
                    FilterChip(selected = state.selectedCategory == category, onClick = { viewModel.selectCategory(category) }, label = { Text(category) })
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 24.dp, bottom = 18.dp).background(MaterialTheme.colorScheme.secondaryContainer, RoundedCornerShape(6.dp)).padding(14.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Info, contentDescription = null, tint = MaterialTheme.colorScheme.onSecondaryContainer)
                Spacer(Modifier.width(10.dp))
                Text("答题增加学习积分，不增加可提现的钱包金币。", color = MaterialTheme.colorScheme.onSecondaryContainer, style = MaterialTheme.typography.bodyMedium)
            }
        }
        Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 2.dp) {
            Button(onClick = viewModel::startQuiz, enabled = !state.isBusy,
                modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 22.dp, vertical = 12.dp).height(56.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) {
                if (state.isBusy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Color.White)
                else Text("开始本局 · 10 题  →", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun StudyModeRow(number: String, title: String, subtitle: String, selected: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 20.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(number, Modifier.width(58.dp), style = MaterialTheme.typography.headlineMedium,
            color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(subtitle, Modifier.padding(top = 5.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Surface(shape = RoundedCornerShape(50), color = if (selected) MaterialTheme.colorScheme.primary else Color.Transparent,
            border = if (selected) null else BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), modifier = Modifier.size(22.dp)) {}
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun QuizScreen(state: UiState, viewModel: QuizViewModel) {
    val question = state.currentQuestion ?: return
    val haptic = LocalHapticFeedback.current
    val isLastQuestion = state.questionIndex == state.questions.lastIndex

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding()) {
        TopAppBar(
            title = { Text("成语练习", fontWeight = FontWeight.Bold) },
            navigationIcon = {
                IconButton(onClick = viewModel::goHome) {
                    Icon(Icons.Filled.Close, contentDescription = "退出答题")
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
        )
        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 22.dp),
            verticalArrangement = Arrangement.spacedBy(0.dp)
        ) {
            Row(Modifier.fillMaxWidth().padding(top = 18.dp, bottom = 16.dp), verticalAlignment = Alignment.Bottom) {
                Text((state.questionIndex + 1).toString().padStart(2, '0'), style = MaterialTheme.typography.displayLarge,
                    color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Medium)
                Text(" / ${state.questions.size}", Modifier.padding(start = 8.dp, bottom = 12.dp),
                    style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Text(if (question.mode == QuizMode.DEFINITION) "释义题" else "填空题",
                Modifier.padding(top = 22.dp, bottom = 20.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge)
            Text(question.prompt, style = MaterialTheme.typography.headlineSmall, lineHeight = 36.sp, fontWeight = FontWeight.Medium)
            HorizontalDivider(Modifier.padding(top = 24.dp), color = MaterialTheme.colorScheme.outlineVariant)
            LinearProgressIndicator(progress = { state.progress }, modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
                color = MaterialTheme.colorScheme.primary, trackColor = Color(0xFFE9DDCE))
            Text(
                if (state.answerSubmitted) "答案已记录" else "选出最恰当的一项。",
                Modifier.padding(top = 16.dp, bottom = 22.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            question.options.forEachIndexed { index, option ->
                AnswerOption(
                    index = index,
                    option = option,
                    question = question,
                    selectedAnswer = state.selectedAnswer,
                    submitted = state.answerSubmitted,
                    onClick = {
                        if (state.settings.hapticEnabled) {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        }
                        viewModel.selectAnswer(option)
                    }
                )
            }

            if (state.answerSubmitted) {
                AnswerFeedback(question = question, selectedAnswer = state.selectedAnswer)
            }
        }

        Surface(
            modifier = Modifier.fillMaxWidth(),
            tonalElevation = 0.dp,
            color = MaterialTheme.colorScheme.surface
        ) {
            Button(
                onClick = viewModel::nextQuestion,
                enabled = state.answerSubmitted,
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(horizontal = 22.dp, vertical = 12.dp)
                    .height(58.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
            ) {
                Text(if (isLastQuestion) "查看本局结果  →" else "下一题  →", fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(8.dp))
                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null)
            }
        }
    }
}

@Composable
private fun ResultScreen(state: UiState, viewModel: QuizViewModel) {
    val result = state.lastResult ?: return
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.weight(1f).statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
            AppTopBar(title = "本局结果", onBack = viewModel::goHome)
            Text("本局新增学习积分", Modifier.padding(top = 28.dp), style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(result.score.toString(), Modifier.padding(top = 12.dp), style = MaterialTheme.typography.displayLarge,
                color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
            Row(Modifier.padding(top = 12.dp, bottom = 28.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Star, contentDescription = null, tint = Color(0xFFB68A3A))
                Text(" 认真完成，就是新的积累", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("一点一滴，都算进步。", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Row(Modifier.fillMaxWidth().padding(vertical = 24.dp)) {
                ResultMetric("${result.correct}", "答对题数", Modifier.weight(1f))
                VerticalDivider(Modifier.height(66.dp), color = MaterialTheme.colorScheme.outlineVariant)
                ResultMetric("${result.total - result.correct}", "答错题数", Modifier.weight(1f))
                VerticalDivider(Modifier.height(66.dp), color = MaterialTheme.colorScheme.outlineVariant)
                ResultMetric("${result.accuracy}%", "正确率", Modifier.weight(1f))
            }
            Text("接下来，巩固一下", Modifier.padding(top = 8.dp, bottom = 8.dp), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            CatalogueEntry("01", "复习本局错题", "把不熟悉的成语再看一遍", viewModel::openMistakes)
            CatalogueEntry("02", "看看学习统计", "记录这一周的进步", viewModel::openStats)
            Row(Modifier.fillMaxWidth().padding(vertical = 18.dp).background(MaterialTheme.colorScheme.secondaryContainer, RoundedCornerShape(6.dp)).padding(14.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Info, null, tint = MaterialTheme.colorScheme.onSecondaryContainer)
                Text("  本局增加的是学习积分，不会改变钱包金币余额。", color = MaterialTheme.colorScheme.onSecondaryContainer)
            }
        }
        Surface(color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.navigationBarsPadding().padding(horizontal = 22.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = viewModel::openModeSelection, modifier = Modifier.fillMaxWidth().height(56.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) { Text("再练一局  →", fontWeight = FontWeight.Bold) }
                OutlinedButton(onClick = viewModel::goHome, modifier = Modifier.fillMaxWidth().height(48.dp)) { Text("回到学习首页", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
}

@Composable
private fun InviteScreen(state: UiState, viewModel: QuizViewModel) {
    val context = LocalContext.current
    androidx.activity.compose.BackHandler(onBack = viewModel::openProfile)
    val isQualified = state.inviteLevel == 1 || state.inviteLevel == 3
    val level = when (state.inviteLevel) { 1 -> "团长"; 3 -> "代理"; else -> "普通会员" }
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
        TopAppBar(title = { Text("我的邀请码", fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = viewModel::openProfile) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") } },
            actions = { TextButton(onClick = { viewModel.openMemberSection(MemberSection.COMMISSIONS) }) { Text("邀请收益", color = MaterialTheme.colorScheme.primary) } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background))
        Text("邀请好友", Modifier.padding(top = 18.dp), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text(if (isQualified) "你的邀请码可用于本应用的新用户注册。" else "普通会员邀请码不能用于强制注册，新用户需使用团长或代理的邀请码。", Modifier.padding(top = 10.dp, bottom = 36.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        HorizontalDivider(color = MaterialTheme.colorScheme.primary, thickness = 2.dp)
        Text("我的邀请码 · $level", Modifier.padding(top = 24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(state.inviteCode ?: if (state.inviteCodeLoading) "邀请码加载中" else "邀请码暂不可用", Modifier.padding(top = 24.dp, bottom = 14.dp),
            style = MaterialTheme.typography.displayMedium, color = MaterialTheme.colorScheme.primary, maxLines = 1, overflow = TextOverflow.Ellipsis)
        state.inviteCodeError?.let { error ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(error, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = viewModel::retryInviteCode, enabled = !state.inviteCodeLoading) { Text("重试") }
            }
        }
        Button(onClick = {
            state.inviteCode?.let { code ->
                val clipboard = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                clipboard.setPrimaryClip(android.content.ClipData.newPlainText("邀请码", code))
            }
        }, enabled = state.inviteCode != null, modifier = Modifier.fillMaxWidth().height(54.dp),
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) { Text("复制邀请码") }
        state.inviteUrl?.let { url ->
            val qr = remember(url) { runCatching { invitationQr(url).asImageBitmap() }.getOrNull() }
            Text("邀请链接", Modifier.padding(top = 22.dp), style = MaterialTheme.typography.titleMedium)
            Text(url, Modifier.padding(vertical = 12.dp), style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = {
                    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                    clipboard.setPrimaryClip(android.content.ClipData.newPlainText("邀请链接", url))
                    viewModel.showMessage("邀请链接已复制")
                }, modifier = Modifier.weight(1f)) { Text("复制链接") }
                OutlinedButton(onClick = {
                    runCatching {
                        context.startActivity(android.content.Intent.createChooser(
                            android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                                type = "text/plain"; putExtra(android.content.Intent.EXTRA_TEXT, "禾合，邀你一起积累：$url")
                            }, "分享邀请链接"))
                    }.onFailure { viewModel.showMessage("暂时无法分享，请复制链接") }
                }, modifier = Modifier.weight(1f)) { Text("分享链接") }
            }
            if (qr != null) Image(qr, contentDescription = "邀请二维码", modifier = Modifier
                .align(Alignment.CenterHorizontally).padding(top = 16.dp).size(220.dp))
            else Text("二维码生成失败，请复制邀请链接", color = MaterialTheme.colorScheme.error)
            Text("使用浏览器扫码，可下载应用或通过短信注册 / 登录。已安装用户可在邀请页打开 APP。",
                Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider(Modifier.padding(vertical = 24.dp), color = MaterialTheme.colorScheme.outlineVariant)
        if (isQualified) {
            Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.width(4.dp).height(92.dp).background(Color(0xFFDA6A68)))
                Column(Modifier.padding(start = 14.dp)) {
                    Text("可用于强制邀请码注册", style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                    Text("你是本应用的$level，账号有效时，此码可用于本应用的强制邀请码注册。",
                        Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 24.sp)
                }
            }
        } else {
            Text("普通会员码，不具备强制注册资格",
                style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
            Text("开启强制注册时，新用户需使用本应用有效团长或代理的邀请码。",
                Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 24.sp)
        }
        WalletDetailRow("当前身份", level)
        WalletDetailRow("用于强制注册", if (isQualified) "具备资格" else "不具备资格")
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun ResultMetric(value: String, label: String, modifier: Modifier) {
    Column(modifier.padding(horizontal = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(value, style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onSurface)
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MistakesScreen(state: UiState, viewModel: QuizViewModel) {
    var query by rememberSaveable { mutableStateOf("") }
    var showFavorites by rememberSaveable { mutableStateOf(false) }
    val source = if (showFavorites) state.idioms.filter { it.isFavorite } else state.mistakes
    val filtered = source.filter { it.word.contains(query.trim(), true) || it.explanation.contains(query.trim(), true) }
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding()) {
        AppTopBar(title = "学习资料", onBack = viewModel::goHome,
            action = if (showFavorites) null else viewModel::openStats)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(horizontal = 22.dp, vertical = 8.dp)) {
            item {
                Text("复习错题", Modifier.padding(top = 16.dp, bottom = 16.dp),
                    style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                OutlinedTextField(value = query, onValueChange = { query = it }, modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("搜索成语或释义") }, leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                    singleLine = true, shape = RoundedCornerShape(6.dp))
                Row(Modifier.fillMaxWidth().padding(top = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { showFavorites = false }) { Text("错题本", color = if (!showFavorites) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant) }
                    TextButton(onClick = { showFavorites = true }) { Text("收藏", color = if (showFavorites) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant) }
                    Spacer(Modifier.weight(1f))
                    if (!showFavorites && state.mistakes.isNotEmpty()) TextButton(onClick = viewModel::startMistakeReview) { Text("开始复习") }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Text("${source.size} 个成语 · ${if (showFavorites) "收藏" else "错题本"}", Modifier.padding(vertical = 14.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (filtered.isEmpty()) item {
                Text(if (source.isEmpty()) if (showFavorites) "还没有收藏" else "还没有错题" else "没有匹配的成语",
                    Modifier.fillMaxWidth().padding(vertical = 32.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            items(filtered, key = { it.id }) { idiom ->
                StudyMaterialRow(idiom, onClick = { viewModel.openDetail(idiom.id) },
                    onDelete = if (showFavorites) null else ({ viewModel.removeMistake(idiom.id) }))
            }
        }
    }
}

@Composable
private fun StudyMaterialRow(idiom: IdiomEntity, onClick: () -> Unit, onDelete: (() -> Unit)?) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 18.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(idiom.word, Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurface)
            onDelete?.let { IconButton(onClick = it) { Icon(Icons.Outlined.DeleteOutline, contentDescription = "移除错题", tint = MaterialTheme.colorScheme.onSurfaceVariant) } }
        }
        Text(idiom.pinyin, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        Text(idiom.explanation, Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun FavoritesScreen(state: UiState, viewModel: QuizViewModel) {
    val favorites = state.idioms.filter { it.isFavorite }
    androidx.activity.compose.BackHandler { viewModel.goHome() }
    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        AppTopBar(title = "我的收藏", onBack = viewModel::goHome)
        if (favorites.isEmpty()) {
            EmptyState(Modifier.fillMaxSize().padding(24.dp), Icons.Filled.Star,
                "还没有收藏", "在成语详情中点击星标收藏，清除学习记录不会删除收藏。")
        } else {
            LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(favorites, key = { it.id }) { idiom ->
                    Card(onClick = { viewModel.openDetail(idiom.id) }, modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Text(idiom.word, style = MaterialTheme.typography.titleLarge)
                            Text(idiom.pinyin, style = MaterialTheme.typography.bodySmall)
                            Text(idiom.explanation)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatsScreen(state: UiState, viewModel: QuizViewModel) {
    val stats = state.stats
    val accuracy = if (stats.totalAnswered == 0) 0 else {
        (stats.totalCorrect * 100f / stats.totalAnswered).roundToInt()
    }
    val counts = state.weeklyAnswerCounts.associate { it.studyDate to it.answerCount }
    val today = java.time.LocalDate.now()
    val start = today.minusDays(6)
    val days = (0..6).map { start.plusDays(it.toLong()) }
    val monthStart = today.withDayOfMonth(1)
    val monthLeadingDays = monthStart.dayOfWeek.value - 1
    val monthWeekCount = (monthLeadingDays + today.lengthOfMonth() + 6) / 7
    val weeklyAnswered = days.sumOf { counts[it.toString()] ?: 0 }
    val maxCount = (days.maxOfOrNull { counts[it.toString()] ?: 0 } ?: 0).coerceAtLeast(1)
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding()
        .verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
        AppTopBar(title = "学习统计", onBack = viewModel::goHome)
        Text("学习概况", Modifier.padding(top = 18.dp, bottom = 24.dp),
            style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Row(Modifier.fillMaxWidth().padding(bottom = 34.dp)) {
            Column(Modifier.weight(1f)) {
                Text("累计答题", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(stats.totalAnswered.toString(), style = MaterialTheme.typography.displayLarge, color = MaterialTheme.colorScheme.primary)
                    Text(" 题", Modifier.padding(bottom = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text("本周已练 $weeklyAnswered 题", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            VerticalDivider(Modifier.height(120.dp).padding(horizontal = 10.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Column(Modifier.weight(1f).padding(start = 18.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
                Column {
                    Text("$accuracy%", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.onSurface)
                    Text("正确率", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column {
                    Text(stats.totalScore.toString(), style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onSurface)
                    Text("学习积分", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("最近一周", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("每日答题量", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth().height(190.dp).padding(top = 16.dp, bottom = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Bottom) {
            days.forEachIndexed { index, day ->
                val count = counts[day.toString()] ?: 0
                Column(Modifier.weight(1f).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Bottom) {
                    if (count > 0) Text(count.toString(), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                    Box(Modifier.fillMaxWidth().height((if (count == 0) 3 else (count * 120f / maxCount).roundToInt().coerceAtLeast(8)).dp)
                        .background(if (index == days.lastIndex) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(topStart = 5.dp, topEnd = 5.dp)))
                    Text(day.dayOfWeek.getDisplayName(java.time.format.TextStyle.SHORT, java.util.Locale.SIMPLIFIED_CHINESE),
                        Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        HorizontalDivider(Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth().padding(top = 24.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("${today.monthValue}月 · 学习足迹", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("连续 ${stats.studyStreakDays} 天", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
            listOf("一", "二", "三", "四", "五", "六", "日").forEach { weekday ->
                Text(weekday, Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center)
            }
        }
        repeat(monthWeekCount) { week ->
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                repeat(7) { weekday ->
                    val dayNumber = week * 7 + weekday - monthLeadingDays + 1
                    if (dayNumber in 1..today.lengthOfMonth()) {
                        val day = monthStart.withDayOfMonth(dayNumber)
                        val count = counts[day.toString()] ?: 0
                        val isToday = day == today
                        Box(Modifier.weight(1f).height(38.dp).background(
                            when { isToday -> MaterialTheme.colorScheme.primary; count > 0 -> MaterialTheme.colorScheme.primaryContainer; else -> Color.Transparent },
                            RoundedCornerShape(6.dp)), contentAlignment = Alignment.Center) {
                            Text(dayNumber.toString(), color = when {
                                isToday -> Color.White
                                count > 0 -> MaterialTheme.colorScheme.onPrimaryContainer
                                else -> MaterialTheme.colorScheme.onSurface
                            })
                        }
                    } else {
                        Spacer(Modifier.weight(1f).height(38.dp))
                    }
                }
            }
        }
        Spacer(Modifier.height(28.dp))
    }
}

@Composable
private fun ProfileMenuRow(icon: Int, title: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(
            modifier = Modifier.size(52.dp),
            shape = RoundedCornerShape(50),
            color = if (title == "更多金币") Color(0xFFFFE7AE) else Color(0xFFDCEBFF)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Image(
                    painter = painterResource(icon),
                    contentDescription = title,
                    modifier = Modifier.size(32.dp)
                )
            }
        }
        Spacer(Modifier.width(18.dp))
        Text(
            title,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.SemiBold
        )
        Icon(
            Icons.AutoMirrored.Filled.ArrowForward,
            contentDescription = "进入$title",
            tint = MaterialTheme.colorScheme.outlineVariant,
            modifier = Modifier.size(28.dp)
        )
    }
}

@Composable
private fun LoginScreen(state: UiState, viewModel: QuizViewModel) {
    var phone by rememberSaveable { mutableStateOf("") }
    var smsCode by remember { mutableStateOf("") }
    var registrationInvite by rememberSaveable(state.pendingInviteCode) { mutableStateOf(state.pendingInviteCode) }
    var consented by rememberSaveable { mutableStateOf(false) }
    val context = LocalContext.current
    androidx.activity.compose.BackHandler(onBack = viewModel::openProfile)
    LaunchedEffect(Unit) { if (state.registrationPolicy == null) viewModel.loadRegistrationPolicy() }
    state.authError?.let { error ->
        AlertDialog(
            onDismissRequest = viewModel::clearAuthError,
            title = { Text("登录未完成") },
            text = { Text(if (error == "邀请码必须是6位英文或数字" && registrationInvite.isBlank())
                "首次登录需要填写本应用团长或代理提供的6位邀请码。请填写后重新点击微信登录。" else error) },
            confirmButton = {
                TextButton(onClick = viewModel::clearAuthError) { Text("知道了") }
            }
        )
    }
    Box(Modifier.fillMaxSize()) {
    Column(Modifier.fillMaxSize().background(androidx.compose.ui.graphics.Brush.verticalGradient(
        listOf(AppPalette.PrimarySoft, Color.White, AppPalette.Background))).statusBarsPadding()
        .verticalScroll(rememberScrollState()).padding(start = 24.dp, end = 24.dp, top = 56.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("你好，\n欢迎使用禾合", color = AppPalette.Primary,
            fontSize = 28.sp, fontWeight = FontWeight.Bold, lineHeight = 36.sp)
        Text("账号登录", color = AppPalette.Text, fontSize = 15.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp, bottom = 8.dp))
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
        ReferenceInput(phone, { phone = it.filter { char -> char in '0'..'9' }.take(11); viewModel.clearAuthError() },
            hint = "请输入手机号", prefix = "+86",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
        ReferenceInput(smsCode, { smsCode = it.filter { char -> char in '0'..'9' }.take(6); viewModel.clearAuthError() },
            hint = "短信验证码",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
        SmsSendButton(state, enabled = !state.authBusy && consented, onClick = { viewModel.sendSms(phone) })
        if (state.registrationPolicy?.requireRegistrationInvite == true) {
        ReferenceInput(registrationInvite,
            { registrationInvite = it.uppercase(Locale.ROOT).filter { char -> char in 'A'..'Z' || char in '0'..'9' }.take(6); viewModel.clearAuthError() },
            hint = if (state.registrationPolicy?.requireRegistrationInvite == true) "上级邀请码（新用户必填）" else "上级邀请码（选填）")
        Text("新用户邀请码适用于微信与短信两种方式；需使用本应用有效团长或代理的邀请码。已有账号登录无需填写。",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        state.authError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.registrationPolicyError?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
            TextButton(onClick = viewModel::loadRegistrationPolicy) { Text("重新加载") }
        }
        Button(onClick = { viewModel.loginWithSms(phone, smsCode, "", if (state.registrationPolicy?.requireRegistrationInvite == true) registrationInvite else "") },
            enabled = !state.authBusy && consented, modifier = Modifier.fillMaxWidth().height(50.dp)
                .clip(RoundedCornerShape(25.dp)).background(MobanButton),
            colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent)) {
            Text(if (state.authBusy) "正在验证…" else "验证码注册 / 登录", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = consented, onCheckedChange = { consented = it })
            Text("已阅读并同意《用户协议》和《隐私政策》", style = MaterialTheme.typography.bodySmall)
        }
        OutlinedButton(onClick = { viewModel.loginWithWeChat(context, if (state.registrationPolicy?.requireRegistrationInvite == true) registrationInvite else "") },
            enabled = !state.authBusy && consented, modifier = Modifier.fillMaxWidth().height(50.dp),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFF1AAD19))) {
            Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = null)
            Spacer(Modifier.width(8.dp)); Text(if (state.authBusy) "正在完成登录…" else "微信登录")
        }
        if (state.registrationPolicy?.requireRegistrationInvite == true) {
            Text("首次微信登录需填写上方6位邀请码；已有账号可直接登录。",
                style = MaterialTheme.typography.bodySmall, color = AppPalette.Primary)
        }
        }
        Spacer(Modifier.height(20.dp))
    }
    IconButton(onClick = viewModel::openProfile, modifier = Modifier.align(Alignment.TopStart).statusBarsPadding()) {
        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = AppPalette.Primary)
    }
    }
}

@Composable
private fun SettingsScreen(state: UiState, viewModel: QuizViewModel) {
    androidx.activity.compose.BackHandler(onBack = viewModel::openProfile)
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
        AppTopBar(title = "偏好与账户", onBack = viewModel::openProfile)
        Text("偏好设置", Modifier.padding(top = 18.dp, bottom = 28.dp), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("学习偏好", Modifier.padding(bottom = 8.dp), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        SettingRow(
            icon = if (state.settings.soundEnabled) {
                Icons.AutoMirrored.Outlined.VolumeUp
            } else {
                Icons.AutoMirrored.Outlined.VolumeOff
            },
            title = "声音提示",
            subtitle = "答题后播放正确或错误提示音",
            trailing = {
                Switch(
                    checked = state.settings.soundEnabled,
                    onCheckedChange = {
                        viewModel.updateSettings(state.settings.copy(soundEnabled = it))
                    }
                )
            }
        )
        SettingRow(
            icon = Icons.Outlined.Vibration,
            title = "触感反馈",
            subtitle = "选择答案时提供轻微震动",
            trailing = {
                Switch(
                    checked = state.settings.hapticEnabled,
                    onCheckedChange = {
                        viewModel.updateSettings(state.settings.copy(hapticEnabled = it))
                    }
                )
            }
        )
        HorizontalDivider(Modifier.padding(vertical = 18.dp), color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("账户", Modifier.padding(end = 18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge)
            Column(Modifier.weight(1f)) {
        CatalogueEntry("01", "会员资料", "个人信息与收款资料") { viewModel.openMemberSection(MemberSection.PROFILE) }
        CatalogueEntry("02", "修改密码", "更新账户登录密码") { viewModel.openMemberSection(MemberSection.PASSWORD) }
        CatalogueEntry("03", "支付宝收款信息", "钱包余额和提现账户") { viewModel.openWallet() }
            }
        }
        HorizontalDivider(Modifier.padding(vertical = 18.dp), color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("关于", Modifier.padding(end = 18.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge)
            Column(Modifier.weight(1f)) {
                Row(Modifier.fillMaxWidth().padding(vertical = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("当前版本", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(com.example.idiomquiz.BuildConfig.VERSION_NAME, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        OutlinedButton(onClick = viewModel::logout, modifier = Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp)) {
            Text("退出登录", color = MaterialTheme.colorScheme.primary)
        }
    }
}

@OptIn(androidx.compose.material.ExperimentalMaterialApi::class)
@Composable
private fun AdHistoryScreen(state: UiState, viewModel: QuizViewModel) {
    androidx.activity.compose.BackHandler(onBack = viewModel::openProfile)
    val listState = rememberLazyListState()
    val pullRefreshState = rememberPullRefreshState(
        refreshing = state.adHistoryRefreshing,
        onRefresh = viewModel::refreshAdHistory
    )
    LaunchedEffect(state.adHistoryRefreshing) {
        if (state.adHistoryRefreshing) listState.scrollToItem(0)
    }
    LaunchedEffect(listState, state.adHistoryPage, state.adHistoryHasMore,
        state.adHistoryRefreshing, state.adHistoryLoadingMore, state.adHistoryError) {
        snapshotFlow {
            val layout = listState.layoutInfo
            layout.totalItemsCount > 0 &&
                (layout.visibleItemsInfo.lastOrNull()?.index ?: -1) >= layout.totalItemsCount - 2
        }.distinctUntilChanged().collect { atEnd ->
            if (atEnd && state.adHistoryError == null) viewModel.loadMoreAdHistory()
        }
    }
    val balance = state.serverCoin ?: state.appBootstrap?.coin ?: java.math.BigDecimal.ZERO
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
        AppTopBar(title = "广告记录", onBack = viewModel::openProfile)
        Text("观看时间与所得金币", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Box(Modifier.fillMaxWidth().weight(1f).pullRefresh(pullRefreshState)) {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(bottom = 16.dp)
            ) {
                if (state.adHistory.isEmpty() && !state.adHistoryRefreshing && state.adHistoryError == null) {
                    item {
                        EmptyState(
                            modifier = Modifier.fillParentMaxSize(),
                            icon = Icons.Filled.ReceiptLong,
                            title = "暂无广告记录",
                            description = "观看激励广告后，时间与实际所得金币将显示在这里"
                        )
                    }
                }
                items(state.adHistory, key = { it.id }) { record ->
                    Card(modifier = Modifier.fillMaxWidth(), shape = CardShape) {
                        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(formatAdRecordTime(record.watchedAt.orEmpty()), Modifier.weight(1f),
                                style = MaterialTheme.typography.bodyMedium)
                            Text("${record.coinAdded.stripTrailingZeros().toPlainString()} 金币",
                                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
                item {
                    Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                        when {
                            state.adHistoryLoadingMore -> CircularProgressIndicator(Modifier.size(24.dp))
                            state.adHistoryError != null -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(state.adHistoryError, color = MaterialTheme.colorScheme.error)
                                TextButton(onClick = viewModel::retryAdHistory) { Text("点击重试") }
                            }
                            state.adHistory.isNotEmpty() && !state.adHistoryHasMore ->
                                Text("没有更多记录了", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            PullRefreshIndicator(
                refreshing = state.adHistoryRefreshing,
                state = pullRefreshState,
                modifier = Modifier.align(Alignment.TopCenter)
            )
        }
        }
    }
}

@Composable
private fun AdHistoryField(label: String, value: String, contentStatus: String) {
    val displayedValue = value.ifBlank {
        when (contentStatus) {
            "sdk_not_provided" -> "SDK 未提供"
            "not_collected" -> "未采集"
            "reported" -> "暂无此字段"
            else -> "未知"
        }
    }
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Text(label, Modifier.width(112.dp), style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(displayedValue, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall,
            color = if (value.isBlank()) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
private fun WalletScreen(state: UiState, viewModel: QuizViewModel) {
    androidx.activity.compose.BackHandler(onBack = viewModel::openProfile)
    val context = LocalContext.current
    val activity = context.findActivity()
    androidx.compose.runtime.DisposableEffect(viewModel) {
        onDispose { viewModel.cancelEntryAd() }
    }
    var showBindDialog by remember { mutableStateOf(false) }
    var selectedWithdrawalId by rememberSaveable { mutableStateOf<String?>(null) }
    val balance = state.serverCoin ?: state.appBootstrap?.coin ?: java.math.BigDecimal.ZERO
    val selectedWithdrawal = state.withdrawalOptions.firstOrNull { it.id == selectedWithdrawalId }
        ?: state.withdrawalOptions.firstOrNull()
    LaunchedEffect(state.withdrawalOptions, selectedWithdrawalId) {
        if (state.withdrawalOptions.none { it.id == selectedWithdrawalId }) {
            selectedWithdrawalId = state.withdrawalOptions.firstOrNull()?.id
        }
    }
    Column(Modifier.fillMaxSize().background(MobanGoldPage)) {
        Column(Modifier.weight(1f).statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp)) {
            ReferenceToolbar("提现", viewModel::openProfile, titleSize = 18) {
                IconButton(onClick = { viewModel.openMemberSection(MemberSection.COINS) }) { Icon(Icons.Filled.ReceiptLong, "金币记录") }
            }
            ReferencePanel(modifier = Modifier.padding(top = 10.dp), radius = 24.dp, padding = 18.dp) {
                Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                    Row {
                        Text(balance.stripTrailingZeros().toPlainString(), Modifier.alignByBaseline(), fontSize = 38.sp, lineHeight = 46.sp,
                            fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface, textAlign = TextAlign.Center)
                        Text("金币", Modifier.padding(start = 3.dp).alignByBaseline(), fontSize = 18.sp, lineHeight = 26.sp)
                    }
                    Text("当前余额", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("冻结 ${state.appBootstrap?.freezeCoin ?: 0L}", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp))
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                    TextButton(onClick = viewModel::openWallet, enabled = !state.isBusy) { Text("刷新余额") }
                    TextButton(onClick = { viewModel.openMemberSection(MemberSection.COINS) }) { Text("金币明细") }
                }
            }

            Column(Modifier.fillMaxWidth().padding(top = 18.dp, bottom = 18.dp)) {
            Text("提现金额", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("选择提现档位，所需金币以服务端配置为准", Modifier.padding(top = 4.dp, bottom = 10.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (state.withdrawalOptions.isEmpty()) {
                Text("暂无可用提现档位", Modifier.padding(vertical = 14.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                state.withdrawalOptions.chunked(2).forEach { rowOptions ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        rowOptions.forEach { option ->
                            val selected = selectedWithdrawal?.id == option.id
                            val affordable = balance >= option.coin
                            OutlinedButton(
                                onClick = { selectedWithdrawalId = option.id },
                                enabled = !state.isBusy && !state.adBusy,
                                modifier = Modifier.weight(1f).padding(bottom = 8.dp).heightIn(min = 82.dp),
                                border = BorderStroke(1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface
                                )
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text("¥${centsText(option.amountCents)}", fontWeight = FontWeight.Bold,
                                        color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface)
                                    Text("${option.coin.stripTrailingZeros().toPlainString()} 金币", style = MaterialTheme.typography.bodySmall,
                                        color = if (affordable) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error)
                                }
                            }
                        }
                        if (rowOptions.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
            }
            selectedWithdrawal?.takeIf { balance < it.coin }?.let {
                Text("当前金币不足此档位", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            selectedWithdrawal?.let { option ->
                Surface(
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                    color = MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(4.dp),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
                ) {
                    Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                        WalletDetailRow("提现至", if (state.alipayAccount?.bound == true) "支付宝 · ${state.alipayAccount.accountMasked.orEmpty()}" else "尚未绑定")
                        WalletDetailRow("本次冻结", "${option.coin.stripTrailingZeros().toPlainString()} 金币")
                        WalletDetailRow("提现金额", "¥${centsText(option.amountCents)}")
                        TextButton(onClick = { showBindDialog = true }, enabled = !state.isBusy) {
                            Text("核对收款账户 ↗", color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
            viewModel.pendingWithdrawalAmount()?.let { amount ->
                Button(onClick = { viewModel.createWithdrawal(amount) }, enabled = !state.isBusy, modifier = Modifier.fillMaxWidth()) {
                    Text("确认上次 ${amount / 100.0} 元提现结果")
                }
            }
            ReferencePanel(Modifier.padding(top = 14.dp), radius = 24.dp, padding = 12.dp) {
            Text("提现方式", fontSize = 16.sp, lineHeight = 24.sp, fontWeight = FontWeight.Bold)
            Row(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                Image(painterResource(R.drawable.moban_alipay), null, Modifier.size(24.dp))
                Text("支付宝", Modifier.weight(1f).padding(start = 8.dp), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                val account = state.alipayAccount
                Text(if (account?.bound == true) "已绑定" else "未绑定", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            val account = state.alipayAccount
            WalletDetailRow("提现至", if (account?.bound == true) "支付宝 · ${account.accountMasked.orEmpty()}" else "尚未绑定")
            WalletDetailRow("收款人", account?.realNameMasked ?: "待服务端校验")
            WalletDetailRow("服务状态", when {
                !state.paymentAvailable -> "暂不可用"
                account?.bound != true -> "请先绑定收款账号"
                account.identityVerified -> "已完成身份校验"
                else -> "待服务端校验"
            })
            OutlinedButton(onClick = { showBindDialog = true }, enabled = !state.isBusy, modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
                Text(if (account?.bound == true) "修改收款账户" else "绑定支付宝")
            }
            Text(
                "申请成功后会冻结对应金币；审核通过不代表已到账，请以支付渠道确认结果为准。",
                Modifier.fillMaxWidth().padding(top = 14.dp).background(AppPalette.PrimarySoft, RoundedCornerShape(5.dp)).padding(14.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium
            )
            if (!state.paymentAvailable) {
                Text(
                    "提现服务暂不可用，当前不能提交申请。请稍后重试。",
                    Modifier.fillMaxWidth().padding(top = 10.dp).background(Color(0xFFFFE8E4), RoundedCornerShape(5.dp)).padding(14.dp),
                    color = Color(0xFF9D504A), style = MaterialTheme.typography.bodyMedium
                )
            }

            }
            Text("提现记录", Modifier.padding(top = 18.dp), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            if (state.withdrawals.isEmpty()) {
                Text("暂无提现记录", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 14.dp))
            } else {
                state.withdrawals.forEach { record ->
                    Column(Modifier.fillMaxWidth().padding(vertical = 14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("¥${centsText(record.amountCents)}", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                            Text(record.statusLabel, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(formatAdRecordTime(record.createdAt), Modifier.padding(top = 5.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                        HorizontalDivider(Modifier.padding(top = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
        }
        }
        Surface(color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.navigationBarsPadding().padding(horizontal = 22.dp, vertical = 12.dp)) {
                if (!state.paymentAvailable) Text("提现服务暂不可用", Modifier.padding(bottom = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                else if (state.alipayAccount?.bound != true) Text("请先绑定支付宝收款账号", Modifier.padding(bottom = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(onClick = {
                    selectedWithdrawal?.let { option ->
                        viewModel.enterWithInterstitial(activity) { viewModel.createWithdrawal(option.amountCents) }
                    }
                },
                    enabled = !state.isBusy && !state.adBusy && state.paymentAvailable && state.alipayAccount?.bound == true && selectedWithdrawal != null && balance >= (selectedWithdrawal?.coin ?: java.math.BigDecimal.ZERO),
                    modifier = Modifier.fillMaxWidth().height(56.dp), colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) {
                    Text(if (state.adBusy) "正在加载插屏…" else selectedWithdrawal?.let { "申请提现 ¥${centsText(it.amountCents)}" } ?: "暂无可用档位", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
    if (showBindDialog) {
        BindAlipayDialog(
            needsPassword = state.onboarding?.optBoolean("system_password_required") == true,
            onDismiss = { showBindDialog = false },
            onSubmit = { account, realName, password ->
                showBindDialog = false
                viewModel.bindAlipay(account, realName, password)
            }
        )
    }
}

@Composable
private fun WalletDetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, color = MaterialTheme.colorScheme.onSurface, textAlign = TextAlign.End)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

private fun centsText(value: Long): String = java.math.BigDecimal.valueOf(value, 2).setScale(2).toPlainString()

@Composable
private fun BindAlipayDialog(
    needsPassword: Boolean,
    onDismiss: () -> Unit,
    onSubmit: (String, String, String) -> Unit
) {
    var account by remember { mutableStateOf("") }
    var realName by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("绑定支付宝") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(account, { account = it }, label = { Text("支付宝账号") }, singleLine = true)
                OutlinedTextField(realName, { realName = it }, label = { Text("真实姓名") }, singleLine = true)
                Text(if (needsPassword) "首次绑定时设置系统密码，需8–128位并包含字母和数字。这不是支付宝支付密码。" else "请输入已有系统密码验证绑定。")
                OutlinedTextField(password, { password = it }, label = { Text(if (needsPassword) "设置系统密码" else "当前系统密码") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
                if (needsPassword) OutlinedTextField(confirmation, { confirmation = it }, label = { Text("确认系统密码") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
        confirmButton = {
            TextButton(
                onClick = { onSubmit(account, realName, password) },
                enabled = account.isNotBlank() && realName.isNotBlank() && password.isNotBlank() &&
                    (!needsPassword || (password == confirmation && password.length in 8..128 && password.any { it in 'a'..'z' || it in 'A'..'Z' } && password.any { it in '0'..'9' }))
            ) { Text("保存") }
        }
    )
}

private val adRecordDateFormatter: DateTimeFormatter = DateTimeFormatter
    .ofPattern("yyyy-MM-dd HH:mm:ss", Locale.CHINA)
    .withZone(ZoneId.of("Asia/Shanghai"))

/** API timestamps are UTC ISO-8601 strings; render them in the user's configured China timezone. */
private fun formatAdRecordTime(value: String): String {
    val raw = value.trim()
    if (raw.isEmpty()) return "时间未知"

    val epochMillis = raw.toLongOrNull()?.let { timestamp ->
        if (kotlin.math.abs(timestamp) < 100_000_000_000L) timestamp * 1000L else timestamp
    }
    if (epochMillis != null) {
        return runCatching { adRecordDateFormatter.format(Instant.ofEpochMilli(epochMillis)) }
            .getOrDefault(raw)
    }

    return runCatching { adRecordDateFormatter.format(Instant.parse(raw)) }
        .recoverCatching {
            // Accept ISO strings with an explicit offset that Instant.parse may reject on older runtimes.
            java.time.OffsetDateTime.parse(raw).toInstant().let(adRecordDateFormatter::format)
        }
        .recoverCatching {
            // The API contract stores UTC. Treat a missing-offset ISO value as UTC before localizing it.
            LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC).let(adRecordDateFormatter::format)
        }
        .getOrDefault(raw)
}

@Composable
private fun AdDemoScreen(state: UiState, viewModel: QuizViewModel) {
    val unavailableMessage = viewModel.adUnavailableMessage()
    androidx.activity.compose.BackHandler(onBack = viewModel::openProfile)
    val context = LocalContext.current
    val activity = context.findActivity()
    val bootstrap = state.appBootstrap
    val bannerPlacement = bootstrap?.let(AnyThinkAdManager::bannerPlacement)
    val nativePlacement = bootstrap?.let(AnyThinkAdManager::nativePlacement)?.takeIf { it.adUnitId.isNotBlank() }
    val interstitialPlacement = bootstrap?.let(AnyThinkAdManager::interstitialPlacement)?.takeIf { it.adUnitId.isNotBlank() }
    val rewardedPlacement = bootstrap?.let(AnyThinkAdManager::rewardedPlacement)?.takeIf { it.adUnitId.isNotBlank() }
    var nativeView by remember { mutableStateOf<android.view.View?>(null) }
    var nativeError by remember { mutableStateOf<String?>(null) }
    var nativeRetry by remember { mutableStateOf(0) }
    var cooldownRemaining by remember { mutableStateOf(0L) }
    androidx.compose.runtime.DisposableEffect(viewModel) {
        onDispose { viewModel.cancelAdGroup() }
    }
    LaunchedEffect(rewardedPlacement?.adUnitId, cooldownRemaining, activity != null) {
        Log.d(
            "AdFlow",
            "Ad demo state: hasRewardedPlacement=${rewardedPlacement != null}, " +
                "rewardedAdUnit=${rewardedPlacement?.adUnitId}, hasActivity=${activity != null}, " +
                "cooldown=$cooldownRemaining, enabled=${rewardedPlacement != null && activity != null && cooldownRemaining <= 0L}"
        )
    }

    LaunchedEffect(cooldownRemaining) {
        if (cooldownRemaining > 0L) {
            delay(1_000)
            cooldownRemaining = (cooldownRemaining - 1L).coerceAtLeast(0L)
        }
    }
    LaunchedEffect(nativePlacement, state.adSdkReady, nativeRetry) {
        nativeView = null
        nativeError = null
        val placement = nativePlacement ?: return@LaunchedEffect
        if (!state.adSdkReady) return@LaunchedEffect
        val loaded = kotlinx.coroutines.withTimeoutOrNull(60_000L) {
            kotlinx.coroutines.suspendCancellableCoroutine<Boolean> { continuation ->
                fun complete(view: android.view.View?, error: String?) {
                    if (continuation.isActive) {
                        nativeView = view
                        nativeError = error
                        continuation.resumeWith(Result.success(true))
                    } else if (view is com.anythink.nativead.api.ATNativeAdView) {
                        com.example.idiomquiz.ads.NativeAdRenderer.destroy(view)
                    }
                }
                runCatching {
                    val cancelLoad = AnyThinkAdManager.loadNative(context, placement,
                        onFailure = { complete(null, it) }, onReady = { complete(it, null) })
                    continuation.invokeOnCancellation { cancelLoad() }
                }.onFailure { complete(null, "原生广告加载失败，请稍后重试") }
            }
        }
        if (loaded == null) nativeError = "原生广告加载超时，请重试"
    }
    androidx.compose.runtime.DisposableEffect(nativeView) {
        val loadedView = nativeView
        onDispose {
            if (loadedView is com.anythink.nativead.api.ATNativeAdView) {
                com.example.idiomquiz.ads.NativeAdRenderer.destroy(loadedView)
            }
        }
    }
    Column(
        modifier = Modifier.fillMaxSize().statusBarsPadding().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        AppTopBar(title = "广告奖励", onBack = viewModel::openProfile,
            actionLabel = "广告记录", action = viewModel::openAdHistory)
        if (bannerPlacement != null) {
            AndroidView(
                factory = { AnyThinkAdManager.createBannerView(it, bannerPlacement) },
                modifier = Modifier.fillMaxWidth().height(60.dp),
                update = {}
            )
        } else {
            Text(unavailableMessage, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.weight(1f))
        Button(
            onClick = {
                Log.d(
                    "AdFlow",
                    "Rewarded button clicked: hasPlacement=${rewardedPlacement != null}, " +
                        "hasActivity=${activity != null}, cooldown=$cooldownRemaining"
                )
                if (activity != null) rewardedPlacement?.let {
                    viewModel.showRewardedAd(activity, it) {
                        if (it.cooldownSeconds > 0L) {
                            cooldownRemaining = it.cooldownSeconds
                        }
                    }
                }
            },
            enabled = state.adSdkReady && !state.adBusy && rewardedPlacement != null && interstitialPlacement != null && activity != null && cooldownRemaining <= 0L,
            modifier = Modifier
                .fillMaxWidth()
                .height(60.dp)
        ) {
            Text(
                if (cooldownRemaining > 0L) "激励视频冷却中（" + cooldownRemaining + "秒）"
                else if (state.adBusy) "广告组展示中…"
                else if (rewardedPlacement == null || interstitialPlacement == null || !state.adSdkReady) unavailableMessage
                else "获取更多金币"
            )
        }
        Spacer(Modifier.weight(1f))
        if (nativeView != null) {
            androidx.compose.runtime.key(nativeView) {
            AndroidView(
                factory = { nativeView!! },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 96.dp)
                    .wrapContentHeight()
            )
            }
        } else {
            Text(when {
                nativePlacement == null || !state.adSdkReady || nativeError != null -> unavailableMessage
                else -> "原生广告加载中…"
            }, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (nativeError != null && state.adSdkReady && nativePlacement != null) {
                TextButton(onClick = { nativeRetry++ }) { Text("重试原生广告") }
            }
        }
        Spacer(Modifier.navigationBarsPadding())
    }
}


@Composable
private fun DetailScreen(state: UiState, viewModel: QuizViewModel) {
    val idiom = state.idioms.firstOrNull { it.id == state.detailId } ?: return
    val backAction = if (state.detailOrigin == AppScreen.FAVORITES) {
        viewModel::openFavorites
    } else if (state.detailOrigin == AppScreen.MISTAKES) {
        viewModel::openMistakes
    } else {
        viewModel::goHome
    }
    androidx.activity.compose.BackHandler(onBack = backAction)

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding()) {
        TopAppBar(title = { Text("成语释义", fontWeight = FontWeight.Bold) }, navigationIcon = {
            IconButton(onClick = backAction) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
        }, colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background))
        Row(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 22.dp, vertical = 24.dp)) {
            Text(idiom.word.toList().joinToString("\n"), Modifier.width(74.dp), style = MaterialTheme.typography.headlineLarge,
                lineHeight = 54.sp, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Medium)
            VerticalDivider(Modifier.fillMaxHeight().padding(horizontal = 12.dp), color = MaterialTheme.colorScheme.outlineVariant)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(0.dp)) {
                Text(idiom.pinyin, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.titleMedium)
                Text(idiom.category + " · " + difficultyText(idiom.difficulty), Modifier.padding(top = 8.dp, bottom = 18.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                EditorialSection("释义", idiom.explanation)
                EditorialSection("出处", idiom.origin)
                EditorialSection("这样用一用", idiom.example)
                EditorialSection("近义词", idiom.synonyms)
                EditorialSection("反义词", idiom.antonyms)
            }
        }
        Surface(color = MaterialTheme.colorScheme.surface) {
            Button(onClick = { viewModel.toggleFavorite(idiom.id) }, modifier = Modifier.fillMaxWidth()
                .navigationBarsPadding().padding(horizontal = 22.dp, vertical = 12.dp).height(58.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)) {
                Icon(if (idiom.isFavorite) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (idiom.isFavorite) "取消收藏" else "收藏这个成语", fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun EditorialSection(title: String, text: String) {
    Column(Modifier.fillMaxWidth().padding(bottom = 14.dp)) {
        Text(title, color = Color(0xFFAD7552), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(text.ifBlank { "暂无内容" }, Modifier.padding(top = 8.dp, bottom = 10.dp),
            color = MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.bodyLarge, lineHeight = 28.sp)
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun AnswerOption(
    index: Int,
    option: String,
    question: com.example.idiomquiz.data.QuizQuestion,
    selectedAnswer: String?,
    submitted: Boolean,
    onClick: () -> Unit
) {
    val isCorrect = submitted && option == question.answer
    val isSelectedWrong = submitted && selectedAnswer == option && option != question.answer
    val isSelected = selectedAnswer == option
    Column(Modifier.fillMaxWidth().clickable(enabled = !submitted, onClick = onClick)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 70.dp)
                .background(when { isCorrect -> Color(0xFFE5EEDB); isSelectedWrong -> Color(0xFFF7E2DC); isSelected -> Color(0xFFFFF0E6); else -> Color.Transparent })
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(42.dp),
                shape = RoundedCornerShape(50),
                color = when {
                    isCorrect -> Color(0xFF648052)
                    isSelectedWrong -> MaterialTheme.colorScheme.primary
                    isSelected -> Color(0xFFEBCFB7)
                    else -> Color(0xFFF1E0CF)
                }
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(
                        ('A'.code + index).toChar().toString(),
                        fontWeight = FontWeight.Medium,
                        color = when {
                            isCorrect || isSelectedWrong -> Color.White
                            else -> Color(0xFF907661)
                        }
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Text(
                option,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = if (isCorrect || isSelectedWrong || isSelected) FontWeight.SemiBold else FontWeight.Normal
            )
            if (isCorrect) {
                Icon(
                    Icons.Filled.CheckCircle,
                    contentDescription = "正确答案",
                    tint = MaterialTheme.colorScheme.primary
                )
            } else if (isSelectedWrong) {
                Icon(
                    Icons.Outlined.ErrorOutline,
                    contentDescription = "错误答案",
                    tint = MaterialTheme.colorScheme.error
                )
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun AnswerFeedback(
    question: com.example.idiomquiz.data.QuizQuestion,
    selectedAnswer: String?
) {
    val correct = selectedAnswer == question.answer
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = CardShape,
        colors = CardDefaults.cardColors(
            containerColor = if (correct) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.errorContainer
            }
        )
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (correct) Icons.Filled.CheckCircle else Icons.Outlined.ErrorOutline,
                    contentDescription = null,
                    tint = if (correct) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    if (correct) "回答正确" else "再想一想",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            if (!correct) {
                Text(
                    "正确答案：${question.answerDisplay}",
                    fontWeight = FontWeight.SemiBold
                )
            }
            Text(question.idiom.explanation, style = MaterialTheme.typography.bodyMedium)
            Text(
                "例句：${question.idiom.example}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun ModeOption(
    selected: Boolean,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    description: String,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = CardShape,
        colors = CardDefaults.cardColors(
            containerColor = if (selected) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surface
            }
        ),
        border = BorderStroke(
            1.dp,
            if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant
        )
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                icon,
                contentDescription = null,
                modifier = Modifier.size(32.dp),
                tint = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(2.dp))
                Text(
                    description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            androidx.compose.material3.RadioButton(selected = selected, onClick = onClick)
        }
    }
}

@Composable
private fun DifficultyChip(
    label: String,
    value: Int?,
    selected: Int?,
    onSelect: (Int?) -> Unit
) {
    FilterChip(
        selected = value == selected,
        onClick = { onSelect(value) },
        label = { Text(label) }
    )
}

@Composable
private fun MistakeRow(idiom: IdiomEntity, onClick: () -> Unit, onDelete: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = CardShape,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    ) {
        Row(
            modifier = Modifier.padding(start = 16.dp, top = 14.dp, bottom = 14.dp, end = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        idiom.word,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        idiom.pinyin,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    idiom.explanation,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Outlined.DeleteOutline,
                    contentDescription = "移除错题",
                    tint = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
private fun DetailSection(
    title: String,
    text: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = CardShape,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(8.dp))
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
            Text(text, style = MaterialTheme.typography.bodyMedium, lineHeight = 24.sp)
        }
    }
}

@Composable
private fun TagSection(modifier: Modifier, title: String, text: String, tint: Color) {
    Card(
        modifier = modifier,
        shape = CardShape,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f))
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge, color = tint)
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun SettingRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    trailing: @Composable () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(24.dp)
        )
        Spacer(Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        trailing()
    }
}

@Composable
private fun SummaryStat(
    modifier: Modifier,
    value: String,
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    tint: Color,
    backgroundIconRes: Int? = null,
    onClick: (() -> Unit)? = null
) {
    Card(
        modifier = modifier
            .heightIn(min = 92.dp)
            .let { base -> if (onClick != null) base.clickable(onClick = onClick) else base },
        shape = CardShape,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Box(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            if (backgroundIconRes != null) {
                Image(
                    painter = painterResource(backgroundIconRes),
                    contentDescription = null,
                    alpha = 0.22f,
                    modifier = Modifier
                        .size(64.dp)
                        .align(Alignment.TopEnd)
                )
            } else {
                Icon(
                    icon,
                    contentDescription = null,
                    tint = tint.copy(alpha = 0.16f),
                    modifier = Modifier
                        .size(58.dp)
                        .align(Alignment.TopEnd)
                )
            }
            Column(
                modifier = Modifier.padding(top = 8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun QuickAction(
    modifier: Modifier,
    iconRes: Int,
    title: String,
    subtitle: String,
    tint: Color,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier
            .heightIn(min = 82.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(46.dp),
                shape = RoundedCornerShape(50),
                color = tint.copy(alpha = 0.16f)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Image(painter = painterResource(iconRes), contentDescription = title, modifier = Modifier.size(30.dp))
                }
            }
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Icon(
                Icons.AutoMirrored.Filled.ArrowForward,
                contentDescription = "进入$title",
                tint = MaterialTheme.colorScheme.outlineVariant,
                modifier = Modifier.size(24.dp)
            )
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.Bold
    )
}

@Composable
private fun AppTopBar(
    title: String,
    onBack: () -> Unit,
    actionLabel: String = "金币记录",
    lightContent: Boolean = false,
    action: (() -> Unit)? = null
) {
    androidx.compose.material3.CenterAlignedTopAppBar(
        title = { Text(title, style = MaterialTheme.typography.titleLarge) },
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
            }
        },
        actions = {
            if (action != null) {
                IconButton(onClick = action) {
                    Icon(Icons.Filled.ReceiptLong, contentDescription = actionLabel)
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = Color.Transparent,
            titleContentColor = if (lightContent) Color.White else MaterialTheme.colorScheme.onSurface,
            navigationIconContentColor = if (lightContent) Color.White else MaterialTheme.colorScheme.onSurface,
            actionIconContentColor = if (lightContent) Color.White else MaterialTheme.colorScheme.onSurface
        )
    )
}

@Composable
private fun EmptyState(
    modifier: Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    description: String
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(58.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        Spacer(Modifier.height(14.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(
            description,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun DetailSectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
}

private fun difficultyText(difficulty: Int): String = when (difficulty) {
    1 -> "简单"
    2 -> "中等"
    else -> "困难"
}
