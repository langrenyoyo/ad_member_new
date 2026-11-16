package com.example.idiomquiz

import android.os.Bundle
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.mutableStateOf
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.idiomquiz.ui.IdiomQuizApp
import com.example.idiomquiz.ui.IdiomQuizTheme
import com.example.idiomquiz.ui.QuizViewModel
import com.example.idiomquiz.ui.StartupAccessScreen
import com.example.idiomquiz.security.AppUsageCollector

class MainActivity : ComponentActivity() {
    private val usageAllowed = mutableStateOf(false)
    private var waitingForAccess = false
    // This activity extends ComponentActivity, never FragmentActivity. The vendor SDK's
    // legacy support fragments do not participate in our ActivityResultRegistry.
    @android.annotation.SuppressLint("InvalidFragmentVersionForActivityResult")
    private val usageSettings = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        waitingForAccess = false
        usageAllowed.value = AppUsageCollector.consented(this) && AppUsageCollector.granted(this)
        if (!usageAllowed.value) finishAndRemoveTask()
    }
    private val viewModel: QuizViewModel by viewModels {
        QuizViewModel.factory(application)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        waitingForAccess = savedInstanceState?.getBoolean("waitingForAccess") ?: false
        usageAllowed.value = AppUsageCollector.consented(this) && AppUsageCollector.granted(this)
        setContent {
            if (usageAllowed.value) {
                val state = viewModel.uiState.collectAsStateWithLifecycle().value
                IdiomQuizTheme(darkTheme = state.settings.darkMode) {
                    IdiomQuizApp(state = state, viewModel = viewModel)
                }
            } else {
                IdiomQuizTheme {
                    StartupAccessScreen(onAuthorize = {
                        AppUsageCollector.acceptConsent(this)
                        if (AppUsageCollector.granted(this)) {
                            usageAllowed.value = true
                        } else {
                            waitingForAccess = true
                            runCatching { usageSettings.launch(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,
                            Uri.parse("package:$packageName"))) }.onFailure {
                            runCatching { usageSettings.launch(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) }
                                .onFailure { waitingForAccess = false; finishAndRemoveTask() }
                            }
                        }
                    }, onExit = { finishAndRemoveTask() })
                }
            }
        }
        acceptInvitation(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        acceptInvitation(intent)
    }

    private fun acceptInvitation(intent: Intent?) {
        val uri = intent?.data ?: return
        if (uri.scheme != "guangjiyexing" || uri.host != "invite") return
        if (uri.getQueryParameter("game_id")?.toIntOrNull() != BuildConfig.REGISTRATION_GAME_ID) return
        val code = uri.getQueryParameter("invite_code")?.uppercase() ?: return
        if (Regex("[A-Z0-9]{6}").matches(code)) {
            getSharedPreferences("pending_invitation", MODE_PRIVATE).edit().putString("code", code).apply()
            // Do not initialize the business/SDK view model until usage access is granted.
            if (usageAllowed.value) viewModel.acceptInvitation(code)
        }
    }

    override fun onResume() {
        super.onResume()
        if (!waitingForAccess) {
            val granted = AppUsageCollector.consented(this) && AppUsageCollector.granted(this)
            if (usageAllowed.value && !granted) finishAndRemoveTask()
            usageAllowed.value = granted
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean("waitingForAccess", waitingForAccess)
        super.onSaveInstanceState(outState)
    }
}
