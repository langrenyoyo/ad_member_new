package com.example.idiomquiz.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.idiomquiz.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

internal enum class MemberSection(val title: String) {
    PROFILE("会员资料"), PASSWORD("修改密码"), OBSERVATIONS("设备观测"), GAMES("可用游戏"), COINS("金币流水"),
    WITHDRAWALS("提现记录"), ADS("广告记录"), CAMPAIGNS("补贴活动"), SUBSIDIES("补贴申请记录"), COMMISSIONS("分佣收益"), TEAM("直属邀请")
}

internal data class MemberCenterState(
    val section: MemberSection = MemberSection.PROFILE,
    val busy: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
    val profile: JSONObject? = null,
    val items: List<JSONObject> = emptyList(),
    val total: Int = 0,
    val commissionSummary: JSONObject? = null,
    val hasMore: Boolean = false,
    val detail: JSONObject? = null,
    val images: Map<String, String> = emptyMap(),
    val formRevision: Int = 0,
    val recoveryMessage: String? = null,
    val recovering: Boolean = false,
    val recoveryPending: Boolean = false
)

internal class MemberCenterViewModel(application: Application) : AndroidViewModel(application) {
    private val auth = AuthRepository(application)
    private val mutable = MutableStateFlow(MemberCenterState())
    val state = mutable.asStateFlow()
    private var applicationKey = UUID.randomUUID().toString()
    private var applicationFingerprint: String? = null
    private val campaignRequests = AuthRepository.campaignRequests

    init { load(MemberSection.PROFILE); retryCampaignRecovery() }

    fun retryCampaignRecovery() {
        if (mutable.value.recovering || auth.pendingCampaign() == null) return
        mutable.update { it.copy(recovering = true, recoveryPending = true, recoveryMessage = "正在确认原补贴申请") }
        viewModelScope.launch {
            try {
                recoverCampaign()
                mutable.update { it.copy(recoveryMessage = "原补贴申请已确认，可查看申请记录") }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { mutable.update { it.copy(recoveryMessage = "补贴确认失败：${e.message}，可稍后重试") } }
            finally { mutable.update { it.copy(recovering = false, recoveryPending = auth.pendingCampaign() != null) } }
        }
    }

    private fun runAction(action: suspend () -> Unit) {
        if (mutable.value.busy) return
        mutable.update { it.copy(busy = true, error = null, notice = null) }
        viewModelScope.launch {
            try { action() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { mutable.update { it.copy(error = e.message ?: "操作失败，请重试") } }
            finally {
                val pending = auth.pendingCampaign() != null
                mutable.update { it.copy(busy = false, recoveryPending = pending,
                    recoveryMessage = if (pending && !it.recovering) "补贴申请结果尚未确认，请重试确认原申请。" else it.recoveryMessage) }
            }
        }
    }

    fun load(section: MemberSection = mutable.value.section, append: Boolean = false) = runAction {
        val offset = if (append) mutable.value.items.size else 0
        if (!append && section != mutable.value.section) mutable.update { it.copy(section = section, items = emptyList(), total = 0,
            hasMore = false, detail = null, images = emptyMap(), commissionSummary = null) }
        if (section == MemberSection.PASSWORD || section == MemberSection.OBSERVATIONS) return@runAction
        if (section == MemberSection.PROFILE) {
            val profile = auth.memberRequest("GET", "me").getJSONObject("data")
            mutable.update { it.copy(profile = profile) }
            return@runAction
        }
        val gameId = auth.serverGameId() ?: error("账号未关联游戏，请重新登录")
        val path = when (section) {
            MemberSection.GAMES -> "games"
            MemberSection.COINS -> "wallet/coin-logs?limit=20&offset=$offset"
            MemberSection.COMMISSIONS -> "commissions?limit=20&offset=$offset"
            MemberSection.TEAM -> "commission-team?limit=20&offset=$offset"
            MemberSection.WITHDRAWALS -> "withdrawals?limit=20&offset=$offset"
            MemberSection.ADS -> "ads/history?game_id=$gameId&limit=20&offset=$offset"
            MemberSection.CAMPAIGNS -> "subsidy-campaigns?game_id=$gameId"
            MemberSection.SUBSIDIES -> "subsidies?game_id=$gameId&limit=20&offset=$offset"
            else -> error("不支持的页面")
        }
        val response = auth.memberRequest("GET", path)
        val page = parseMemberPage(response, offset)
        mutable.update { it.copy(items = if (append) it.items + page.items else page.items,
            total = page.total, hasMore = page.hasMore,
            commissionSummary = if (section == MemberSection.COMMISSIONS) response.optJSONObject("data")?.optJSONObject("summary") else null) }
    }

    fun saveProfile(name: String, realName: String, receiveName: String, address: String, sex: Int) = runAction {
        require(name.trim().isNotEmpty() && name.length <= 128) { "昵称不能为空且不能超过 128 字" }
        require(realName.length <= 64 && receiveName.length <= 64 && address.length <= 255) { "资料内容超出长度限制" }
        val data = auth.memberRequest("PATCH", "me", JSONObject().put("name", name.trim())
            .put("real_name", realName.trim()).put("receive_name", receiveName.trim())
            .put("address", address.trim()).put("sex", sex)).getJSONObject("data")
        auth.restoreSession()
        mutable.update { it.copy(profile = data, notice = "资料已保存") }
    }

    fun changePassword(current: String, password: String, confirmation: String) = runAction {
        require(current.isNotEmpty()) { "请输入当前密码" }
        validateNewPassword(password, confirmation)
        auth.memberRequest("POST", "auth/change-password", JSONObject()
            .put("current_password", current).put("new_password", password))
        mutable.update { it.copy(notice = "密码已修改", formRevision = it.formRevision + 1) }
    }

    fun detail(id: String) = runAction {
        val path = when (mutable.value.section) {
            MemberSection.WITHDRAWALS -> "withdrawals/$id"
            MemberSection.CAMPAIGNS -> "subsidy-campaigns/$id"
            MemberSection.SUBSIDIES -> "subsidies/$id"
            else -> return@runAction
        }
        val result = auth.memberRequest("GET", path).getJSONObject("data")
        applicationKey = UUID.randomUUID().toString()
        applicationFingerprint = null
        mutable.update { it.copy(detail = result, images = emptyMap()) }
    }

    fun closeDetail() { if (!mutable.value.busy) mutable.update { it.copy(detail = null, images = emptyMap()) } }

    fun upload(slot: String, uri: Uri) = runAction {
        val resolver = getApplication<Application>().contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        val bytes = withContext(Dispatchers.IO) {
            resolver.openInputStream(uri)?.use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= 2 * 1024 * 1024) { "图片不能超过 2MB，请压缩后重试" }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            } ?: error("无法读取所选图片")
        }
        val url = auth.uploadEvidence(bytes, mime)
        if (slot == "avatar") {
            val profile = auth.memberRequest("PATCH", "me", JSONObject().put("image_url", url)).getJSONObject("data")
            mutable.update { it.copy(profile = profile, notice = "头像已更新") }
        } else mutable.update { it.copy(images = it.images + (slot to url), notice = "图片上传成功") }
    }

