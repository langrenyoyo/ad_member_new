package com.example.idiomquiz.data

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import java.time.LocalDate

class QuizRepository(context: Context) {
    private val database = AppDatabase.get(context)
    private val idiomDao = database.idiomDao()
    private val answerDao = database.answerRecordDao()
    private val statsDao = database.statsDao()
    private val preferences = context.applicationContext.getSharedPreferences(
        "idiom_quiz_preferences",
        Context.MODE_PRIVATE
    )
    private val toneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 65)

    suspend fun initialize() {
        val seededIdioms = SeedData.idioms()
        val existingIds = idiomDao.getAll().map { it.id }.toSet()
        val missingIdioms = seededIdioms.filter { it.id !in existingIds }
        if (missingIdioms.isNotEmpty()) {
            idiomDao.insertAll(missingIdioms)
        }
        if (statsDao.get() == null) {
            statsDao.upsert(UserStatsEntity())
        }
    }

    suspend fun getIdioms(): List<IdiomEntity> = idiomDao.getAll()

    suspend fun getStats(): UserStatsEntity = statsDao.get() ?: UserStatsEntity()

    suspend fun getMistakes(): List<IdiomEntity> {
        val all = idiomDao.getAll().associateBy { it.id }
        return answerDao.getMistakeIds().mapNotNull { all[it] }
    }

    suspend fun getMistakeCount(): Int = answerDao.countMistakes()

    suspend fun toggleFavorite(id: Long) {
        idiomDao.getById(id)?.let { idiomDao.setFavorite(id, !it.isFavorite) }
    }

    suspend fun removeMistake(id: Long) {
        answerDao.deleteForIdiom(id)
    }

    suspend fun clearProgress() {
        answerDao.clear()
        statsDao.upsert(UserStatsEntity())
    }

    fun settings(): AppSettings = AppSettings(
        soundEnabled = preferences.getBoolean(KEY_SOUND, true),
        hapticEnabled = preferences.getBoolean(KEY_HAPTIC, true),
        darkMode = preferences.getBoolean(KEY_DARK_MODE, false)
    )

    fun updateSettings(settings: AppSettings) {
        preferences.edit()
            .putBoolean(KEY_SOUND, settings.soundEnabled)
            .putBoolean(KEY_HAPTIC, settings.hapticEnabled)
            .putBoolean(KEY_DARK_MODE, settings.darkMode)
            .apply()
    }

    fun playAnswerTone(correct: Boolean) {
        if (!preferences.getBoolean(KEY_SOUND, true)) return
        val tone = if (correct) ToneGenerator.TONE_PROP_ACK else ToneGenerator.TONE_PROP_NACK
        toneGenerator.startTone(tone, 110)
    }

    fun release() {
        toneGenerator.release()
    }

    suspend fun createQuestions(
        mode: QuizMode,
        difficulty: Int?,
        category: String?,
        count: Int = 10
    ): List<QuizQuestion> {
        val all = idiomDao.getAll()
        return createQuestionsFromPool(all, mode, difficulty, category, count)
    }

    fun createQuestionsFromIdioms(
        idioms: List<IdiomEntity>,
        mode: QuizMode,
        count: Int = 10
    ): List<QuizQuestion> = createQuestionsFromPool(idioms, mode, null, null, count)

    private fun createQuestionsFromPool(
        all: List<IdiomEntity>,
        mode: QuizMode,
        difficulty: Int?,
        category: String?,
        count: Int
    ): List<QuizQuestion> {
        if (all.isEmpty()) return emptyList()

        val filtered = all.filter { idiom ->
            (difficulty == null || idiom.difficulty == difficulty) &&
                (category == null || idiom.category == category)
        }
        val pool = when {
            filtered.size >= 4 -> filtered
            category != null -> all.filter { it.category == category }.ifEmpty { all }
            difficulty != null -> all.filter { it.difficulty == difficulty }.ifEmpty { all }
            else -> all
        }
        val shuffled = pool.shuffled()

        return (0 until count).map { index ->
            val target = shuffled[index % shuffled.size]
            val questionContent = when (mode) {
                QuizMode.DEFINITION -> {
                    val distractors = all
                        .asSequence()
                        .filter { it.id != target.id }
                        .map { it.word }
                        .distinct()
                        .shuffled()
                        .take(3)
                        .toList()
                    QuestionContent(
                        prompt = "下列哪个成语最符合这段解释？\n${target.explanation}",
                        options = (listOf(target.word) + distractors).shuffled(),
                        answer = target.word,
                        answerDisplay = target.word
                    )
                }

                QuizMode.FILL_BLANK -> {
                    val answer = fillBlankAnswer(target.word)
                    val distractors = (
                        all.map { fillBlankAnswer(it.word) } +
                            listOf("天", "地", "人", "心", "海", "风")
                        )
                        .filter { it.isNotBlank() && it != answer }
                        .distinct()
                        .shuffled()
                        .take(3)
                    QuestionContent(
                        prompt = "请补全成语：${maskIdiomWord(target.word)}",
                        options = (listOf(answer) + distractors).shuffled(),
                        answer = answer,
                        answerDisplay = target.word
                    )
                }
            }
            QuizQuestion(
                idiom = target,
                mode = mode,
                prompt = questionContent.prompt,
                options = questionContent.options,
                answer = questionContent.answer,
                answerDisplay = questionContent.answerDisplay
            )
        }
    }

    suspend fun recordAnswer(
        question: QuizQuestion,
        selectedAnswer: String,
        scoreDelta: Int,
        isCorrect: Boolean
    ) {
        if (isCorrect) {
            answerDao.deleteForIdiom(question.idiom.id)
        }
        answerDao.insert(
            AnswerRecordEntity(
                idiomId = question.idiom.id,
                questionType = question.mode.name,
                selectedAnswer = selectedAnswer,
                correctAnswer = question.answer,
                isCorrect = isCorrect,
                answeredAt = System.currentTimeMillis()
            )
        )

        val old = getStats()
        val nextCurrentStreak = if (isCorrect) old.currentStreak + 1 else 0
        val today = LocalDate.now().toString()
        val nextStudyDays = if (old.lastStudyDate == today) {
            old.studyStreakDays
        } else if (old.lastStudyDate == LocalDate.now().minusDays(1).toString()) {
            old.studyStreakDays + 1
        } else {
            1
        }
        statsDao.upsert(
            old.copy(
                totalAnswered = old.totalAnswered + 1,
                totalCorrect = old.totalCorrect + if (isCorrect) 1 else 0,
                totalScore = old.totalScore + scoreDelta,
                currentStreak = nextCurrentStreak,
                bestStreak = maxOf(old.bestStreak, nextCurrentStreak),
                studyStreakDays = nextStudyDays,
                lastStudyDate = today
            )
        )
    }

    companion object {
        private const val KEY_SOUND = "sound_enabled"
        private const val KEY_HAPTIC = "haptic_enabled"
        private const val KEY_DARK_MODE = "dark_mode"
    }
}

private data class QuestionContent(
    val prompt: String,
    val options: List<String>,
    val answer: String,
    val answerDisplay: String
)

data class AppSettings(
    val soundEnabled: Boolean = true,
    val hapticEnabled: Boolean = true,
    val darkMode: Boolean = false
)
