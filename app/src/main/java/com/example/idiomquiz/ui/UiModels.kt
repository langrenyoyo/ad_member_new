package com.example.idiomquiz.ui

import com.example.idiomquiz.data.AppSettings
import com.example.idiomquiz.data.AppBootstrap
import com.example.idiomquiz.data.AdHistoryRecord
import com.example.idiomquiz.data.AuthUser
import com.example.idiomquiz.data.IdiomEntity
import com.example.idiomquiz.data.QuizMode
import com.example.idiomquiz.data.QuizQuestion
import com.example.idiomquiz.data.UserStatsEntity

enum class AppScreen {
    HOME,
    MODE_SELECTION,
    QUIZ,
    RESULT,
    MISTAKES,
    STATS,
    SETTINGS,
    AD_DEMO,
    AD_HISTORY,
    DETAIL,
    PROFILE,
    LOGIN
}

enum class AuthMode {
    LOGIN,
    REGISTER
}

data class QuizResult(
    val score: Int,
    val correct: Int,
    val total: Int,
    val durationSeconds: Long
) {
    val accuracy: Int
        get() = if (total == 0) 0 else (correct * 100 / total)
}

data class UiState(
    val initialized: Boolean = false,
    val screen: AppScreen = AppScreen.HOME,
    val idioms: List<IdiomEntity> = emptyList(),
    val mistakes: List<IdiomEntity> = emptyList(),
    val stats: UserStatsEntity = UserStatsEntity(),
    val mistakeCount: Int = 0,
    val settings: AppSettings = AppSettings(),
    val currentUser: AuthUser? = null,
    val appBootstrap: AppBootstrap? = null,
    val serverCoin: Long? = null,
    val adHistory: List<AdHistoryRecord> = emptyList(),
    val bootstrapBusy: Boolean = false,
    val bootstrapError: String? = null,
    val adSdkReady: Boolean = false,
    val authMode: AuthMode = AuthMode.LOGIN,
    val authError: String? = null,
    val authBusy: Boolean = false,
    val selectedMode: QuizMode = QuizMode.DEFINITION,
    val selectedDifficulty: Int? = null,
    val selectedCategory: String? = null,
    val questions: List<QuizQuestion> = emptyList(),
    val questionIndex: Int = 0,
    val selectedAnswer: String? = null,
    val answerSubmitted: Boolean = false,
    val score: Int = 0,
    val correct: Int = 0,
    val incorrect: Int = 0,
    val answerStreak: Int = 0,
    val quizStartedAt: Long = 0L,
    val lastResult: QuizResult? = null,
    val isBusy: Boolean = false,
    val message: String? = null,
    val detailId: Long? = null
) {
    val categories: List<String>
        get() = idioms.map { it.category }.distinct().sorted()

    val currentQuestion: QuizQuestion?
        get() = questions.getOrNull(questionIndex)

    val progress: Float
        get() = if (questions.isEmpty()) 0f else (questionIndex + 1f) / questions.size
}
