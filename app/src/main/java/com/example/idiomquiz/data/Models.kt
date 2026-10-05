package com.example.idiomquiz.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "idioms")
data class IdiomEntity(
    @PrimaryKey val id: Long,
    val word: String,
    val pinyin: String,
    val explanation: String,
    val origin: String,
    val example: String,
    val synonyms: String,
    val antonyms: String,
    val difficulty: Int,
    val category: String,
    val isFavorite: Boolean = false
)

@Entity(tableName = "answer_records")
data class AnswerRecordEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val idiomId: Long,
    val questionType: String,
    val selectedAnswer: String,
    val correctAnswer: String,
    val isCorrect: Boolean,
    val answeredAt: Long
)

@Entity(tableName = "user_stats")
data class UserStatsEntity(
    @PrimaryKey val id: Int = 1,
    val totalAnswered: Int = 0,
    val totalCorrect: Int = 0,
    val totalScore: Int = 0,
    val currentStreak: Int = 0,
    val bestStreak: Int = 0,
    val studyStreakDays: Int = 0,
    val lastStudyDate: String = ""
)

enum class QuizMode {
    DEFINITION,
    FILL_BLANK
}

data class QuizQuestion(
    val idiom: IdiomEntity,
    val mode: QuizMode,
    val prompt: String,
    val options: List<String>,
    val answer: String,
    val answerDisplay: String = answer
)

fun fillBlankAnswer(word: String): String = word.getOrNull(1)?.toString().orEmpty()

fun maskIdiomWord(word: String): String = word.mapIndexed { index, char ->
    if (index == 1) '□' else char
}.joinToString("")
