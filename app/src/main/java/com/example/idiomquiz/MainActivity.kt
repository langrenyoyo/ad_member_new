package com.example.idiomquiz

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.idiomquiz.ui.IdiomQuizApp
import com.example.idiomquiz.ui.IdiomQuizTheme
import com.example.idiomquiz.ui.QuizViewModel

class MainActivity : ComponentActivity() {
    private val viewModel: QuizViewModel by viewModels {
        QuizViewModel.factory(application)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val state = viewModel.uiState.collectAsStateWithLifecycle().value
            IdiomQuizTheme(darkTheme = state.settings.darkMode) {
                IdiomQuizApp(state = state, viewModel = viewModel)
            }
        }
    }
}
