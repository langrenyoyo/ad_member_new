package com.example.idiomquiz.auth

import android.content.Context
import android.util.Log
import com.example.idiomquiz.BuildConfig
import com.tencent.mm.opensdk.modelbase.BaseResp
import com.tencent.mm.opensdk.modelmsg.SendAuth
import com.tencent.mm.opensdk.openapi.IWXAPI
import com.tencent.mm.opensdk.openapi.WXAPIFactory
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.util.UUID

sealed interface WeChatLoginEvent {
    data class Authorized(
        val code: String,
        val state: String
    ) : WeChatLoginEvent

    data class Failed(
        val errorCode: Int,
        val message: String
    ) : WeChatLoginEvent
}

object WeChatLoginManager {
    private const val TAG = "IdiomQuizWeChat"

    private var wxApi: IWXAPI? = null
    private var expectedState: String? = null

    private val _events = MutableSharedFlow<WeChatLoginEvent>(extraBufferCapacity = 1)
    val events = _events.asSharedFlow()

    fun startLogin(context: Context): String? {
        val appId = BuildConfig.WECHAT_APP_ID.trim()
        if (appId.isBlank()) {
            return "微信 AppID 未配置"
        }

        val api = wxApi ?: WXAPIFactory.createWXAPI(
            context.applicationContext,
            appId,
            true
        ).also {
            it.registerApp(appId)
            wxApi = it
        }

        if (!api.isWXAppInstalled) {
            return "请先安装微信客户端"
        }
        if (api.getWXAppSupportAPI() <= 0) {
            return "当前微信版本不支持登录"
        }

        val state = "idiom_quiz_${UUID.randomUUID()}"
        expectedState = state
        val request = SendAuth.Req().apply {
            scope = "snsapi_userinfo"
            this.state = state
        }

        if (!api.sendReq(request)) {
            expectedState = null
            return "无法调起微信登录，请检查微信配置"
        }

        Log.d(TAG, "WeChat login request sent, state=$state")
        return null
    }

    fun handleResponse(response: BaseResp) {
        val authResponse = response as? SendAuth.Resp
        if (authResponse == null) {
            emitFailure(response.errCode, response.errStr ?: "微信返回了无法识别的响应")
            return
        }

        val state = authResponse.state.orEmpty()
        val expected = expectedState
        expectedState = null
        if (expected != null && expected != state) {
            emitFailure(-1, "微信登录 state 校验失败")
            return
        }

        if (authResponse.errCode != BaseResp.ErrCode.ERR_OK) {
            emitFailure(
                authResponse.errCode,
                authResponse.errStr?.takeIf { it.isNotBlank() }
                    ?: "微信登录失败（${authResponse.errCode}）"
            )
            return
        }

        val code = authResponse.code.orEmpty()
        if (code.isBlank()) {
            emitFailure(-1, "微信登录成功但未返回授权 code")
            return
        }

        Log.i(TAG, "WeChat login authorized, code=$code, state=$state")
        _events.tryEmit(WeChatLoginEvent.Authorized(code = code, state = state))
    }

    private fun emitFailure(errorCode: Int, message: String) {
        Log.w(TAG, "WeChat login failed: code=$errorCode, message=$message")
        _events.tryEmit(WeChatLoginEvent.Failed(errorCode, message))
    }
}
