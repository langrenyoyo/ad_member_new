@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.idiomquiz.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.util.Log
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.Image
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
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.ReceiptLong
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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DividerDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
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

    LaunchedEffect(state.appBootstrap, state.adSdkReady) {
        if (!SPLASH_AD_ENABLED) return@LaunchedEffect
        if (!state.adSdkReady) return@LaunchedEffect

        val activity = context.findActivity() ?: return@LaunchedEffect
        val bootstrap = state.appBootstrap ?: return@LaunchedEffect
        val placement = AnyThinkAdManager.splashPlacement(bootstrap) ?: return@LaunchedEffect
        AnyThinkAdManager.loadAndShowSplash(activity, placement)
    }

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    val hasBottomBar = state.screen in setOf(
        AppScreen.HOME,
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
                    AppScreen.MODE_SELECTION -> ModeSelectionScreen(state, viewModel)
                    AppScreen.QUIZ -> QuizScreen(state, viewModel)
                    AppScreen.RESULT -> ResultScreen(state, viewModel)
                    AppScreen.MISTAKES -> MistakesScreen(state, viewModel)
                    AppScreen.STATS -> StatsScreen(state, viewModel)
                    AppScreen.SETTINGS -> SettingsScreen(state, viewModel)
                    AppScreen.AD_DEMO -> AdDemoScreen(state, viewModel)
                    AppScreen.AD_HISTORY -> AdHistoryScreen(state, viewModel)
                    AppScreen.WALLET -> WalletScreen(state, viewModel)
                    AppScreen.DETAIL -> DetailScreen(state, viewModel)
                    AppScreen.PROFILE -> ProfileScreen(state, viewModel)
                    AppScreen.LOGIN -> LoginScreen(state, viewModel)
                }
            }
        }
    }
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
    NavigationBar {
        NavigationBarItem(
            selected = state.screen == AppScreen.HOME,
            onClick = viewModel::goHome,
            icon = {
                Image(
                    painter = painterResource(
                        if (state.screen == AppScreen.HOME) R.drawable.tabbar_home_sel
                        else R.drawable.tabbar_home_un
                    ),
                    contentDescription = "首页",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = { Text("首页") }
        )
        NavigationBarItem(
            selected = state.screen == AppScreen.PROFILE,
            onClick = viewModel::openProfile,
            icon = {
                Image(
                    painter = painterResource(
                        if (state.screen == AppScreen.PROFILE) R.drawable.tabbar_mine_sel
                        else R.drawable.tabbar_mine_un
                    ),
                    contentDescription = "我的",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = { Text("我的") }
        )
    }
}

@Composable
private fun HomeScreen(state: UiState, viewModel: QuizViewModel) {
    val stats = state.stats
    val accuracy = if (stats.totalAnswered == 0) 0 else {
        (stats.totalCorrect * 100f / stats.totalAnswered).roundToInt()
    }
    Box(Modifier.fillMaxSize().background(Color(0xFFF4EBDD))) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(
                    text = "鸭只易记",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "每天积累一点，表达更有力量",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            IconButton(onClick = viewModel::openProfile) {
                Icon(Icons.Filled.Person, contentDescription = "我的")
            }
        }

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(30.dp),
            colors = CardDefaults.cardColors(containerColor = Color.Transparent)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.linearGradient(listOf(Color(0xFFF36B78), Color(0xFFFFC477))),
                        RoundedCornerShape(30.dp)
                    )
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Top
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            "准备好挑战了吗？",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "10 道题，检验你的成语积累",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFFFF3EC)
                        )
                    }
                    Image(
                        painter = painterResource(R.drawable.a_shuben3),
                        contentDescription = "开始学习",
                        modifier = Modifier.size(80.dp)
                    )
                }
                Button(
                    onClick = viewModel::openModeSelection,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary
                    )
                ) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("开始答题")
                }
            }
        }

        SectionTitle("学习概览")
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = stats.totalAnswered.toString(),
                label = "累计答题",
                icon = Icons.Outlined.CheckCircleOutline,
                tint = MaterialTheme.colorScheme.primary,
                backgroundIconRes = R.drawable.icon_lightning
            )
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = "$accuracy%",
                label = "正确率",
                icon = Icons.Outlined.Insights,
                tint = MaterialTheme.colorScheme.tertiary,
                backgroundIconRes = R.drawable.icon_aims_full
            )
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = stats.studyStreakDays.toString(),
                label = "连续天数",
                icon = Icons.Outlined.CalendarMonth,
                tint = MaterialTheme.colorScheme.secondary,
                backgroundIconRes = R.drawable.icon_calendar
            )
        }

        SectionTitle("快速入口")
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            QuickAction(
                modifier = Modifier.fillMaxWidth(),
                iconRes = R.drawable.icon_shield,
                title = "错题本",
                subtitle = "${state.mistakeCount} 道待复习",
                tint = MaterialTheme.colorScheme.secondary,
                onClick = viewModel::openMistakes
            )
            QuickAction(
                modifier = Modifier.fillMaxWidth(),
                iconRes = R.drawable.icon_trophy,
                title = "学习统计",
                subtitle = "查看答题表现",
                tint = MaterialTheme.colorScheme.tertiary,
                onClick = viewModel::openStats
            )
        }

        Spacer(Modifier.height(8.dp))
        }
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

private fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> if (baseContext === this) null else baseContext.findActivity()
    else -> null
}

@Composable
private fun ModeSelectionScreen(state: UiState, viewModel: QuizViewModel) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        AppTopBar(title = "开始答题", onBack = viewModel::goHome)
        Text(
            "选择答题模式",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        ModeOption(
            selected = state.selectedMode == QuizMode.DEFINITION,
            icon = Icons.Outlined.Psychology,
            title = "释义选择题",
            description = "根据解释，从四个成语中选出正确答案",
            onClick = { viewModel.selectMode(QuizMode.DEFINITION) }
        )
        ModeOption(
            selected = state.selectedMode == QuizMode.FILL_BLANK,
            icon = Icons.Outlined.EditNote,
            title = "成语填空题",
            description = "根据提示补全成语，巩固字词记忆",
            onClick = { viewModel.selectMode(QuizMode.FILL_BLANK) }
        )

        SectionTitle("难度")
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            DifficultyChip("全部", null, state.selectedDifficulty, viewModel::selectDifficulty)
            DifficultyChip("简单", 1, state.selectedDifficulty, viewModel::selectDifficulty)
            DifficultyChip("中等", 2, state.selectedDifficulty, viewModel::selectDifficulty)
            DifficultyChip("困难", 3, state.selectedDifficulty, viewModel::selectDifficulty)
        }

        SectionTitle("题库分类")
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FilterChip(
                selected = state.selectedCategory == null,
                onClick = { viewModel.selectCategory(null) },
                label = { Text("全部") }
            )
            state.categories.forEach { category ->
                FilterChip(
                    selected = state.selectedCategory == category,
                    onClick = { viewModel.selectCategory(category) },
                    label = { Text(category) }
                )
            }
        }

        Spacer(Modifier.height(4.dp))
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = CardShape,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
            )
        ) {
            Row(
                modifier = Modifier.padding(14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Filled.Info,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary
                )
                Spacer(Modifier.width(10.dp))
                Text(
                    "每局 10 题，答对基础分为 10/20/30 分，连续答对还有额外奖励。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Button(
            onClick = viewModel::startQuiz,
            enabled = !state.isBusy,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
        ) {
            if (state.isBusy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Icon(Icons.Filled.PlayArrow, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("开始本局")
            }
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun QuizScreen(state: UiState, viewModel: QuizViewModel) {
    val question = state.currentQuestion ?: return
    val haptic = LocalHapticFeedback.current
    val isLastQuestion = state.questionIndex == state.questions.lastIndex

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
    ) {
        TopAppBar(
            title = {
                Text(
                    "第 ${state.questionIndex + 1} / ${state.questions.size} 题",
                    style = MaterialTheme.typography.titleMedium
                )
            },
            navigationIcon = {
                IconButton(onClick = viewModel::goHome) {
                    Icon(Icons.Filled.Close, contentDescription = "退出答题")
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.background
            )
        )
        LinearProgressIndicator(
            progress = { state.progress },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp),
            color = MaterialTheme.colorScheme.primary,
            trackColor = MaterialTheme.colorScheme.surfaceVariant
        )

        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            AssistChip(
                onClick = {},
                label = {
                    Text(if (question.mode == QuizMode.DEFINITION) "释义题" else "填空题")
                },
                leadingIcon = {
                    Icon(Icons.AutoMirrored.Outlined.MenuBook, contentDescription = null, modifier = Modifier.size(18.dp))
                }
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = CardShape,
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
            ) {
                Text(
                    text = question.prompt,
                    modifier = Modifier.padding(20.dp),
                    style = MaterialTheme.typography.titleLarge,
                    lineHeight = 30.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }

            Text(
                "请选择一个答案",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant
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
            tonalElevation = 2.dp,
            color = MaterialTheme.colorScheme.surface
        ) {
            Button(
                onClick = viewModel::nextQuestion,
                enabled = state.answerSubmitted,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 12.dp)
                    .height(50.dp)
            ) {
                Text(if (isLastQuestion) "查看结果" else "下一题")
                Spacer(Modifier.width(8.dp))
                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null)
            }
        }
    }
}

@Composable
private fun ResultScreen(state: UiState, viewModel: QuizViewModel) {
    val result = state.lastResult ?: return
    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        AppTopBar(title = "答题结果", onBack = viewModel::goHome)
        Spacer(Modifier.height(4.dp))
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = CardShape,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.primaryContainer
            )
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    if (result.accuracy >= 80) Icons.Filled.CheckCircle else Icons.Filled.Lightbulb,
                    contentDescription = null,
                    modifier = Modifier.size(54.dp),
                    tint = MaterialTheme.colorScheme.primary
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    when {
                        result.accuracy >= 90 -> "表现出色！"
                        result.accuracy >= 60 -> "继续保持！"
                        else -> "再复习一下吧"
                    },
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onPrimaryContainer
                )
                Spacer(Modifier.height(4.dp))
                Text("本局得分", color = MaterialTheme.colorScheme.onPrimaryContainer)
                Text(
                    result.score.toString(),
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = "${result.correct}",
                label = "答对",
                icon = Icons.Outlined.CheckCircleOutline,
                tint = MaterialTheme.colorScheme.primary
            )
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = "${result.total - result.correct}",
                label = "答错",
                icon = Icons.Outlined.ErrorOutline,
                tint = MaterialTheme.colorScheme.error
            )
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = "${result.durationSeconds}s",
                label = "用时",
                icon = Icons.Outlined.CalendarMonth,
                tint = MaterialTheme.colorScheme.tertiary
            )
        }

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = CardShape,
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("本局正确率", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${result.accuracy}%",
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                Spacer(Modifier.height(10.dp))
                LinearProgressIndicator(
                    progress = { result.accuracy / 100f },
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }

        Button(
            onClick = viewModel::openModeSelection,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp)
        ) {
            Icon(Icons.Filled.Refresh, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("再来一局")
        }
        OutlinedButton(
            onClick = viewModel::openMistakes,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp)
        ) {
            Icon(Icons.Outlined.ErrorOutline, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("查看错题本")
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun MistakesScreen(state: UiState, viewModel: QuizViewModel) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
    ) {
        AppTopBar(title = "错题本", onBack = viewModel::goHome)
        if (state.mistakes.isEmpty()) {
            EmptyState(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                icon = Icons.Filled.CheckCircle,
                title = "还没有错题",
                description = "完成几道题后，需要复习的内容会出现在这里。"
            )
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text(
                                "${state.mistakes.size} 道错题",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                "重新掌握它们，正确率会继续提升",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Button(
                            onClick = viewModel::startMistakeReview,
                            contentPadding = PaddingValues(horizontal = 12.dp)
                        ) {
                            Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("复习")
                        }
                    }
                }
                items(state.mistakes, key = { it.id }) { idiom ->
                    MistakeRow(
                        idiom = idiom,
                        onClick = { viewModel.openDetail(idiom.id) },
                        onDelete = { viewModel.removeMistake(idiom.id) }
                    )
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
    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        AppTopBar(title = "学习统计", onBack = viewModel::goHome)
        Text(
            "坚持记录，看到自己的进步",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = stats.totalAnswered.toString(),
                label = "累计答题",
                icon = Icons.Outlined.CheckCircleOutline,
                tint = MaterialTheme.colorScheme.primary
            )
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = "$accuracy%",
                label = "正确率",
                icon = Icons.Outlined.Insights,
                tint = MaterialTheme.colorScheme.tertiary
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = stats.totalScore.toString(),
                label = "累计积分",
                icon = Icons.Filled.Star,
                tint = MaterialTheme.colorScheme.secondary
            )
            SummaryStat(
                modifier = Modifier.weight(1f),
                value = stats.bestStreak.toString(),
                label = "最佳连对",
                icon = Icons.Outlined.Psychology,
                tint = MaterialTheme.colorScheme.primary
            )
        }

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = CardShape,
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
        ) {
            Column(modifier = Modifier.padding(18.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("答题正确率", style = MaterialTheme.typography.titleMedium)
                    Text("$accuracy%", fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(12.dp))
                LinearProgressIndicator(
                    progress = { accuracy / 100f },
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.tertiary
                )
                Spacer(Modifier.height(12.dp))
                Text(
                    when {
                        stats.totalAnswered == 0 -> "完成第一局答题后，这里会显示你的表现。"
                        accuracy >= 90 -> "稳定发挥，继续挑战更高难度的成语。"
                        accuracy >= 60 -> "基础不错，多复习错题可以进一步提升。"
                        else -> "先从简单题开始，逐步建立成语语感。"
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        SectionTitle("学习记录")
        SettingRow(
            icon = Icons.Outlined.CalendarMonth,
            title = "连续学习",
            subtitle = "已经连续学习 ${stats.studyStreakDays} 天",
            trailing = {
                Text(
                    "${stats.studyStreakDays} 天",
                    color = MaterialTheme.colorScheme.secondary,
                    fontWeight = FontWeight.Bold
                )
            }
        )
        SettingRow(
            icon = Icons.Filled.Star,
            title = "最高连对",
            subtitle = "一次答题中连续答对的最高记录",
            trailing = {
                Text(
                    "${stats.bestStreak} 题",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold
                )
            }
        )
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun ProfileScreen(state: UiState, viewModel: QuizViewModel) {
    var showClearDialog by remember { mutableStateOf(false) }
    val user = state.currentUser
    val coinBalance = state.serverCoin ?: state.appBootstrap?.coin ?: 0L

    Box(Modifier.fillMaxSize().background(Color(0xFFF4EBDD))) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
        TopAppBar(
            title = { Text("我的") },
            actions = {
                if (user != null) {
                    TextButton(onClick = viewModel::logout) {
                        Text("退出登录", color = Color(0xFF9B5E4D))
                    }
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = Color.Transparent
            )
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(30.dp),
            colors = CardDefaults.cardColors(containerColor = Color.Transparent)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.linearGradient(listOf(Color(0xFFF36B78), Color(0xFFFFC477))),
                        RoundedCornerShape(30.dp)
                    )
                    .padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        modifier = Modifier.size(82.dp),
                        shape = RoundedCornerShape(50),
                        color = Color(0xFFFFF7F1),
                        border = BorderStroke(5.dp, Color.White)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Image(
                                painter = painterResource(R.drawable.icon_avatar),
                                contentDescription = "头像",
                                modifier = Modifier.size(68.dp)
                            )
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(
                            user?.displayName ?: "鸭只易记",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            if (user == null) "登录后同步学习记录" else "ID: ${user.id}",
                            style = MaterialTheme.typography.bodyLarge,
                            color = Color(0xFFFFF3EC)
                        )
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "金币：$coinBalance",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    Spacer(Modifier.width(8.dp))
                    Image(
                        painter = painterResource(R.drawable.icon_gold_one),
                        contentDescription = "金币",
                        modifier = Modifier.size(100.dp)
                    )
                    Spacer(Modifier.weight(1f))
                    IconButton(
                        onClick = viewModel::openWallet,
                        modifier = Modifier.size(48.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Filled.AccountBalanceWallet,
                            contentDescription = "钱包",
                            tint = Color.White,
                            modifier = Modifier.size(28.dp)
                        )
                    }
                    if (user == null) {
                        TextButton(onClick = viewModel::openLogin) {
                            Text("立即登录", color = Color.White)
                        }
                    }
                }
            }
        }

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(28.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFCF8))
        ) {
            Column(modifier = Modifier.padding(horizontal = 18.dp, vertical = 6.dp)) {
                ProfileMenuRow(
                    icon = R.drawable.icon_setting,
                    title = "偏好设置",
                    onClick = viewModel::openSettings
                )
                HorizontalDivider(color = Color(0xFFEDE5DE))
                ProfileMenuRow(
                    icon = R.drawable.icon_gold_pile,
                    title = "更多金币",
                    onClick = viewModel::openAdDemo
                )
            }
        }

        SectionTitle("数据管理")
        OutlinedButton(
            onClick = { showClearDialog = true },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = MaterialTheme.colorScheme.error
            )
        ) {
            Icon(Icons.Outlined.DeleteOutline, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("清除学习记录")
        }
        Text(
            "清除后会删除积分、答题统计和错题本，收藏与账号信息会保留。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
            Spacer(Modifier.height(16.dp))
        }
    }

    if (showClearDialog) {
        AlertDialog(
            onDismissRequest = { showClearDialog = false },
            title = { Text("清除学习记录？") },
            text = { Text("积分、答题统计和错题本都会被清空，此操作无法恢复。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.clearProgress()
                        showClearDialog = false
                    }
                ) {
                    Text("确认清除", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearDialog = false }) { Text("取消") }
            }
        )
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
            color = Color(0xFF76574F),
            fontWeight = FontWeight.SemiBold
        )
        Icon(
            Icons.AutoMirrored.Filled.ArrowForward,
            contentDescription = "进入$title",
            tint = Color(0xFFB7ADA8),
            modifier = Modifier.size(28.dp)
        )
    }
}

