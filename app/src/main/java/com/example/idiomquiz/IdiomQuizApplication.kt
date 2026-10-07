package com.example.idiomquiz

import android.app.Application
import android.util.Log
import com.example.idiomquiz.security.AliyunDeviceRiskManager
import com.example.idiomquiz.BuildConfig

class IdiomQuizApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        val appKey = BuildConfig.ALIYUN_DEVICE_RISK_APP_KEY.trim()
        if (appKey.isNotEmpty() && AliyunDeviceRiskManager.isAvailable()) {
            AliyunDeviceRiskManager.initialize(this, appKey) { code ->
                Log.i("AliyunDeviceRisk", "初始化结果 code=$code")
            }
        }
    }
}
