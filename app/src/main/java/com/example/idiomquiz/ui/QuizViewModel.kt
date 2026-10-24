package com.example.idiomquiz.ui

import android.app.Application
import android.app.Activity
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.idiomquiz.ads.AnyThinkAdManager
import com.example.idiomquiz.auth.WeChatLoginEvent
import com.example.idiomquiz.auth.WeChatLoginManager
import com.example.idiomquiz.data.AppBootstrap
import com.example.idiomquiz.data.AdPlacement
import com.example.idiomquiz.data.AppSettings
import com.example.idiomquiz.data.AuthRepository
import com.example.idiomquiz.data.AuthUser
import com.example.idiomquiz.data.UserApiException
import com.example.idiomquiz.data.QuizMode
import com.example.idiomquiz.data.QuizRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.CancellationException
import com.example.idiomquiz.data.decimal
import com.example.idiomquiz.data.quotaExhausted
import com.example.idiomquiz.security.AliyunDeviceRiskManager
import com.example.idiomquiz.security.SecurityGuard
import org.json.JSONObject
import java.util.UUID

class QuizViewModel(application: Application) : AndroidViewModel(application) {
    private val memberStore = androidx.lifecycle.ViewModelStore()
    private var memberOwner: String? = null
    internal fun memberCenterModel(userId: String?): MemberCenterViewModel {
        if (memberOwner != userId) { memberStore.clear(); memberOwner = userId }
        return ViewModelProvider(memberStore, ViewModelProvider.AndroidViewModelFactory.getInstance(getApplication()))
            .get("member-center", MemberCenterViewModel::class.java)
    }
    private val repository = QuizRepository(application)
    private val authRepository = AuthRepository(application)
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val initializationMutex = Mutex()
    private var wechatAttempt = 0L
    private var passwordAuthorization: Pair<String, String>? = null
    private var onboardingRefreshJob: kotlinx.coroutines.Job? = null

    init {
        viewModelScope.launch {
            WeChatLoginManager.events.collect { event ->
                try {
                    wechatAttempt++
                    when (event) {
                        is WeChatLoginEvent.Authorized -> {
                            val pending = passwordAuthorization
                            if (pending != null) {
                                passwordAuthorization = null
                                if (_uiState.value.currentUser?.id == pending.first) {
                                    sessionCatching { authRepository.memberRequest("POST", "auth/wechat-password",
                                        JSONObject().put("code", event.code).put("new_password", pending.second)) }
                                        .onSuccess { _uiState.update { it.copy(isBusy = false, message = "密码已设置，请使用新密码绑定支付宝") } }
                                        .onFailure { error -> _uiState.update { it.copy(isBusy = false, message = error.message) } }
                                }
                                return@collect
                            }

                            if (!_uiState.value.authBusy) return@collect
                            val result = authRepository.loginWithWeChatCode(event.code, registrationInvite)
                            _uiState.update { it.copy(authBusy = false, currentUser = result.user,
                                authError = result.error, screen = if (result.user != null) AppScreen.PROFILE else AppScreen.LOGIN) }
                            if (result.user != null) initializeApp()
                        }

                        is WeChatLoginEvent.Failed -> {
                            passwordAuthorization = null
                            _uiState.update { it.copy(isBusy = false, authBusy = false, authError = event.message, message = event.message) }
                        }
                    }
                } catch (error: CancellationException) {
                    if (!currentCoroutineContext().isActive) throw error
                }
            }
        }

        viewModelScope.launch {
            repository.initialize()
            refreshSummary(markInitialized = true)
            val restoredUser = authRepository.restoreSession()
            _uiState.update { it.copy(currentUser = restoredUser ?: authRepository.currentUser()) }
            if (restoredUser != null) initializeApp()
        }
    }

    fun goHome() {
        _uiState.update {
            it.copy(
                screen = AppScreen.HOME,
                message = null,
                detailId = null
            )
        }
        viewModelScope.launch { refreshSummary() }
    }

    fun sendSms(phone: String) {
        if (_uiState.value.authBusy || android.os.SystemClock.elapsedRealtime() < _uiState.value.smsRetryAt) return
        if (!Regex("1[3-9][0-9]{9}").matches(phone.trim())) {
            _uiState.update { it.copy(authError = "请输入有效的 11 位手机号") }; return
        }
        val epoch = authRepository.sessionEpoch()
        _uiState.update { it.copy(authBusy = true, authError = null) }
        viewModelScope.launch {
            sessionCatching { authRepository.sendSms(phone) }
                .onSuccess { challenge -> if (epoch == authRepository.sessionEpoch()) _uiState.update { it.copy(authBusy = false, smsChallenge = challenge,
                    smsPhone = phone.trim(), smsRetryAt = android.os.SystemClock.elapsedRealtime() + 60_000, message = "验证码已发送，5 分钟内有效") } }
                .onFailure { error -> if (epoch == authRepository.sessionEpoch()) _uiState.update { it.copy(authBusy = false, authError = error.message) } }
        }
    }

