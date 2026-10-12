package com.example.idiomquiz

import android.app.Application
import android.util.Log
import com.example.idiomquiz.security.AliyunDeviceRiskManager
import com.example.idiomquiz.BuildConfig

class IdiomQuizApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Device collection starts only on an explicit rewarded-ad action after consent.
    }
}
