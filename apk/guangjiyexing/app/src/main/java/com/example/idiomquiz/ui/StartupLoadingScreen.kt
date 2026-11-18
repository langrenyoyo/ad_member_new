package com.example.idiomquiz.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.example.idiomquiz.ads.AnyThinkAdManager
import com.example.idiomquiz.ads.StartupAdCache
import kotlinx.coroutines.delay

@Composable
fun StartupLoadingScreen(progress: Float? = null) {
    Surface(Modifier.fillMaxSize(), color=MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().padding(40.dp), verticalArrangement=Arrangement.Center,
            horizontalAlignment=Alignment.CenterHorizontally) {
            Text("禾合",style=MaterialTheme.typography.headlineLarge,color=MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(28.dp))
            Text("正在准备，请稍候",style=MaterialTheme.typography.bodyLarge)
            Spacer(Modifier.height(20.dp))
            if(progress==null) LinearProgressIndicator(Modifier.fillMaxWidth())
            else {
                LinearProgressIndicator(progress={progress},modifier=Modifier.fillMaxWidth())
                Text("${(progress*100).toInt()}%",Modifier.padding(top=12.dp))
            }
        }
    }
}

private tailrec fun Context.startupActivity(): Activity? = when(this) {
    is Activity -> this
    is ContextWrapper -> baseContext.startupActivity()
    else -> null
}

@Composable
fun StartupAdPreparation(state: UiState): Boolean {
    val context=LocalContext.current
    val user=state.currentUser?.id
    var done by rememberSaveable(user) { mutableStateOf(false) }
    var completed by remember(user) { mutableIntStateOf(0) }
    LaunchedEffect(user,state.adSdkReady,state.appBootstrap) {
        if(user==null || done) return@LaunchedEffect
        val bootstrap=state.appBootstrap
        if(!state.adSdkReady || bootstrap==null) {
            delay(8000);done=true;return@LaunchedEffect
        }
        val activity=context.startupActivity()
        if(activity==null) {done=true;return@LaunchedEffect}
        try {
            StartupAdCache.load(activity,bootstrap,AnyThinkAdManager.preloadReporter()) {completed=it}
            completed=5
            delay(200)
            done=true
        } catch (error: kotlinx.coroutines.CancellationException) {throw error}
        catch (_: Exception) {StartupAdCache.clear();done=true}
    }
    if(user!=null && !done) StartupLoadingScreen(completed/5f)
    return user==null || done
}