    fun loginWithSms(phone: String, code: String, password: String, inviteCode: String = "") {
        val snapshot = _uiState.value
        if (snapshot.authBusy) return
        if (!Regex("[0-9]{6}").matches(code.trim())) {
            _uiState.update { it.copy(authError = "请输入 6 位短信验证码") }; return
        }
        if (snapshot.smsPhone != phone.trim() || snapshot.smsChallenge == null) {
            _uiState.update { it.copy(authError = "请先为当前手机号获取验证码") }; return
        }
        _uiState.update { it.copy(authBusy = true, authError = null) }
        viewModelScope.launch {
            val result = authRepository.loginWithSms(phone, code, snapshot.smsChallenge, password, inviteCode)
            applyAuthResult(result.user, result.error)
            if (result.user != null) {
                _uiState.update { it.copy(smsChallenge = null) }
                initializeApp()
            }
        }
    }

    fun refreshOnboarding() {
        if (_uiState.value.currentUser == null || _uiState.value.onboardingBusy) return
        val epoch = authRepository.sessionEpoch()
        _uiState.update { it.copy(onboardingBusy = true) }
        onboardingRefreshJob = viewModelScope.launch {
            try {
                initializeApp()
            }
            catch (error: CancellationException) { throw error }
            catch (error: Exception) { recordOnboardingFailure(error) }
            finally { if (authRepository.sessionEpoch() == epoch) _uiState.update { it.copy(onboardingBusy = false) } }
        }
    }

    fun pauseOnboardingRefresh() {
        onboardingRefreshJob?.cancel()
    }

