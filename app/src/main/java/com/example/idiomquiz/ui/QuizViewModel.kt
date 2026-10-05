package com.example.idiomquiz.ui

import android.app.Application
import android.app.Activity
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
import com.example.idiomquiz.data.QuizMode
import com.example.idiomquiz.data.QuizRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import com.example.idiomquiz.security.SecurityGuard

class QuizViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = QuizRepository(application)
    private val authRepository = AuthRepository(application)
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            WeChatLoginManager.events.collect { event ->
                when (event) {
                    is WeChatLoginEvent.Authorized -> _uiState.update {
                        it.copy(
                            authBusy = false,
                            message = "微信 SDK 授权成功，code：${event.code}"
                        )
                    }

                    is WeChatLoginEvent.Failed -> _uiState.update {
                        it.copy(authBusy = false, authError = event.message)
                    }
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
            val security = SecurityGuard.evaluate(getApplication())
            if (state.appBootstrap?.adsEnabled == true && !security.blocked) {
                state.copy(screen = AppScreen.AD_DEMO, message = null)
            } else if (security.blocked) {
                state.copy(message = "当前设备环境不支持广告功能：${security.flags.joinToString("、")}")
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
            runCatching {
                authRepository.adHistory(
                    state.appBootstrap?.gameId ?: AppBootstrap.DEFAULT_GAME_ID
                )
            }.onSuccess { records ->
                _uiState.update { it.copy(adHistory = records, isBusy = false) }
            }.onFailure { error ->
                _uiState.update {
                    it.copy(isBusy = false, message = "广告记录加载失败：" + error.message)
                }
            }
        }
    }

    fun showRewardedAd(activity: Activity, placement: AdPlacement, onClosed: () -> Unit = {}) {
        val snapshot = _uiState.value
        viewModelScope.launch {
            runCatching {
                val session = authRepository.requestAd(
                    snapshot.appBootstrap?.gameId ?: AppBootstrap.DEFAULT_GAME_ID,
                    placement.placement,
                    placement.adType
                ) ?: error("请先登录后再请求广告")
                if (session.expiresAtEpochMillis != null &&
                    session.expiresAtEpochMillis <= System.currentTimeMillis()
                ) {
                    authRepository.adFail(session, "SESSION_EXPIRED")
                    error("广告会话已过期，请重试")
                }
                var rewarded = false
                var shownAtMillis = 0L
                AnyThinkAdManager.showRewarded(
                    activity,
                    placement.copy(adUnitId = session.adUnitId),
                    onReward = {
                        rewarded = true
                        val watchedSeconds = if (shownAtMillis == 0L) {
                            0
                        } else {
                            ((System.currentTimeMillis() - shownAtMillis) / 1_000L)
                                .coerceAtLeast(0L)
                                .coerceAtMost(Int.MAX_VALUE.toLong())
                                .toInt()
                        }
                        viewModelScope.launch {
                            runCatching { authRepository.adComplete(session, watchedSeconds) }
                                .onSuccess { response ->
                                    val data = response.optJSONObject("data") ?: response
                                    val coinBalance = data.opt("coin_balance")
                                        ?.toString()?.toLongOrNull()
                                    _uiState.update {
                                        it.copy(
                                            serverCoin = coinBalance ?: it.serverCoin,
                                            message = "广告完成，奖励已提交"
                                        )
                                    }
                                }
                                .onFailure { _uiState.update { it.copy(message = "奖励结算失败：${it.message}") } }
                        }
                    },
                    onClosed = {
                        if (!rewarded) viewModelScope.launch {
                            runCatching { authRepository.adFail(session, "CLOSED_BEFORE_REWARD") }
                        }
                        onClosed()
                    },
                    onShown = {
                        shownAtMillis = System.currentTimeMillis()
                        viewModelScope.launch {
                            runCatching { authRepository.adImpression(session) }
                                .onFailure {
                                    _uiState.update { state ->
                                        state.copy(message = "广告曝光上报失败：" + it.message)
                                    }
                                }
                        }
                    }
                )
            }.onFailure { error ->
                _uiState.update { it.copy(message = "广告请求失败：${error.message}") }
            }
        }
    }

    fun openProfile() {
        _uiState.update { it.copy(screen = AppScreen.PROFILE, message = null, authError = null) }
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

    fun loginWithPhone(phone: String, password: String) {
        val mode = _uiState.value.authMode
        _uiState.update { it.copy(authBusy = true, authError = null) }
        viewModelScope.launch {
            val result = if (mode == AuthMode.REGISTER) {
                authRepository.registerWithPhone(phone, password)
            } else {
                authRepository.loginWithPhone(phone, password)
            }
            applyAuthResult(result.user, result.error)
            if (result.user != null) initializeApp()
        }
    }

    fun loginWithWeChat(context: android.content.Context) {
        _uiState.update { it.copy(authBusy = true, authError = null) }
        val error = WeChatLoginManager.startLogin(context)
        if (error != null) {
            _uiState.update {
                it.copy(authBusy = false, authError = error)
            }
        }
    }

    fun logout() {
        _uiState.update {
            it.copy(
                currentUser = null,
                appBootstrap = null,
                bootstrapBusy = false,
                bootstrapError = null,
                adSdkReady = false,
                screen = AppScreen.PROFILE,
                authError = null
            )
        }
        viewModelScope.launch { authRepository.logout() }
    }

    fun clearAuthError() {
        _uiState.update { it.copy(authError = null) }
    }

    fun openDetail(id: Long) {
        _uiState.update {
            it.copy(screen = AppScreen.DETAIL, detailId = id, message = null)
        }
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
        if (authRepository.currentUser() == null) return
        _uiState.update { it.copy(bootstrapBusy = true, bootstrapError = null) }
        val result = authRepository.initializeApp(AppBootstrap.DEFAULT_GAME_ID)
        val bootstrap = result.bootstrap
        val serverCoin = if (result.sessionInvalid) {
            null
        } else {
            runCatching { authRepository.walletBalance() }.getOrNull() ?: bootstrap?.coin
        }
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
        repository.release()
        super.onCleared()
    }

    companion object {
        fun factory(application: Application): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return QuizViewModel(application) as T
                }
            }
    }
}