@Composable
private fun LoginScreen(state: UiState, viewModel: QuizViewModel) {
    var phone by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    val context = LocalContext.current
    val isRegister = state.authMode == AuthMode.REGISTER

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        AppTopBar(title = if (isRegister) "注册账号" else "登录", onBack = viewModel::openProfile)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                if (isRegister) "创建你的学习账号" else "欢迎回来",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold
            )
            Text(
                "手机号登录后可同步学习身份和账号状态",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(
                selected = !isRegister,
                onClick = { viewModel.switchAuthMode(AuthMode.LOGIN) },
                label = { Text("登录") }
            )
            FilterChip(
                selected = isRegister,
                onClick = { viewModel.switchAuthMode(AuthMode.REGISTER) },
                label = { Text("注册") }
            )
        }

        OutlinedTextField(
            value = phone,
            onValueChange = {
                phone = it.filter(Char::isDigit).take(11)
                viewModel.clearAuthError()
            },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("手机号") },
            placeholder = { Text("请输入 11 位手机号") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
        )
        OutlinedTextField(
            value = password,
            onValueChange = {
                password = it
                viewModel.clearAuthError()
            },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("密码") },
            placeholder = { Text("至少 8 位，包含字母和数字") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password)
        )

        state.authError?.let { error ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = CardShape,
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Outlined.ErrorOutline,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.error
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(error, color = MaterialTheme.colorScheme.onErrorContainer)
                }
            }
        }

        Button(
            onClick = { viewModel.loginWithPhone(phone, password) },
            enabled = !state.authBusy,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp)
        ) {
            if (state.authBusy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text(if (isRegister) "注册并登录" else "登录")
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            HorizontalDivider(modifier = Modifier.weight(1f))
            Text(
                "或",
                modifier = Modifier.padding(horizontal = 12.dp),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            HorizontalDivider(modifier = Modifier.weight(1f))
        }

        OutlinedButton(
            onClick = { viewModel.loginWithWeChat(context) },
            enabled = !state.authBusy,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = Color(0xFF1AAD19)
            )
        ) {
            Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("微信登录")
        }
        Text(
            "当前仅调起微信 SDK，授权 code 会显示在提示中，暂不提交后端。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(18.dp))
    }
}

