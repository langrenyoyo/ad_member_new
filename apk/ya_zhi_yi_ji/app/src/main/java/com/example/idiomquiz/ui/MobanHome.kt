package com.example.idiomquiz.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.idiomquiz.R

/** Bundled shouye.html: orange header, 5-column shortcuts and 4 feature cards. */
@Composable
internal fun HomeScreen(state: UiState, viewModel: QuizViewModel) {
    Column(Modifier.fillMaxSize().background(AppPalette.Background).verticalScroll(rememberScrollState())) {
        Column(Modifier.fillMaxWidth().background(MobanHeader)
            .statusBarsPadding().padding(15.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("鸭只易记", color = AppPalette.Text, fontSize = 20.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold)
            Surface(Modifier.padding(top = 12.dp).fillMaxWidth().clickable(onClick = viewModel::openModeSelection), color = Color.White, shape = RoundedCornerShape(25.dp)) {
                Row(Modifier.padding(horizontal = 18.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("每日成语练习", Modifier.weight(1f), color = AppPalette.Muted, fontSize = 14.sp)
                    Text("开始学习", color = AppPalette.Primary, fontSize = 14.sp)
                }
            }
        }
        Text(state.onboarding?.optJSONObject("policy")?.optString("announcement")?.takeIf(String::isNotBlank) ?: "每日练习，温故知新",
            Modifier.fillMaxWidth().background(Color.White).clickable(onClick = viewModel::openNotice).padding(12.dp),
            fontSize = 12.sp, lineHeight = 18.sp, color = AppPalette.Primary, maxLines = 2)
        Surface(Modifier.padding(8.dp), shape = RoundedCornerShape(10.dp), color = Color.White, shadowElevation = 2.dp) {
            Column(Modifier.padding(15.dp)) {
                Row {
                    HomeService(R.drawable.a_shuben3, "开始练习", viewModel::openModeSelection)
                    HomeService(R.drawable.icon_book, "错题本", viewModel::openMistakes)
                    HomeService(R.drawable.icon_medal, "我的收藏", viewModel::openFavorites)
                    HomeService(R.drawable.moban_charts, "学习统计", viewModel::openStats)
                    HomeService(R.drawable.moban_privacy, "广告奖励", viewModel::openAdDemo)
                }
                Row {
                    HomeService(R.drawable.moban_bind, "金币钱包", viewModel::openWallet)
                    HomeService(R.drawable.icon_gold_pile, "补贴活动", viewModel::openBenefits)
                    HomeService(R.drawable.moban_crown, "邀请好友", viewModel::openInvite)
                    HomeService(R.drawable.moban_user_agreement, "广告记录", viewModel::openAdHistory)
                    HomeService(R.drawable.moban_service, "我的账户", viewModel::openProfile)
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            HomeOffer("成语练习", "每局 10 题", R.drawable.a_shuben3, AppPalette.PrimarySoft, viewModel::openModeSelection)
            HomeOffer("错题复习", "${state.mistakeCount} 道待复习", R.drawable.icon_book, AppPalette.PrimarySoft, viewModel::openMistakes)
            HomeOffer("广告奖励", "查看金币奖励", R.drawable.icon_gold_pile, AppPalette.PrimarySoft, viewModel::openAdDemo)
            HomeOffer("补贴活动", "查看参与条件", R.drawable.moban_crown, AppPalette.PrimarySoft, viewModel::openBenefits)
        }
        Surface(Modifier.padding(10.dp), shape = RoundedCornerShape(10.dp), color = Color.White) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("学习进度", fontSize = 16.sp, lineHeight = 24.sp, fontWeight = FontWeight.Bold, color = AppPalette.Primary)
                Row(Modifier.fillMaxWidth()) {
                    DashboardMetric("${state.stats.totalAnswered}", "累计答题", Modifier.weight(1f))
                    DashboardMetric(if (state.stats.totalAnswered == 0) "0%" else "${state.stats.totalCorrect * 100 / state.stats.totalAnswered}%", "正确率", Modifier.weight(1f))
                    DashboardMetric("${state.stats.studyStreakDays} 天", "连续学习", Modifier.weight(1f))
                }
            }
        }
        Surface(Modifier.padding(10.dp).fillMaxWidth(), shape = RoundedCornerShape(10.dp), color = Color.White) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("每日一词", color = AppPalette.Primary, fontSize = 12.sp)
                    Text("温故知新", fontSize = 20.sp, lineHeight = 28.sp, fontWeight = FontWeight.Bold)
                    Text("温习旧的知识，获得新的理解。", fontSize = 12.sp)
                }
                TextButton(onClick = { state.idioms.firstOrNull()?.let { viewModel.openDetail(it.id) } }, enabled = state.idioms.isNotEmpty()) { Text("查看") }
            }
        }
    }
}

@Composable private fun RowScope.HomeService(icon: Int, title: String, onClick: () -> Unit) {
    Column(Modifier.weight(1f).clickable(onClick = onClick).padding(vertical = 10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Image(painterResource(icon), null, Modifier.size((androidx.compose.ui.platform.LocalConfiguration.current.screenWidthDp * 0.10f).dp))
        Text(title, fontSize = 12.sp, lineHeight = 18.sp, color = AppPalette.Muted, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(top = 5.dp))
    }
}

@Composable private fun RowScope.HomeOffer(title: String, subtitle: String, icon: Int, color: Color, onClick: () -> Unit) {
    Column(Modifier.weight(1f).clip(RoundedCornerShape(8.dp)).background(color).clickable(onClick = onClick).padding(horizontal = 3.dp, vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(title, fontSize = 13.sp, lineHeight = 20.sp, fontWeight = FontWeight.Bold, color = AppPalette.Text)
        Image(painterResource(icon), null, Modifier.padding(vertical = 10.dp).size(42.dp))
        Text(subtitle, fontSize = 9.sp, lineHeight = 14.sp, textAlign = TextAlign.Center, color = AppPalette.Muted)
    }
}