    private suspend fun loadOnboarding() {
        val epoch = authRepository.sessionEpoch()
        val data = authRepository.memberRequest("GET", "onboarding").getJSONObject("data")
        if (data.getJSONObject("policy").optBoolean("require_usage")) {
            data.put("usage_granted", com.example.idiomquiz.security.AppUsageCollector.granted(getApplication()))
            _uiState.update { it.copy(onboarding = data) }
            val report = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                com.example.idiomquiz.security.AppUsageCollector.collect(getApplication())
            }
            authRepository.checkSession(epoch)
            authRepository.memberRequest("POST", "usage", report)
            data.put("usage_granted", report.getBoolean("granted"))
        }
        _uiState.update { it.copy(onboarding = data, onboardingError = null, onboardingBlockCode = null, blockedUntil = null) }
    }

    private fun recordOnboardingFailure(error: Exception) {
        val apiError = error as? com.example.idiomquiz.data.UserApiException
        _uiState.update { it.copy(onboardingError = onboardingFailureMessage(apiError?.statusCode, error.message),
            onboardingBlockCode = onboardingFailureCode(apiError?.statusCode, apiError?.errorCode) ?: it.onboardingBlockCode,
            blockedUntil = apiError?.blockedUntil ?: it.blockedUntil) }
    }

    fun checkUsageOnResume() {
        val data = _uiState.value.onboarding ?: return
        if (data.optJSONObject("policy")?.optBoolean("require_usage") == true &&
            !com.example.idiomquiz.security.AppUsageCollector.granted(getApplication())) {
            val updated = JSONObject(data.toString()).put("usage_granted", false)
            _uiState.update { it.copy(onboarding = updated) }
        }
    }

    fun setPasswordWithSms(phone: String, code: String, password: String, confirmation: String) {
        val snapshot = _uiState.value
        if (snapshot.isBusy || snapshot.authBusy) return
        try { com.example.idiomquiz.data.validateNewPassword(password, confirmation) }
        catch (error: IllegalArgumentException) { _uiState.update { it.copy(message = error.message) }; return }
        if (snapshot.smsPhone != phone.trim() || snapshot.smsChallenge == null) {
            _uiState.update { it.copy(message = "请先获取当前账号手机号的验证码") }; return
        }
        val epoch = authRepository.sessionEpoch()
        _uiState.update { it.copy(isBusy = true, message = null) }
        viewModelScope.launch {
            try {
                authRepository.memberRequest("POST", "auth/sms/password", JSONObject()
                    .put("challenge_id", snapshot.smsChallenge).put("code", code.trim()).put("new_password", password))
                _uiState.update { it.copy(message = "密码已设置，请使用新密码绑定支付宝", smsChallenge = null) }
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) { _uiState.update { it.copy(message = error.message) } }
            finally { if (authRepository.sessionEpoch() == epoch) _uiState.update { it.copy(isBusy = false) } }
        }
    }

    private fun onboardingComplete(): Boolean {
        val data = _uiState.value.onboarding ?: return false
        val policy = data.getJSONObject("policy")
        return (!policy.optBoolean("require_invite") || data.optInt("parent_id") > 0) &&
            (!policy.optBoolean("require_alipay") || data.optBoolean("alipay_bound")) &&
            (!policy.optBoolean("require_usage") || data.optBoolean("usage_granted"))
    }

    fun bindInvite(code: String) {
        if (_uiState.value.onboardingBusy) return
        _uiState.update { it.copy(onboardingBusy = true, onboardingError = null) }
        viewModelScope.launch {
            try {
                authRepository.memberRequest("POST", "onboarding", JSONObject().put("invite_code", code.trim()))
                initializeApp()
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) { recordOnboardingFailure(error) }
            finally { _uiState.update { it.copy(onboardingBusy = false) } }
        }
    }

    fun openModeSelection() {
        _uiState.update { it.copy(screen = AppScreen.MODE_SELECTION, message = null) }
    }

    fun openMistakes() {
        viewModelScope.launch {
            val mistakes = repository.getMistakes()
            _uiState.update {
                it.copy(
                    screen = AppScreen.MISTAKES,
                    mistakes = mistakes,
                    mistakeCount = mistakes.size,
                    message = null
                )
            }
        }
    }

    fun openStats() {
        viewModelScope.launch {
            val stats = repository.getStats()
            _uiState.update { it.copy(screen = AppScreen.STATS, stats = stats, message = null) }
        }
    }

    fun openSettings() {
        _uiState.update { it.copy(screen = AppScreen.SETTINGS, message = null) }
    }

    fun openAdDemo() {
        _uiState.update { state ->
            if (state.currentUser == null) {
                return@update state.copy(
                    screen = AppScreen.LOGIN,
                    authMode = AuthMode.LOGIN,
                    authError = null,
                    message = null
                )
            }
            if (state.appBootstrap?.adsEnabled == true) {
                state.copy(screen = AppScreen.AD_DEMO, message = null)
            } else {
                state.copy(message = "广告功能当前未开启")
            }
        }
    }

    fun openAdHistory() {
        val state = _uiState.value
        if (state.currentUser == null) {
            openLogin()
            return
        }
        _uiState.update { it.copy(screen = AppScreen.AD_HISTORY, isBusy = true, message = null) }
        viewModelScope.launch {
            sessionCatching {
                authRepository.adHistory(
                    state.appBootstrap?.gameId ?: authRepository.serverGameId()
                    ?: error("服务端未返回游戏 ID")
                )
            }.onSuccess { records ->
                _uiState.update { it.copy(adHistory = records, isBusy = false) }
            }.onFailure { error ->
                if (error is CancellationException) throw error

                _uiState.update {
                    it.copy(isBusy = false, message = "广告记录加载失败：" + error.message)
                }
            }
        }
    }

    fun openWallet() {
        if (_uiState.value.isBusy) return
        if (_uiState.value.currentUser == null) {
            openLogin()
            return
        }
        _uiState.update { it.copy(screen = AppScreen.WALLET, isBusy = true, message = null, paymentAvailable = false) }
        viewModelScope.launch {
            val gameId = _uiState.value.appBootstrap?.gameId ?: authRepository.serverGameId()
            if (gameId == null) {
                _uiState.update { it.copy(isBusy = false, message = "服务端未返回游戏 ID，请重新登录") }
                return@launch
            }
            val failures = mutableListOf<String>()
            sessionCatching { refreshWalletState() }
                .onFailure { failures += "余额：${it.message}" }
            sessionCatching { authRepository.alipayAccount() }
                .onSuccess { account -> _uiState.update { it.copy(alipayAccount = account) } }
                .onFailure { failures += "支付宝资料：${it.message}" }
            sessionCatching { authRepository.withdrawalOptions(gameId) }
                .onSuccess { options -> _uiState.update { it.copy(withdrawalOptions = options.options, paymentAvailable = options.paymentAvailable) } }
                .onFailure { failures += "提现档位：${it.message}" }
            sessionCatching { authRepository.withdrawals() }
                .onSuccess { withdrawals -> _uiState.update { it.copy(withdrawals = withdrawals) } }
                .onFailure { failures += "提现记录：${it.message}" }
            _uiState.update {
                it.copy(
                    isBusy = false,
                    message = failures.takeIf { errors -> errors.isNotEmpty() }
                        ?.joinToString("；", prefix = "钱包部分数据加载失败：")
                )
            }
        }
    }

    private suspend fun refreshWalletState() {
        val wallet = authRepository.refreshWallet()
        _uiState.update { it.copy(serverCoin = wallet.decimal("coin"),
            appBootstrap = it.appBootstrap?.copy(coin = wallet.decimal("coin"), freezeCoin = wallet.decimal("freeze_coin"))) }
    }

    fun setPasswordWithWeChat(context: android.content.Context, password: String, confirmation: String) {
        if (_uiState.value.isBusy || _uiState.value.authBusy) return
        val user = _uiState.value.currentUser ?: return
        try { com.example.idiomquiz.data.validateNewPassword(password, confirmation) }
        catch (error: IllegalArgumentException) {
            _uiState.update { it.copy(message = error.message) }
            return
        }
        passwordAuthorization = user.id to password
        val pending = passwordAuthorization
        _uiState.update { it.copy(isBusy = true, message = null) }
        val error = WeChatLoginManager.startLogin(context)
        if (error != null) {
            passwordAuthorization = null
            _uiState.update { it.copy(isBusy = false, message = error) }
        }
        viewModelScope.launch {
            delay(120_000)
            if (passwordAuthorization === pending) {
                passwordAuthorization = null
                WeChatLoginManager.cancelAuthorization()
                _uiState.update { it.copy(isBusy = false, message = "微信授权已超时，请重新发起") }
            }
        }
    }

    fun bindAlipay(account: String, realName: String, currentPassword: String) {
        if (_uiState.value.isBusy) return
        _uiState.update { it.copy(isBusy = true, message = null) }
        viewModelScope.launch {
            sessionCatching { authRepository.bindAlipay(account.trim(), realName.trim(), currentPassword) }
                .onSuccess { value -> _uiState.update { it.copy(alipayAccount = value, isBusy = false, message = "支付宝绑定成功") }; refreshOnboarding() }
                .onFailure { error ->
                if (error is CancellationException) throw error
 _uiState.update { it.copy(isBusy = false, message = "支付宝绑定失败：${error.message}") } }
        }
    }

    private val withdrawalPrefs = application.getSharedPreferences("idiom_quiz_withdrawals", 0)

    fun pendingWithdrawalAmount(): Long? {
        val user = _uiState.value.currentUser?.id ?: return null
        val game = authRepository.serverGameId() ?: return null
        val prefix = "$user:$game:"
        return withdrawalPrefs.getString(prefix + "key", null)?.let {
            withdrawalPrefs.getLong(prefix + "amount", -1).takeIf { it > 0 }
        }
    }

    fun createWithdrawal(amountCents: Long) {
        if (_uiState.value.isBusy) return
        if (pendingWithdrawalAmount() == null && (!_uiState.value.paymentAvailable || _uiState.value.alipayAccount?.bound != true)) {
            _uiState.update { it.copy(message = "请确认提现服务可用，并先绑定支付宝") }
            return
        }
        val userId = _uiState.value.currentUser?.id ?: return _uiState.update { it.copy(message = "请先登录") }
        val gameId = _uiState.value.appBootstrap?.gameId ?: authRepository.serverGameId()
            ?: return _uiState.update { it.copy(message = "服务端未返回游戏 ID") }
        val prefix = "$userId:$gameId:"
        val storedAmount = withdrawalPrefs.getLong(prefix + "amount", -1)
        val storedKey = withdrawalPrefs.getString(prefix + "key", null)
        if (storedKey != null && storedAmount != amountCents) {
            return _uiState.update { it.copy(message = "上次 ${storedAmount / 100.0} 元提现结果未确认，请选择相同金额重试确认") }
        }
        val requestKey = storedKey ?: UUID.randomUUID().toString()
        if (!withdrawalPrefs.edit().putLong(prefix + "amount", amountCents)
                .putString(prefix + "key", requestKey).commit()) {
            return _uiState.update { it.copy(message = "无法保存提现凭据，请稍后重试") }
        }
        _uiState.update { it.copy(isBusy = true, message = null) }
        viewModelScope.launch {
            sessionCatching {
                authRepository.createWithdrawal(gameId, amountCents, requestKey)
            }.onSuccess { record ->
                withdrawalPrefs.edit().remove(prefix + "amount").remove(prefix + "key").apply()
                _uiState.update { it.copy(withdrawals = listOf(record) + it.withdrawals, isBusy = false, message = "提现申请已提交") }
                sessionCatching { refreshWalletState() }
            }.onFailure { error ->
                if (error is CancellationException) throw error
                if (error is com.example.idiomquiz.data.UserApiException &&
                    (error.errorCode == "WITHDRAWAL_NOT_CREATED" || (storedKey == null && error.statusCode in listOf(400, 422)))) {
                    withdrawalPrefs.edit().remove(prefix + "amount").remove(prefix + "key").commit()
                }
                val message = if (pendingWithdrawalAmount() != null) {
                    "提现结果尚未确认，请点击确认上次提现结果：${error.message}"
                } else "提现申请失败：${error.message}"
                _uiState.update { it.copy(isBusy = false, message = message) }
            }
        }
    }

    fun showRewardedAd(activity: Activity, placement: AdPlacement, onClosed: () -> Unit = {}) {
        if (_uiState.value.adBusy) return
        _uiState.update { it.copy(adBusy = true, message = "正在加载广告") }
        val epoch = authRepository.sessionEpoch()
        viewModelScope.launch {
            try {
                val gameId = _uiState.value.appBootstrap?.gameId ?: authRepository.serverGameId()
                    ?: error("服务端未返回游戏 ID")
                val config = authRepository.deviceRiskConfig(gameId)
                val riskCheckId = if (config.enabled) {
                    if (!AliyunDeviceRiskManager.hasConsent(getApplication())) {
                        _uiState.update { it.copy(adBusy = false, showRiskConsent = true, message = null) }
                        return@launch
                    }
                    AliyunDeviceRiskManager.requireConfigured()
                    val challenge = authRepository.deviceRiskChallenge(gameId)
                    val token = AliyunDeviceRiskManager.getDeviceToken(getApplication(), challenge.bizId)
                    authRepository.checkSession(epoch)
                    val verification = authRepository.deviceRiskVerify(challenge.challengeId, token)
                    if (verification.quotaExhausted()) error("当前设备已达到今日广告次数限制")
                    verification.riskCheckId
                } else null
                authRepository.checkSession(epoch)
                val session = authRepository.requestAd(gameId, placement.placement, placement.adType, riskCheckId)
                    ?: error("请先登录后再请求广告")
                Log.d(AD_FLOW_TAG, "Ad session=${session.id}, request=${session.requestId}")
                var earned = false
                var shownAt = 0L
                AnyThinkAdManager.showRewarded(activity, session,
                    onMetadata = { event, payload ->
                        viewModelScope.launch {
                            try {
                                authRepository.checkSession(epoch)
                                authRepository.memberRequest("POST", "ads/${session.id}/metadata",
                                    payload.put("event", event).put("session_token", session.sessionToken))
                            } catch (e: CancellationException) { throw e }
                            catch (_: Exception) { /* Metadata is advisory and never gates settlement. */ }
                        }
                    },
                    onReward = reward@{ rewardEvidence ->
                        try { authRepository.checkSession(epoch) } catch (_: CancellationException) { return@reward }
                        earned = true
                        val seconds = if (shownAt == 0L) 0 else
                            ((android.os.SystemClock.elapsedRealtime() - shownAt) / 1000).coerceIn(0, 86400).toInt()
                        viewModelScope.launch {
                            try {
                                // The server uses the one-shot session reward as the
                                // immediate user-facing result.  The TAKU callback
                                // remains a later reconciliation signal.
                                val completion = sessionCatching {
                                    authRepository.adComplete(session, seconds, rewardEvidence)
                                }
                                completion.onSuccess { response ->
                                    val data = response.optJSONObject("data")
                                    if (data?.optBoolean("rewarded", false) == true) {
                                        val balance = data.optDouble("coin_balance", Double.NaN)
                                        if (!balance.isNaN()) {
                                            val coins = balance.toBigDecimal()
                                            _uiState.update { it.copy(serverCoin = coins,
                                                appBootstrap = it.appBootstrap?.copy(coin = coins), message = "奖励已到账") }
                                        } else {
                                            viewModelScope.launch {
                                                runCatching { refreshWalletState() }
                                                _uiState.update { it.copy(message = "奖励已到账") }
                                            }
                                        }
                                    } else if (data?.optString("status") == "queued") {
                                        _uiState.update { it.copy(message = "奖励正在补发，网络恢复后会自动到账") }
                                    } else {
                                        awaitRewardSettlement(session, gameId, epoch)
                                    }
                                }.onFailure { error ->
                                    if (error is CancellationException) throw error
                                    val unavailable = error is UserApiException && error.errorCode?.startsWith(
                                        "PUBLISHER_REVENUE_") == true
                                    _uiState.update { it.copy(message = if (unavailable)
                                        "广告平台未返回有效收益，本次未发放奖励"
                                    else "奖励正在补发，网络恢复后会自动到账") }
                                }
                            } catch (e: CancellationException) { throw e }
                            catch (e: Exception) {
                                _uiState.update { it.copy(message = "奖励正在补发，网络恢复后会自动到账") }
                            }
                        }
                    },
                    onClosed = closed@{
                        try { authRepository.checkSession(epoch) } catch (_: CancellationException) { return@closed }
                        _uiState.update { it.copy(adBusy = false) }
                        if (!earned) viewModelScope.launch {
                            reportAdFailure(session, "CLOSED_BEFORE_REWARD")
                        }
                        onClosed()
                    },
                    onShown = shown@{
                        try { authRepository.checkSession(epoch) } catch (_: CancellationException) { return@shown }
                        shownAt = android.os.SystemClock.elapsedRealtime()
                        viewModelScope.launch {
                            try { authRepository.adImpression(session) }
                            catch (e: CancellationException) { throw e }
                            catch (e: Exception) { Log.w(AD_FLOW_TAG, "Impression upload failed for ${session.id}") }
                        }
                    },
                    onFailure = failed@{ message ->
                        try { authRepository.checkSession(epoch) } catch (_: CancellationException) { return@failed }
                        _uiState.update { it.copy(adBusy = false, message = message) }
                        if (!earned) viewModelScope.launch { reportAdFailure(session, "SDK_FAILED") }
                    }
                )
            } catch (e: CancellationException) {
                _uiState.update { it.copy(adBusy = false) }
                throw e
            } catch (e: Exception) {
                _uiState.update { it.copy(adBusy = false, message = "广告请求失败：${e.message}") }
            }
        }
    }

    private suspend fun reportAdFailure(session: com.example.idiomquiz.data.AdSession, reason: String) {
        try { authRepository.adFail(session, reason) }
        catch (e: CancellationException) { throw e }
        catch (e: Exception) { Log.w(AD_FLOW_TAG, "Failure upload failed for ${session.id}") }
    }

    fun respondToRiskConsent(accepted: Boolean) {
        if (accepted) AliyunDeviceRiskManager.acceptConsent(getApplication())
        _uiState.update { it.copy(showRiskConsent = false,
            message = if (accepted) "已同意，请再次点击观看广告" else "未开启设备检测，仍可使用学习功能") }
    }

    private suspend fun awaitRewardSettlement(session: com.example.idiomquiz.data.AdSession, gameId: Int, epoch: Long) {
        _uiState.update { it.copy(message = "奖励确认中") }
        repeat(15) {
            authRepository.checkSession(epoch)
            val record = try { authRepository.adHistory(gameId).firstOrNull { it.id == session.id } }
                catch (e: CancellationException) { throw e }
                catch (e: java.io.IOException) { null }
            if (record?.status == "rewarded") {
                val balance = authRepository.walletBalance()
                _uiState.update { it.copy(serverCoin = balance, message = "奖励已到账") }
                return
            }
            delay(2000)
        }
        _uiState.update { it.copy(message = "奖励确认中，请稍后刷新钱包") }
    }

    fun openProfile() {
        _uiState.update { it.copy(screen = AppScreen.PROFILE, currentUser = authRepository.currentUser(), message = null, authError = null) }
    }

    fun openMemberCenter() {
        if (authRepository.currentUser() == null) { openLogin(); return }
        _uiState.update { it.copy(screen = AppScreen.MEMBER_CENTER) }
    }

    fun openLogin() {
        _uiState.update {
            it.copy(
                screen = AppScreen.LOGIN,
                authMode = AuthMode.LOGIN,
                authError = null,
                message = null
            )
        }
    }

    fun switchAuthMode(mode: AuthMode) {
        _uiState.update { it.copy(authMode = mode, authError = null) }
    }

    private var registrationInvite = ""

    fun loginWithPhone(phone: String, password: String, inviteCode: String = "") {
        val mode = _uiState.value.authMode
        _uiState.update { it.copy(authBusy = true, authError = null) }
        viewModelScope.launch {
            val result = if (mode == AuthMode.REGISTER) {
                authRepository.registerWithPhone(phone, password, inviteCode)
            } else {
                authRepository.loginWithPhone(phone, password)
            }
            applyAuthResult(result.user, result.error)
            if (result.user != null) initializeApp()
        }
    }

    fun loginWithWeChat(context: android.content.Context, inviteCode: String = "") {
        if (_uiState.value.authBusy || passwordAuthorization != null) return
        registrationInvite = inviteCode
        val attempt = ++wechatAttempt
        _uiState.update { it.copy(authBusy = true, authError = null) }
        viewModelScope.launch {
            delay(120_000)
            if (wechatAttempt == attempt && _uiState.value.authBusy) {
                WeChatLoginManager.cancelAuthorization()
                _uiState.update { it.copy(authBusy = false, authError = "微信授权已超时，请重新发起") }
            }
        }
        val error = WeChatLoginManager.startLogin(context)
        if (error != null) {
            _uiState.update {
                it.copy(authBusy = false, authError = error)
            }
        }
    }

    fun logout() {
        memberStore.clear()
        memberOwner = null
        wechatAttempt++
        passwordAuthorization = null
        WeChatLoginManager.cancelAuthorization()
        val revoke = authRepository.prepareLogout()
        _uiState.update {
            it.copy(
                currentUser = null,
                smsChallenge = null,
                smsPhone = "",
                onboarding = null,
                onboardingError = null,
                onboardingBlockCode = null,
                blockedUntil = null,
                onboardingBusy = false,
                isBusy = false,
                authBusy = false,
                adBusy = false,
                serverCoin = null,
                withdrawals = emptyList(),
                withdrawalOptions = emptyList(),
                paymentAvailable = false,
                alipayAccount = null,
                adHistory = emptyList(),
                appBootstrap = null,
                bootstrapBusy = false,
                bootstrapError = null,
                adSdkReady = false,
                screen = AppScreen.PROFILE,
                authError = null
            )
        }
        viewModelScope.launch { revoke() }
    }

    fun clearAuthError() {
        _uiState.update { it.copy(authError = null) }
    }

    fun openDetail(id: Long) {
        _uiState.update {
            it.copy(screen = AppScreen.DETAIL, detailId = id, detailOrigin = it.screen, message = null)
        }
    }

    fun openFavorites() {
        _uiState.update { it.copy(screen = AppScreen.FAVORITES, message = null) }
    }

    fun selectMode(mode: QuizMode) {
        _uiState.update { it.copy(selectedMode = mode) }
    }

    fun selectDifficulty(difficulty: Int?) {
        _uiState.update { it.copy(selectedDifficulty = difficulty) }
    }

    fun selectCategory(category: String?) {
        _uiState.update { it.copy(selectedCategory = category) }
    }

    fun startQuiz() {
        val selection = _uiState.value
        _uiState.update { it.copy(isBusy = true, message = null) }
        viewModelScope.launch {
            val questions = repository.createQuestions(
                mode = selection.selectedMode,
                difficulty = selection.selectedDifficulty,
                category = selection.selectedCategory
            )
            if (questions.isEmpty()) {
                _uiState.update {
                    it.copy(isBusy = false, message = "暂时没有符合条件的题目，请调整筛选条件")
                }
            } else {
                _uiState.update {
                    it.copy(
                        screen = AppScreen.QUIZ,
                        questions = questions,
                        questionIndex = 0,
                        selectedAnswer = null,
                        answerSubmitted = false,
                        score = 0,
                        correct = 0,
                        incorrect = 0,
                        answerStreak = 0,
                        quizStartedAt = System.currentTimeMillis(),
                        isBusy = false,
                        lastResult = null,
                        message = null
                    )
                }
            }
        }
    }

    fun startMistakeReview() {
        val mistakes = _uiState.value.mistakes
        if (mistakes.isEmpty()) return
        _uiState.update { it.copy(isBusy = true, message = null) }
        viewModelScope.launch {
            val questions = repository.createQuestionsFromIdioms(
                idioms = mistakes,
                mode = QuizMode.DEFINITION
            )
            _uiState.update {
                it.copy(
                    screen = AppScreen.QUIZ,
                    questions = questions,
                    questionIndex = 0,
                    selectedMode = QuizMode.DEFINITION,
                    selectedAnswer = null,
                    answerSubmitted = false,
                    score = 0,
                    correct = 0,
                    incorrect = 0,
                    answerStreak = 0,
                    quizStartedAt = System.currentTimeMillis(),
                    isBusy = false,
                    lastResult = null
                )
            }
        }
    }

    fun selectAnswer(answer: String) {
        val snapshot = _uiState.value
        val question = snapshot.currentQuestion ?: return
        if (snapshot.answerSubmitted) return

        val isCorrect = answer == question.answer
        val nextStreak = if (isCorrect) snapshot.answerStreak + 1 else 0
        val streakBonus = if (isCorrect && nextStreak > 0 && nextStreak % 3 == 0) 10 else 0
        val scoreDelta = if (isCorrect) question.idiom.difficulty * 10 + streakBonus else 0

        _uiState.update {
            it.copy(
                selectedAnswer = answer,
                answerSubmitted = true,
                score = it.score + scoreDelta,
                correct = it.correct + if (isCorrect) 1 else 0,
                incorrect = it.incorrect + if (isCorrect) 0 else 1,
                answerStreak = nextStreak
            )
        }

        repository.playAnswerTone(isCorrect)
        viewModelScope.launch {
            repository.recordAnswer(question, answer, scoreDelta, isCorrect)
            refreshSummary()
        }
    }

    fun nextQuestion() {
        val snapshot = _uiState.value
        if (!snapshot.answerSubmitted) return

        if (snapshot.questionIndex >= snapshot.questions.lastIndex) {
            val duration = if (snapshot.quizStartedAt == 0L) {
                0L
            } else {
                ((System.currentTimeMillis() - snapshot.quizStartedAt) / 1000L).coerceAtLeast(0L)
            }
            _uiState.update {
                it.copy(
                    screen = AppScreen.RESULT,
                    lastResult = QuizResult(
                        score = it.score,
                        correct = it.correct,
                        total = it.questions.size,
                        durationSeconds = duration
                    )
                )
            }
        } else {
            _uiState.update {
                it.copy(
                    questionIndex = it.questionIndex + 1,
                    selectedAnswer = null,
                    answerSubmitted = false
                )
            }
        }
    }

    fun toggleFavorite(id: Long) {
        viewModelScope.launch {
            repository.toggleFavorite(id)
            val idioms = repository.getIdioms()
            _uiState.update { it.copy(idioms = idioms) }
        }
    }

    fun removeMistake(id: Long) {
        viewModelScope.launch {
            repository.removeMistake(id)
            val mistakes = repository.getMistakes()
            _uiState.update {
                it.copy(mistakes = mistakes, mistakeCount = mistakes.size)
            }
        }
    }

    fun updateSettings(settings: AppSettings) {
        repository.updateSettings(settings)
        _uiState.update { it.copy(settings = settings) }
    }

    fun clearProgress() {
        viewModelScope.launch {
            repository.clearProgress()
            refreshSummary()
        }
    }

    fun clearMessage() {
        _uiState.update { it.copy(message = null) }
    }

    fun showMessage(message: String) {
        _uiState.update { it.copy(message = message) }
    }

    private suspend fun refreshSummary(markInitialized: Boolean = false) {
        val idioms = repository.getIdioms()
        val mistakes = repository.getMistakes()
        val stats = repository.getStats()
        _uiState.update {
            it.copy(
                initialized = it.initialized || markInitialized,
                idioms = idioms,
                mistakes = mistakes,
                stats = stats,
                mistakeCount = mistakes.size,
                settings = repository.settings(),
                currentUser = authRepository.currentUser()
            )
        }
    }

    private suspend fun initializeApp() {
        val epoch = authRepository.sessionEpoch()
        initializationMutex.withLock {
            authRepository.checkSession(epoch)
            initializeCurrentSession(epoch)
        }
    }

    private suspend fun initializeCurrentSession(epoch: Long) {
        if (authRepository.currentUser() == null) return
        try { loadOnboarding() }
        catch (error: CancellationException) { throw error }
        catch (error: Exception) {
            recordOnboardingFailure(error)
            return
        }
        authRepository.checkSession(epoch)
        if (!onboardingComplete() || _uiState.value.appBootstrap != null) return
        _uiState.update { it.copy(bootstrapBusy = true, bootstrapError = null) }
        val gameId = authRepository.serverGameId()
        if (gameId == null) {
            _uiState.update {
                it.copy(bootstrapBusy = false, bootstrapError = "服务端未返回游戏 ID")
            }
            return
        }
        val result = authRepository.initializeApp(gameId)
        val bootstrap = result.bootstrap
        val serverCoin = if (result.sessionInvalid) {
            null
        } else {
            sessionCatching { authRepository.walletBalance() }.getOrNull() ?: bootstrap?.coin
        }
        authRepository.checkSession(epoch)
        val adSdkReady = bootstrap?.let {
            AnyThinkAdManager.initialize(getApplication(), it)
        } ?: false
        _uiState.update {
            it.copy(
                appBootstrap = bootstrap,
                serverCoin = serverCoin,
                bootstrapBusy = false,
                bootstrapError = result.error,
                adSdkReady = adSdkReady,
                currentUser = if (result.sessionInvalid) null else authRepository.currentUser()
            )
        }
    }

    private fun applyAuthResult(user: AuthUser?, error: String?) {
        _uiState.update {
            if (user != null) {
                it.copy(
                    screen = AppScreen.PROFILE,
                    currentUser = user,
                    authBusy = false,
                    authError = null
                )
            } else {
                it.copy(authBusy = false, authError = error ?: "登录失败，请稍后重试")
            }
        }
    }

    override fun onCleared() {
        memberStore.clear()
        repository.release()
        super.onCleared()
    }

    companion object {
        private const val AD_FLOW_TAG = "AdFlow"

        fun factory(application: Application): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return QuizViewModel(application) as T
                }
            }
    }
}

// Session invalidation must stop the whole UI operation, including sequential wallet loads.
private inline fun <T> sessionCatching(block: () -> T): Result<T> = try {
    Result.success(block())
} catch (error: CancellationException) {
    throw error
} catch (error: Exception) {
    Result.failure(error)
}