@Composable
private fun SettingsScreen(state: UiState, viewModel: QuizViewModel) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        AppTopBar(title = "设置", onBack = viewModel::openProfile)
        SectionTitle("答题体验")
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

        SectionTitle("外观")
        SettingRow(
            icon = if (state.settings.darkMode) Icons.Outlined.DarkMode else Icons.Outlined.LightMode,
            title = "深色模式",
            subtitle = "切换应用的明暗主题",
            trailing = {
                Switch(
                    checked = state.settings.darkMode,
                    onCheckedChange = {
                        viewModel.updateSettings(state.settings.copy(darkMode = it))
                    }
                )
            }
        )

        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun AdHistoryScreen(state: UiState, viewModel: QuizViewModel) {
    val balance = state.serverCoin ?: state.appBootstrap?.coin ?: 0L
    Box(Modifier.fillMaxSize().background(Color(0xFFF4EBDD))) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
        AppTopBar(title = "金币记录", onBack = viewModel::openProfile)
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = CardShape,
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(18.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Image(
                        painter = painterResource(R.drawable.icon_gold_pile),
                        contentDescription = "金币余额",
                        modifier = Modifier.size(36.dp)
                    )
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text("金币余额", style = MaterialTheme.typography.bodyMedium)
                        Text(balance.toString(), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    }
                }
                Button(onClick = { viewModel.showMessage("提现功能暂未开放") }) {
                    Text("提现")
                }
            }
        }
        Text("金币记录", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        if (state.isBusy) {
            Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (state.adHistory.isEmpty()) {
            EmptyState(
                modifier = Modifier.fillMaxWidth().weight(1f),
                icon = Icons.Filled.ReceiptLong,
                title = "暂无金币记录",
                description = "完成激励视频后，记录会显示在这里"
            )
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(bottom = 16.dp)
            ) {
                items(state.adHistory, key = { it.id }) { record ->
                    Card(modifier = Modifier.fillMaxWidth(), shape = CardShape) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Image(
                                painter = painterResource(R.drawable.icon_calendar),
                                contentDescription = "金币记录日期",
                                modifier = Modifier.size(28.dp)
                            )
                            Spacer(Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    when (record.placement) {
                                        "rewarded" -> "激励视频"
                                        else -> record.placement.ifBlank { record.adType }
                                    },
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    record.status + " · " + formatAdRecordTime(record.createdAt),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                            Text(
                                if (record.coinAdded > 0) "+" + record.coinAdded else "0",
                                color = if (record.coinAdded > 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
        }
    }
}

@Composable
private fun WalletScreen(state: UiState, viewModel: QuizViewModel) {
    var showBindDialog by remember { mutableStateOf(false) }
    var showWithdrawDialog by remember { mutableStateOf(false) }
    val balance = state.serverCoin ?: state.appBootstrap?.coin ?: 0L
    Box(Modifier.fillMaxSize().background(Color(0xFFF4EBDD))) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            AppTopBar(title = "钱包", onBack = viewModel::openProfile)
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(28.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFFFFD4C9))
            ) {
                Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("可用金币", style = MaterialTheme.typography.bodyLarge)
                    Text(balance.toString(), style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
                    Text("冻结金币：${state.appBootstrap?.freezeCoin ?: 0L}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Button(
                        onClick = { showWithdrawDialog = true },
                        enabled = state.withdrawalOptions.isNotEmpty() && balance > 0L,
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("提现") }
                }
            }
            Card(modifier = Modifier.fillMaxWidth(), shape = CardShape) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("支付宝收款", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    val account = state.alipayAccount
                    if (account?.bound == true) {
                        Text(account.accountMasked ?: "已绑定账号")
                        Text(account.realNameMasked ?: "", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(if (account.identityVerified) "已完成身份校验" else "待服务端校验", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        Text("尚未绑定支付宝账号", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    OutlinedButton(onClick = { showBindDialog = true }, modifier = Modifier.fillMaxWidth()) {
                        Text(if (account?.bound == true) "修改绑定" else "绑定支付宝")
                    }
                }
            }
            Text("提现记录", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            if (state.withdrawals.isEmpty()) {
                Text("暂无提现记录", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                state.withdrawals.forEach { record ->
                    Card(modifier = Modifier.fillMaxWidth(), shape = CardShape) {
                        Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                            Column(Modifier.weight(1f)) {
                                Text("¥${record.amountCents / 100.0}", fontWeight = FontWeight.Bold)
                                Text(record.payoutState ?: record.state, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(formatAdRecordTime(record.createdAt), style = MaterialTheme.typography.bodySmall)
                            }
                            Text(if (record.payoutState == "succeeded") "已到账" else "处理中")
                        }
                    }
                }
            }
            Spacer(Modifier.height(20.dp))
        }
    }
    if (showBindDialog) {
        BindAlipayDialog(
            onDismiss = { showBindDialog = false },
            onSubmit = { account, realName, password ->
                showBindDialog = false
                viewModel.bindAlipay(account, realName, password)
            }
        )
    }
    if (showWithdrawDialog) {
        AlertDialog(
            onDismissRequest = { showWithdrawDialog = false },
            title = { Text("选择提现金额") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.withdrawalOptions.forEach { option ->
                        OutlinedButton(
                            onClick = {
                                showWithdrawDialog = false
                                viewModel.createWithdrawal(option.amountCents)
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text(option.title) }
                    }
                    if (state.withdrawalOptions.isEmpty()) Text("暂无可用提现档位")
                }
            },
            confirmButton = { TextButton(onClick = { showWithdrawDialog = false }) { Text("取消") } }
        )
    }
}

@Composable
private fun BindAlipayDialog(
    onDismiss: () -> Unit,
    onSubmit: (String, String, String) -> Unit
) {
    var account by remember { mutableStateOf("") }
    var realName by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("绑定支付宝") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(account, { account = it }, label = { Text("支付宝账号") }, singleLine = true)
                OutlinedTextField(realName, { realName = it }, label = { Text("真实姓名") }, singleLine = true)
                OutlinedTextField(password, { password = it }, label = { Text("当前登录密码") }, singleLine = true)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
        confirmButton = {
            TextButton(
                onClick = { onSubmit(account, realName, password) },
                enabled = account.isNotBlank() && realName.isNotBlank() && password.isNotBlank()
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
    val context = LocalContext.current
    val activity = context.findActivity()
    val bootstrap = state.appBootstrap
    val bannerPlacement = bootstrap?.let(AnyThinkAdManager::bannerPlacement)
    val nativePlacement = bootstrap?.let(AnyThinkAdManager::nativePlacement)
    val interstitialPlacement = bootstrap?.let(AnyThinkAdManager::interstitialPlacement)
    val rewardedPlacement = bootstrap?.let(AnyThinkAdManager::rewardedPlacement)
    var nativeView by remember { mutableStateOf<android.view.View?>(null) }
    var cooldownRemaining by remember { mutableStateOf(0L) }
    var cooldownPaused by remember { mutableStateOf(false) }
    var interstitialShownForCooldown by remember { mutableStateOf(false) }
    val cooldownTotal = rewardedPlacement?.cooldownSeconds ?: 0L
    LaunchedEffect(rewardedPlacement?.adUnitId, cooldownRemaining, activity != null) {
        Log.d(
            "AdFlow",
            "Ad demo state: hasRewardedPlacement=${rewardedPlacement != null}, " +
                "rewardedAdUnit=${rewardedPlacement?.adUnitId}, hasActivity=${activity != null}, " +
                "cooldown=$cooldownRemaining, enabled=${rewardedPlacement != null && activity != null && cooldownRemaining <= 0L}"
        )
    }

    LaunchedEffect(cooldownRemaining, cooldownPaused) {
        if (!cooldownPaused && cooldownRemaining > 0L) {
            delay(1_000)
            cooldownRemaining = (cooldownRemaining - 1L).coerceAtLeast(0L)
        }
    }
    LaunchedEffect(cooldownRemaining, cooldownTotal, interstitialShownForCooldown) {
        if (cooldownTotal <= 1L || cooldownRemaining <= 0L || interstitialShownForCooldown) return@LaunchedEffect
        if (cooldownRemaining <= cooldownTotal / 2L) {
            cooldownPaused = true
            interstitialShownForCooldown = true
            val shown = if (activity != null && interstitialPlacement != null) {
                AnyThinkAdManager.showInterstitial(activity, interstitialPlacement) {
                    cooldownPaused = false
                }
            } else false
            if (!shown) cooldownPaused = false
        }
    }
    LaunchedEffect(bootstrap) {
        if (bootstrap != null) {
            interstitialPlacement?.let { AnyThinkAdManager.loadInterstitial(context, it) }
            nativePlacement?.let { AnyThinkAdManager.loadNative(context, it) { nativeView = it } }
        }
    }
    Column(
        modifier = Modifier.fillMaxSize().statusBarsPadding().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        AppTopBar(title = "广告测试", onBack = viewModel::openProfile, action = viewModel::openAdHistory)
        if (bannerPlacement != null) {
            AndroidView(
                factory = { AnyThinkAdManager.createBannerView(it, bannerPlacement) },
                modifier = Modifier.fillMaxWidth().height(60.dp),
                update = {}
            )
        } else {
            Text("未配置横幅广告", color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                            cooldownPaused = false
                            interstitialShownForCooldown = false
                        }
                    }
                }
            },
            enabled = rewardedPlacement != null && activity != null && cooldownRemaining <= 0L,
            modifier = Modifier
                .fillMaxWidth()
                .height(60.dp)
        ) {
            Text(
                if (cooldownRemaining > 0L) "激励视频冷却中（" + cooldownRemaining + "秒）"
                else "获取更多金币"
            )
        }
        Spacer(Modifier.weight(1f))
        if (nativeView != null) {
            AndroidView(
                factory = { nativeView!! },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 96.dp)
                    .wrapContentHeight()
            )
        } else {
            Text("原生广告加载中…", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.navigationBarsPadding())
    }
}


@Composable
private fun DetailScreen(state: UiState, viewModel: QuizViewModel) {
    val idiom = state.idioms.firstOrNull { it.id == state.detailId } ?: return
    val backAction = if (state.mistakes.any { it.id == idiom.id }) {
        viewModel::openMistakes
    } else {
        viewModel::goHome
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
    ) {
        TopAppBar(
            title = { Text("成语详情") },
            navigationIcon = {
                IconButton(onClick = backAction) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                }
            },
            actions = {
                IconButton(onClick = { viewModel.toggleFavorite(idiom.id) }) {
                    Icon(
                        if (idiom.isFavorite) Icons.Filled.Favorite else Icons.Outlined.FavoriteBorder,
                        contentDescription = if (idiom.isFavorite) "取消收藏" else "收藏",
                        tint = if (idiom.isFavorite) {
                            MaterialTheme.colorScheme.error
                        } else {
                            MaterialTheme.colorScheme.onSurface
                        }
                    )
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = MaterialTheme.colorScheme.background
            )
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = CardShape,
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Top
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                idiom.word,
                                style = MaterialTheme.typography.displaySmall,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                idiom.pinyin,
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        }
                        AssistChip(
                            onClick = {},
                            label = { Text(difficultyText(idiom.difficulty)) }
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(
                        idiom.category,
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
            DetailSection("释义", idiom.explanation, Icons.Filled.Info)
            DetailSection("出处", idiom.origin, Icons.AutoMirrored.Outlined.MenuBook)
            DetailSection("例句", idiom.example, Icons.Outlined.FormatQuote)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                TagSection(
                    modifier = Modifier.weight(1f),
                    title = "近义词",
                    text = idiom.synonyms,
                    tint = MaterialTheme.colorScheme.primary
                )
                TagSection(
                    modifier = Modifier.weight(1f),
                    title = "反义词",
                    text = idiom.antonyms,
                    tint = MaterialTheme.colorScheme.secondary
                )
            }
            Spacer(Modifier.height(16.dp))
        }
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
    val borderColor = when {
        isCorrect -> MaterialTheme.colorScheme.primary
        isSelectedWrong -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.outlineVariant
    }
    val backgroundColor = when {
        isCorrect -> MaterialTheme.colorScheme.primaryContainer
        isSelectedWrong -> MaterialTheme.colorScheme.errorContainer
        else -> MaterialTheme.colorScheme.surface
    }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .clip(CardShape)
            .clickable(enabled = !submitted, onClick = onClick),
        shape = CardShape,
        colors = CardDefaults.cardColors(containerColor = backgroundColor),
        border = BorderStroke(1.dp, borderColor)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(30.dp),
                shape = RoundedCornerShape(50),
                color = when {
                    isCorrect -> MaterialTheme.colorScheme.primary
                    isSelectedWrong -> MaterialTheme.colorScheme.error
                    else -> MaterialTheme.colorScheme.surfaceVariant
                }
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(
                        ('A'.code + index).toChar().toString(),
                        fontWeight = FontWeight.Bold,
                        color = when {
                            isCorrect -> MaterialTheme.colorScheme.onPrimary
                            isSelectedWrong -> MaterialTheme.colorScheme.onError
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        }
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Text(
                option,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = if (isCorrect || isSelectedWrong) FontWeight.Bold else FontWeight.Normal
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
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFCF8))
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
                tint = Color(0xFFB7ADA8),
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
private fun AppTopBar(title: String, onBack: () -> Unit, action: (() -> Unit)? = null) {
    TopAppBar(
        title = { Text(title) },
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
            }
        },
        actions = {
            if (action != null) {
                IconButton(onClick = action) {
                    Icon(Icons.Filled.ReceiptLong, contentDescription = "金币记录")
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = Color.Transparent
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