    fun applySubsidy(name: String, account: String, amount: String, campaign: Boolean) = runAction {
        campaignRequests.exclusive {
        if (auth.pendingCampaign() != null) {
            recoverCampaignLocked()
            mutable.update { it.copy(notice = "原申请已恢复，请在申请记录中查看") }
            return@exclusive
        }
        val epoch = auth.sessionEpoch()
        require(name.trim().isNotEmpty() && name.length <= 64 && account.trim().isNotEmpty() && account.length <= 64) {
            "请填写收款姓名和账号（各不超过 64 字）"
        }
        val body = JSONObject().put("receive_name", name.trim()).put("receive_tel", account.trim())
        val path: String
        if (campaign) {
            val detail = mutable.value.detail ?: error("请重新打开活动")
            require(detail.optBoolean("eligible")) { "暂不符合活动条件，请刷新活动详情" }
            for (slot in listOf("download_image", "install_image", "recharge_image")) {
                body.put(slot, mutable.value.images[slot] ?: error("请分别上传三类凭证图片"))
            }
            require(mutable.value.images.values.toSet().size == 3) { "三类凭证必须是不同图片" }
            path = "subsidy-campaigns/${detail.getInt("id")}/applications"
            // Keep the key for an uncertain response; changing content starts a new operation.
            val fingerprint = path + body.toString()
            if (applicationFingerprint != null && applicationFingerprint != fingerprint) applicationKey = UUID.randomUUID().toString()
            applicationFingerprint = fingerprint
            body.put("request_key", applicationKey)
            auth.savePendingCampaign(JSONObject().put("path", path).put("body", body), epoch)
        } else {
            body.put("game_id", auth.serverGameId() ?: error("账号未关联游戏"))
                .put("tx_price", moneyInput(amount).toPlainString())
                .put("pics", JSONArray(mutable.value.images.values.toList()))
            path = "subsidies"
        }
        auth.memberRequest("POST", path, body)
        if (campaign) auth.savePendingCampaign(null, epoch)
        applicationKey = UUID.randomUUID().toString()
        applicationFingerprint = null
        mutable.update { it.copy(detail = null, images = emptyMap(), notice = "补贴申请已提交，可在申请记录中查看",
            formRevision = it.formRevision + 1) }
        }
    }

    private suspend fun recoverCampaign() = campaignRequests.exclusive {
        recoverCampaignLocked()
    }

    // Caller holds the process-wide campaign lock through request completion and cleanup.
    private suspend fun recoverCampaignLocked() {
        val epoch = auth.sessionEpoch()
        campaignRequests.recoverLocked(
            read = { auth.checkSession(epoch); auth.pendingCampaign() },
            send = { pending -> auth.memberRequest("POST", pending.getString("path"), pending.getJSONObject("body")); Unit },
            clear = { auth.savePendingCampaign(null, epoch) },
            definiteFailure = { it is UserApiException && it.statusCode in listOf(400, 403, 404, 409, 410, 422) }
        )
    }
}
