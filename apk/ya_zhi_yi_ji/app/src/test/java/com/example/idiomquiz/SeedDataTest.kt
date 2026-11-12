package com.example.idiomquiz

import com.example.idiomquiz.data.SeedData
import com.example.idiomquiz.data.fillBlankAnswer
import com.example.idiomquiz.data.maskIdiomWord
import com.example.idiomquiz.ui.QuizResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SeedDataTest {
    @Test
    fun seedDataContainsEnoughUsableIdioms() {
        val idioms = SeedData.idioms()

        assertEquals(300, idioms.size)
        assertEquals(idioms.size, idioms.map { it.id }.distinct().size)
        assertEquals(idioms.size, idioms.map { it.word }.distinct().size)
        assertTrue(idioms.all { it.word.length == 4 })
        assertTrue(idioms.all { it.explanation.isNotBlank() && it.example.isNotBlank() })
    }

    @Test
    fun quizResultCalculatesAccuracy() {
        assertEquals(80, QuizResult(score = 20, correct = 8, total = 10, durationSeconds = 12).accuracy)
        assertEquals(0, QuizResult(score = 0, correct = 0, total = 0, durationSeconds = 0).accuracy)
    }

    @Test
    fun fillBlankQuestionUsesOneCharacterAnswer() {
        assertEquals("龙", fillBlankAnswer("画龙点睛"))
        assertEquals("画□点睛", maskIdiomWord("画龙点睛"))
        assertEquals("", fillBlankAnswer(""))
    }
}
