package com.example.idiomquiz.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.idiomquiz.R

// Shared orange/white presentation; screen structure and callbacks are unchanged.
internal val MobanHeader = Brush.horizontalGradient(listOf(AppPalette.PrimarySoft, AppPalette.Background))
internal val MobanPaper = AppPalette.Background
internal val MobanGoldPage = Brush.verticalGradient(listOf(AppPalette.PrimarySoft, Color.White, AppPalette.Background))
internal val MobanButton = Brush.horizontalGradient(listOf(AppPalette.Primary, AppPalette.Primary))

@Composable
internal fun ProfileScreen(state: UiState, viewModel: QuizViewModel) {
    val balance = state.serverCoin ?: state.appBootstrap?.coin
    val level = when (state.inviteLevel) { 1 -> "团长"; 3 -> "代理"; else -> "普通会员" }
    Column(Modifier.fillMaxSize().background(MobanPaper).verticalScroll(rememberScrollState())) {
        Box {
            Box(Modifier.fillMaxWidth().height(240.dp).background(MobanHeader))
            Column(Modifier.statusBarsPadding().heightIn(min = 568.dp), verticalArrangement = Arrangement.SpaceBetween) {
                Row(Modifier.padding(start = 20.dp, end = 20.dp, top = 28.dp, bottom = 24.dp), verticalAlignment = Alignment.CenterVertically) {
                    Image(painterResource(R.drawable.hehe_avatar), "头像", Modifier.size(70.dp).clickable {
                        if (state.currentUser == null) viewModel.openLogin() else viewModel.openMemberSection(MemberSection.PROFILE)
                    })
                    Column(Modifier.weight(1f).padding(start = 14.dp)) {
                        Text(state.currentUser?.displayName ?: "点击登录", color = AppPalette.Text, fontSize = 19.sp, lineHeight = 27.sp,
                            fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text("ID：${state.currentUser?.id ?: "—"}   $level", color = AppPalette.Text, fontSize = 11.sp, lineHeight = 16.sp,
                            modifier = Modifier.padding(top = 10.dp))
                    }
                }
                Surface(Modifier.padding(horizontal = 16.dp), shape = RoundedCornerShape(28.dp), color = Color.White, shadowElevation = 4.dp) {
                    Column(Modifier.padding(16.dp)) {
                        Box(Modifier.fillMaxWidth().height(56.dp)) {
                            Image(painterResource(R.drawable.hehe_balance_strip), null, Modifier.matchParentSize(), contentScale = ContentScale.FillBounds)
                            Row(Modifier.fillMaxSize().padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                                Image(painterResource(R.drawable.hehe_coins), null, Modifier.size(28.dp))
                                Text("余额", Modifier.weight(1f).padding(start = 10.dp), color = AppPalette.Text, fontSize = 15.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
                                Text(balance?.stripTrailingZeros()?.toPlainString() ?: "—", color = AppPalette.Text, fontSize = 17.sp, lineHeight = 24.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                        // Keep real learning data; the existing API has no monthly income summary.
                        Row(Modifier.fillMaxWidth().padding(top = 20.dp)) {
                            MobanMetric("${state.stats.totalScore}", "学习积分", Modifier.weight(1f), true)
                            MobanMetric("${state.stats.totalAnswered}", "累计答题", Modifier.weight(1f), true)
                        }
                        Row(Modifier.fillMaxWidth().padding(top = 20.dp).background(AppPalette.PrimarySoft, RoundedCornerShape(18.dp)).padding(vertical = 14.dp)) {
                            MobanMetric("${state.stats.totalCorrect}", "答对题数", Modifier.weight(1f))
                            VerticalDivider(Modifier.height(32.dp).align(Alignment.CenterVertically), color = AppPalette.Border)
                            MobanMetric("${state.stats.studyStreakDays}", "连续学习(天)", Modifier.weight(1f))
                            VerticalDivider(Modifier.height(32.dp).align(Alignment.CenterVertically), color = AppPalette.Border)
                            MobanMetric("${state.mistakeCount}", "待复习", Modifier.weight(1f))
                        }
                        Row(Modifier.fillMaxWidth().padding(top = 18.dp).height(154.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            MobanPictureTile(R.drawable.hehe_wallet_card, "提现中心", "可申请提现", AppPalette.Primary, Modifier.weight(1.08f).fillMaxHeight(), viewModel::openWallet)
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                MobanPictureTile(R.drawable.hehe_income_card, "收支明细", "查看收支流水", AppPalette.Primary, Modifier.weight(1f)) { viewModel.openMemberSection(MemberSection.COINS) }
                                MobanPictureTile(R.drawable.hehe_subsidy_card, "补贴入口", "申请补贴", AppPalette.Primary, Modifier.weight(1f)) { viewModel.openMemberSection(MemberSection.SUBSIDIES) }
                            }
                        }
                    }
                }
            }
        }
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(MobanHeader).clickable(onClick = viewModel::openInvite).heightIn(min = 54.dp).padding(start = 14.dp, end = 10.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Image(painterResource(R.drawable.hehe_invite), null, Modifier.size(24.dp))
                Column(Modifier.weight(1f).padding(horizontal = 8.dp)) {
                    Text("我的邀请码 · $level", color = AppPalette.Primary, fontSize = 12.sp)
                    Text(state.inviteCode ?: if (state.inviteCodeLoading) "加载中" else "查看邀请资格", color = AppPalette.Text, fontSize = 13.sp)
                }
                Text("查看邀请", color = AppPalette.Primary, fontSize = 12.sp, lineHeight = 18.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.background(Color(0xFFFFFFFF), RoundedCornerShape(24.dp)).padding(horizontal = 14.dp, vertical = 8.dp))
            }
            state.inviteCodeError?.let {
                Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                TextButton(onClick = viewModel::retryInviteCode, enabled = !state.inviteCodeLoading) { Text("重试邀请码") }
            }
            Text("相关服务", Modifier.padding(start = 4.dp), fontSize = 16.sp, lineHeight = 24.sp, fontWeight = FontWeight.Bold, color = AppPalette.Text)
            Surface(shape = RoundedCornerShape(22.dp), color = Color.White, border = androidx.compose.foundation.BorderStroke(1.dp, AppPalette.Border), shadowElevation = 2.dp) {
                Column(Modifier.padding(horizontal = 8.dp, vertical = 10.dp)) {
                    Row(Modifier.fillMaxWidth()) {
                        MobanService(R.drawable.moban_bind, "绑定支付宝", viewModel::openWallet)
                        MobanService(R.drawable.moban_charts, "邀请收益") { viewModel.openMemberSection(MemberSection.COMMISSIONS) }
                        MobanService(R.drawable.moban_modifypwd, "修改密码") { viewModel.openMemberSection(MemberSection.PASSWORD) }
                        MobanService(R.drawable.moban_service, "会员资料") { viewModel.openMemberSection(MemberSection.PROFILE) }
                    }
                    Row(Modifier.fillMaxWidth()) {
                        MobanService(R.drawable.moban_user_agreement, "广告记录", viewModel::openAdHistory)
                        MobanService(R.drawable.moban_privacy, "广告奖励", viewModel::openAdDemo)
                        MobanService(R.drawable.moban_settings, "设置", viewModel::openSettings)
                        MobanService(R.drawable.moban_charts, "我的收藏", viewModel::openFavorites)
                    }
                }
            }
            if (state.currentUser == null) Button(onClick = viewModel::openLogin, modifier = Modifier.fillMaxWidth()) { Text("微信 / 验证码登录") }
        }
    }
}

@Composable private fun MobanMetric(value: String, label: String, modifier: Modifier, large: Boolean = false) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, color = if (large) AppPalette.Primary else AppPalette.Text, fontSize = if (large) 28.sp else 21.sp, lineHeight = if (large) 36.sp else 29.sp, fontWeight = FontWeight.Bold)
        Text(label, color = AppPalette.Muted, fontSize = 11.sp, lineHeight = 16.sp, modifier = Modifier.padding(top = 6.dp))
    }
}

@Composable internal fun MobanPictureTile(image: Int, title: String, subtitle: String, color: Color, modifier: Modifier, onClick: () -> Unit) {
    val large = image == R.drawable.hehe_wallet_card
    Box(modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).clickable(onClick = onClick)) {
        Image(painterResource(image), null, Modifier.matchParentSize(), contentScale = ContentScale.FillBounds)
        Column(Modifier.align(if (large) Alignment.TopStart else Alignment.CenterStart).padding(horizontal = if (large) 16.dp else 14.dp, vertical = if (large) 16.dp else 0.dp)) {
            Text(title, color = color, fontSize = if (large) 16.sp else 15.sp, lineHeight = 22.sp, fontWeight = FontWeight.Bold)
            Text(subtitle, color = color, fontSize = if (large) 11.sp else 10.sp, lineHeight = 16.sp, modifier = Modifier.padding(top = 4.dp))
        }
    }
}

@Composable private fun RowScope.MobanService(icon: Int, label: String, onClick: () -> Unit) {
    Column(Modifier.weight(1f).clickable(onClick = onClick).heightIn(min = 82.dp).padding(vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Image(painterResource(icon), null, Modifier.size(36.dp))
        Text(label, modifier = Modifier.fillMaxWidth().padding(top = 8.dp), fontSize = 12.sp, lineHeight = 18.sp, color = AppPalette.Text, textAlign = TextAlign.Center)
    }
}
