package com.heshangzhilian.yazhiyiji.wxapi

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import com.example.idiomquiz.auth.WeChatLoginManager
import com.example.idiomquiz.BuildConfig
import com.tencent.mm.opensdk.modelbase.BaseResp
import com.tencent.mm.opensdk.modelbase.BaseReq
import com.tencent.mm.opensdk.openapi.IWXAPI
import com.tencent.mm.opensdk.openapi.IWXAPIEventHandler
import com.tencent.mm.opensdk.openapi.WXAPIFactory

class WXEntryActivity : Activity(), IWXAPIEventHandler {
    private lateinit var wxApi: IWXAPI

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wxApi = WXAPIFactory.createWXAPI(this, BuildConfig.WECHAT_APP_ID, false)
        if (!wxApi.handleIntent(intent, this)) finish()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        if (intent == null) return
        setIntent(intent)
        wxApi.handleIntent(intent, this)
    }

    override fun onReq(req: BaseReq) {
        finish()
    }

    override fun onResp(resp: BaseResp) {
        WeChatLoginManager.handleResponse(resp)
        finish()
    }
}
