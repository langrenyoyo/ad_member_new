package com.example.idiomquiz.data

import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull
import java.io.IOException
import java.util.UUID
import org.json.JSONObject
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

enum class AuthProvider {
    PHONE,
    WECHAT
}

data class AuthUser(
    val id: String,
    val displayName: String,
    val accountLabel: String,
    val provider: AuthProvider
)

data class AuthResult(
    val user: AuthUser? = null,
    val error: String? = null
)

class AuthRepository(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        "idiom_quiz_auth",
        Context.MODE_PRIVATE
    )
    private val api = UserAppApi(context)

    fun sessionEpoch(): Long = sessions.snapshot()
    fun pendingCampaign(): JSONObject? = preferences.getString("pending_campaign", null)?.let { JSONObject(it) }
    fun savePendingCampaign(value: JSONObject?, epoch: Long) = sessions.withCurrent(epoch) {
        val editor = preferences.edit()
        if (value == null) editor.remove("pending_campaign") else editor.putString("pending_campaign", value.toString())
        check(editor.commit()) { "无法保存申请恢复记录，请重试" }
    }
    fun checkSession(epoch: Long) = sessions.withCurrent(epoch) { }
    suspend fun sendSms(phone: String): String = api.sendSms(phone.trim(), deviceId())
    suspend fun loginWithSms(phone: String, code: String, challenge: String, password: String, inviteCode: String = ""): AuthResult =
        authenticate(sms = true) { api.smsLogin(phone.trim(), code.trim(), challenge, password, deviceId(), inviteCode) }

    private suspend fun validAccessToken(epoch: Long, rejected: String? = null): String? = refreshMutex.withLock {
        val current = sessions.withCurrent(epoch) { accessToken() }
        if (current != null && ((rejected != null && current != rejected) ||
                (rejected == null && preferences.getLong(KEY_EXPIRES_AT, 0) > System.currentTimeMillis() + 60_000))) {
            return@withLock current
        }
        val refresh = sessions.withCurrent(epoch) { refreshToken() } ?: return@withLock current
        try {
            val session = api.refresh(refresh, deviceId())
            sessions.withCurrent(epoch) { saveTokens(session) }
            session.accessToken
        } catch (e: UserApiException) {
            sessions.withCurrent(epoch) {
                if (e.statusCode in listOf(401, 403)) clearSession()
            }
            throw e
        }
    }

    suspend fun loginWithWeChatCode(code: String, inviteCode: String = ""): AuthResult = authenticate {
        api.wechatLogin(code, deviceId(), com.example.idiomquiz.BuildConfig.REGISTRATION_GAME_ID, inviteCode)
    }

    private suspend fun <T> authenticated(request: suspend (String) -> T): T =
        authenticatedInSession(sessions.snapshot(), request)

    private suspend fun <T> authenticatedInSession(epoch: Long, request: suspend (String) -> T): T {
        try {
        val token = validAccessToken(epoch) ?: throw UserApiException(401, "SESSION_EXPIRED", "Please sign in again")
        val result = try {
            request(token)
        } catch (e: UserApiException) {
            sessions.withCurrent(epoch) { }
            // A business 401 (wrong password/code) is not permission to replay a mutation.
            if (e.statusCode != 401 || e.errorCode != "TOKEN_EXPIRED") throw e
            val renewed = validAccessToken(epoch, token) ?: throw e
            request(renewed)
        }
        return sessions.withCurrent(epoch) { result }
        } catch (error: Exception) {
            sessions.withCurrent(epoch) { }
            throw error
        }
    }

    internal suspend fun memberRequest(method: String, path: String, body: JSONObject? = null): JSONObject =
        authenticated { token -> api.requestJson(method, path, deviceId(), token, body) }

    internal suspend fun uploadEvidence(bytes: ByteArray, mime: String): String {
        require(bytes.isNotEmpty() && bytes.size <= 2 * 1024 * 1024) { "图片不能超过 2MB" }
        return authenticated { token ->
            api.requestJson("POST", "subsidies/images", deviceId(), token,
                rawBody = bytes, contentType = mime).getJSONObject("data").getString("url")
        }
    }

    suspend fun refreshWallet(): JSONObject {
        scheduleRewardCompletions()
        return memberRequest("GET", "wallet").getJSONObject("data")
    }

    fun currentUser(): AuthUser? {
        if (!preferences.getBoolean(KEY_LOGGED_IN, false)) return null
        if (accessToken().isNullOrBlank() && refreshToken().isNullOrBlank()) return null
        return readStoredUser()
    }

    suspend fun registerWithPhone(phone: String, password: String, inviteCode: String = ""): AuthResult {
        val normalizedPhone = phone.trim()
        val validationError = validatePhoneAndPassword(normalizedPhone, password)
        if (validationError != null) return AuthResult(error = validationError)
        return authenticate {
            api.register(normalizedPhone, password, deviceId(), inviteCode)
        }
    }

    suspend fun loginWithPhone(phone: String, password: String): AuthResult {
        val normalizedPhone = phone.trim()
        if (!normalizedPhone.matches(PHONE_PATTERN) || password.isEmpty()) {
            return AuthResult(error = "请输入有效手机号和密码")
        }
        return authenticate {
            api.login(normalizedPhone, password, deviceId())
        }
    }

    suspend fun initializeApp(gameId: Int): BootstrapResult = try {
        scheduleImpressions()
        scheduleRewardCompletions()
        BootstrapResult(bootstrap = authenticated { api.bootstrap(it, deviceId(), gameId) })
    } catch (error: UserApiException) {
        bootstrapFailure(error).copy(sessionInvalid = currentUser() == null)
    } catch (error: IOException) {
        BootstrapResult(error = "初始化服务连接失败，请稍后重试")
    } catch (error: CancellationException) {
        throw error
    } catch (_: Exception) {
        BootstrapResult(error = "服务器返回了无法识别的初始化数据")
    }

    /** Game selection comes from the authenticated account returned by the server. */
    fun serverGameId(): Int? = preferences.getInt(KEY_GAME_ID, 0).takeIf { it > 0 }

    suspend fun walletBalance(): java.math.BigDecimal {
        scheduleRewardCompletions()
        scheduleImpressions()
        return authenticated { token -> api.wallet(token, deviceId()) }
    }

    suspend fun adHistory(gameId: Int): List<AdHistoryRecord> {
        return authenticated { token -> api.adHistory(token, deviceId(), gameId) }
    }

    suspend fun alipayAccount(): AlipayAccount {
        return authenticated { token -> api.getAlipay(token, deviceId()) }
    }

    suspend fun bindAlipay(account: String, realName: String, currentPassword: String): AlipayAccount {
        return authenticated { token -> api.bindAlipay(token, deviceId(), account, realName, currentPassword) }
    }

    suspend fun withdrawalOptions(gameId: Int): WithdrawalAvailability {
        return authenticated { token -> api.withdrawalOptions(token, deviceId(), gameId) }
    }

    suspend fun createWithdrawal(gameId: Int, amountCents: Long, requestKey: String): WithdrawalRecord {
        return authenticated { token -> api.createWithdrawal(token, deviceId(), gameId, amountCents, requestKey) }
    }

    suspend fun withdrawals(): List<WithdrawalRecord> {
        return authenticated { token -> api.withdrawals(token, deviceId()) }
    }

    suspend fun requestAd(gameId: Int, placement: String, adType: String): AdSession? {
        return authenticated { token -> api.requestAd(token, deviceId(), gameId, placement, adType) }
    }

    suspend fun deviceRiskConfig(gameId: Int): DeviceRiskConfig {
        return authenticated { token -> api.deviceRiskConfig(token, deviceId(), gameId) }
    }

    suspend fun deviceRiskChallenge(gameId: Int): DeviceRiskChallenge {
        return authenticated { token -> api.deviceRiskChallenge(token, deviceId(), gameId, deviceId()) }
    }

    suspend fun deviceRiskVerify(challengeId: String, aliyunDeviceToken: String): DeviceRiskVerification {
        return authenticated { token -> api.deviceRiskVerify(token, deviceId(), challengeId, aliyunDeviceToken) }
    }

    suspend fun requestAd(
        gameId: Int,
        placement: String,
        adType: String,
        riskCheckId: String?
    ): AdSession? {
        return authenticated { token -> api.requestAd(token, deviceId(), gameId, placement, adType, riskCheckId) }
    }

    suspend fun adImpression(session: AdSession) {
        val epoch = sessions.snapshot()
        sessions.withCurrent(epoch) {
            val record = JSONObject().put("id", session.id).put("token", session.sessionToken)
                .put("created", System.currentTimeMillis())
            check(preferences.edit().putString("pending_impression_" + session.id, record.toString()).commit())
        }
        scheduleImpressions()
    }

    private fun scheduleImpressions() {
        val epoch = sessions.snapshot()
        impressionWorker.schedule { withTimeoutOrNull(45_000) { retryImpressions(epoch) } }
    }

    private suspend fun retryImpressions(epoch: Long) {
        val entries = sessions.withCurrent(epoch) { preferences.all.filterKeys { it.startsWith("pending_impression_") }.toList().take(20) }
        for ((key, raw) in entries) {
            val record = JSONObject(raw as String)
            var done = System.currentTimeMillis() - record.getLong("created") >= 24 * 60 * 60 * 1000L
            if (!done) try {
                authenticatedInSession(epoch) { token -> api.requestJson("POST",
                    "ads/${record.getString("id")}/impression", deviceId(), token, JSONObject()
                        .put("session_token", record.getString("token"))
                        .put("event_id", "imp-${record.getString("id")}")) }
                done = true
            } catch (e: CancellationException) { throw e }
            catch (e: UserApiException) {
                done = e.statusCode in listOf(404, 409, 422)
                if (!done) return
            }
            catch (_: IOException) { return }
            if (done) sessions.withCurrent(epoch) { preferences.edit().remove(key).commit() }
        }
    }

    private fun scheduleRewardCompletions() {
        val epoch = sessions.snapshot()
        rewardWorker.schedule { retryRewardCompletions(epoch) }
    }

    private suspend fun retryRewardCompletions(epoch: Long) {
        var backoffMs = 1_000L
        while (true) {
            val userId = sessions.withCurrent(epoch) { currentUser()?.id } ?: return
            val entries = sessions.withCurrent(epoch) {
                preferences.all.filterKeys { it.startsWith(PENDING_REWARD_PREFIX) }.toList().take(30)
            }
            if (entries.isEmpty()) return
            var retryLater = false
            for ((key, raw) in entries) {
                val record = runCatching { JSONObject(raw as String) }.getOrNull() ?: continue
                if (record.optString("member_id") != userId) continue
                val created = record.optLong("created", 0)
                if (created <= 0) continue
                if (System.currentTimeMillis() - created > 7 * 24 * 60 * 60 * 1000L) {
                    sessions.withCurrent(epoch) { preferences.edit().remove(key).commit() }
                    continue
                }
                try {
                    val result = try {
                        authenticatedInSession(epoch) { token -> api.adComplete(token, deviceId(),
                            record.getString("id"), record.getString("token"), record.getString("event_id"),
                            record.optInt("seconds", 0), record.optString("e_c"),
                            record.optString("e_c_cny"), record.optString("s_id"),
                            record.optString("sdk_request_id"), record.optString("sdk_show_id"),
                            record.optString("source_id")) }
                    } catch (error: IOException) {
                        if (error is UserApiException) throw error
                        authenticatedInSession(epoch) { token -> api.adComplete(token, deviceId(),
                            record.getString("id"), record.getString("token"), record.getString("event_id"),
                            record.optInt("seconds", 0), record.optString("e_c"),
                            record.optString("e_c_cny"), record.optString("s_id"),
                            record.optString("sdk_request_id"), record.optString("sdk_show_id"),
                            record.optString("source_id")) }
                    }
                    if (result.optJSONObject("data")?.optBoolean("rewarded", false) == true) {
                        sessions.withCurrent(epoch) { preferences.edit().remove(key).commit() }
                    } else {
                        retryLater = true
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: UserApiException) {
                    if (error.statusCode in listOf(404, 409, 422)) {
                        sessions.withCurrent(epoch) { preferences.edit().remove(key).commit() }
                        continue
                    }
                    retryLater = true
                    break
                } catch (_: IOException) {
                    retryLater = true
                    break
                }
            }
            if (!retryLater) return
            delay(backoffMs)
            backoffMs = (backoffMs * 2).coerceAtMost(60_000L)
        }
    }

    private fun pendingRewardKey(sessionId: String) = PENDING_REWARD_PREFIX + sessionId

    suspend fun adComplete(
        session: AdSession,
        watchedSeconds: Int,
        rewardEvidence: JSONObject
    ): JSONObject {
        val epoch = sessions.snapshot()
        val userId = currentUser()?.id ?: throw UserApiException(401, "SESSION_EXPIRED", "Please sign in again")
        val key = pendingRewardKey(session.id)
        val record = JSONObject().put("id", session.id).put("token", session.sessionToken)
            .put("seconds", watchedSeconds).put("event_id", "complete-${session.id}")
            .put("member_id", userId).put("created", System.currentTimeMillis())
        listOf("e_c", "e_c_cny", "s_id", "sdk_request_id", "sdk_show_id", "source_id").forEach { key ->
            if (rewardEvidence.has(key) && !rewardEvidence.isNull(key)) record.put(key, rewardEvidence.get(key))
        }
        sessions.withCurrent(epoch) {
            check(preferences.edit().putString(key, record.toString()).commit()) {
                "无法保存奖励补发记录，奖励将保持待确认状态"
            }
        }
        scheduleRewardCompletions()
        return try {
            var result = try {
                authenticatedInSession(epoch) { token ->
                    api.adComplete(token, deviceId(), session, watchedSeconds, rewardEvidence)
                }
            } catch (error: IOException) {
                if (error is UserApiException) throw error
                authenticatedInSession(epoch) { token ->
                    api.adComplete(token, deviceId(), session, watchedSeconds, rewardEvidence)
                }
            }
            if (result.optJSONObject("data")?.optBoolean("rewarded", false) == true) {
                sessions.withCurrent(epoch) { preferences.edit().remove(key).commit() }
            } else {
                scheduleRewardCompletions()
            }
            result
        } catch (error: CancellationException) {
            throw error
        } catch (error: UserApiException) {
            if (error.statusCode in listOf(404, 409, 422)) {
                sessions.withCurrent(epoch) { preferences.edit().remove(key).commit() }
            }
            throw error
        } catch (error: IOException) {
            scheduleRewardCompletions()
            JSONObject().put("data", JSONObject().put("status", "queued")
                .put("rewarded", false).put("ad_session_id", session.id))
        }
    }

    suspend fun adFail(session: AdSession, reason: String) {
        return authenticated { token -> api.adFail(token, deviceId(), session, reason) }
    }

    suspend fun restoreSession(): AuthUser? {
        val epoch = sessions.snapshot()
        val cached = currentUser()
        if (accessToken() == null && refreshToken() == null) return null
        return try {
            val user = authenticatedInSession(epoch) { api.me(it, deviceId()).toAuthUser() }
            sessions.withCurrent(epoch) { saveUser(user) }
            scheduleRewardCompletions()
            user
        } catch (error: CancellationException) {
            throw error
        } catch (error: UserApiException) {
            sessions.withCurrent(epoch) {
                if (error.statusCode == 403 && error.errorCode in listOf("DEVICE_COOLDOWN", "RECOVERY_ONLY")) cached
                else if (error.statusCode in listOf(401, 403, 404)) {
                    sessions.replace { clearSession() }
                    null
                } else cached
            }
        } catch (_: Exception) {
            sessions.withCurrent(epoch) { cached }
        }
    }

    /** Invalidate locally immediately; remote revocation always uses the old credentials. */
    fun prepareLogout(): suspend () -> Unit {
        val credentials = sessions.replace {
            val old = accessToken() to refreshToken()
            clearSession()
            old
        }
        return {
            try {
                credentials.first?.let { api.logout(it, credentials.second, deviceId()) }
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                // Local logout already completed.
            }
        }
    }

    suspend fun logout() = prepareLogout().invoke()

    private suspend fun authenticate(sms: Boolean = false, request: suspend () -> UserApiSession): AuthResult {
        val epoch = sessions.replace { clearSession(); sessions.snapshot() }
        return try {
            val session = request()
            val user = session.user?.toAuthUser()
                ?: api.me(session.accessToken, deviceId()).toAuthUser()
            sessions.withCurrent(epoch) { saveTokens(session); saveUser(user) }
            scheduleRewardCompletions()
            AuthResult(user = user)
        } catch (error: UserApiException) {
            sessions.withCurrent(epoch) { AuthResult(error = if (sms && error.statusCode == 401)
                "验证码错误、已过期或已使用，请检查后重试" else readableError(error)) }
        } catch (error: IOException) {
            sessions.withCurrent(epoch) { AuthResult(error = "网络连接失败，请检查网络后重试") }
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            sessions.withCurrent(epoch) { AuthResult(error = "服务器返回了无法识别的数据，请稍后重试") }
        }
    }

    private fun readableError(error: UserApiException): String = when {
        error.errorCode == "USERNAME_EXISTS" || error.statusCode == 409 ->
            "该手机号已经注册，请直接登录"
        error.errorCode == "PASSWORD_WEAK" || error.statusCode == 422 ->
            "密码至少 8 位，并同时包含字母和数字"
        error.errorCode == "ACCOUNT_DISABLED" -> "账号已停用，请联系管理员"
        error.errorCode == "DEVICE_BLOCKED" -> "当前设备不可用，请联系管理员"
        error.statusCode == 401 -> "手机号或密码不正确"
        error.statusCode == 429 -> "请求太频繁，请稍后再试"
        error.statusCode == 503 -> "服务暂时不可用，请稍后重试"
        else -> error.message.ifBlank { "登录失败，请稍后重试" }
    }

    private fun bootstrapFailure(error: UserApiException): BootstrapResult =
        BootstrapResult(
            error = when {
                error.errorCode == "ACCOUNT_DISABLED" -> "账号已停用，请联系管理员"
                error.errorCode == "DEVICE_BLOCKED" -> "当前设备不可用，请联系管理员"
                error.statusCode == 403 -> "当前账号或设备不可用"
                error.statusCode == 404 -> "游戏初始化接口或配置不存在"
                error.statusCode == 429 -> "初始化请求太频繁，请稍后再试"
                error.statusCode == 503 -> "初始化服务暂时不可用，请稍后重试"
                else -> error.message.ifBlank { "应用初始化失败，请稍后重试" }
            },
            sessionInvalid = error.statusCode == 403
        )

    private fun saveTokens(session: UserApiSession) {
        preferences.edit()
            .putBoolean(KEY_LOGGED_IN, true)
            .putString(KEY_ACCESS_TOKEN, session.accessToken)
            .putString(KEY_REFRESH_TOKEN, session.refreshToken)
            .putLong(KEY_EXPIRES_AT, System.currentTimeMillis() + session.expiresInSeconds * 1000L)
            .apply {
                session.user?.gameId?.let { putInt(KEY_GAME_ID, it) }
            }
            .apply()
    }

    private fun saveUser(user: AuthUser) {
        preferences.edit()
            .putBoolean(KEY_LOGGED_IN, true)
            .putString(KEY_USER_ID, user.id)
            .putString(KEY_USER_NAME, user.displayName)
            .putString(KEY_USER_LABEL, user.accountLabel)
            .putString(KEY_PROVIDER, user.provider.name)
            .apply()
    }

    private fun readStoredUser(): AuthUser? {
        val id = preferences.getString(KEY_USER_ID, null) ?: return null
        val name = preferences.getString(KEY_USER_NAME, null) ?: "成语学习者"
        val label = preferences.getString(KEY_USER_LABEL, null) ?: ""
        val provider = preferences.getString(KEY_PROVIDER, AuthProvider.PHONE.name)
            ?.let { runCatching { AuthProvider.valueOf(it) }.getOrDefault(AuthProvider.PHONE) }
            ?: AuthProvider.PHONE
        return AuthUser(id, name, label, provider)
    }

    private fun clearSession() {
        impressionWorker.cancel()
        rewardWorker.cancel()
        val pending = preferences.edit().remove("pending_campaign")
        preferences.all.keys.filter { it.startsWith("pending_impression_") }.forEach { pending.remove(it) }
        pending.commit()
        preferences.edit()
            .putBoolean(KEY_LOGGED_IN, false)
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_EXPIRES_AT)
            .remove(KEY_USER_ID)
            .remove(KEY_USER_NAME)
            .remove(KEY_USER_LABEL)
            .remove(KEY_PROVIDER)
            .remove(KEY_GAME_ID)
            .apply()
    }

    private fun accessToken(): String? = preferences.getString(KEY_ACCESS_TOKEN, null)

    private fun refreshToken(): String? = preferences.getString(KEY_REFRESH_TOKEN, null)

    private fun deviceId(): String {
        preferences.getString(KEY_DEVICE_ID, null)?.let { return it }
        return UUID.randomUUID().toString().also { generated ->
            preferences.edit().putString(KEY_DEVICE_ID, generated).apply()
        }
    }

    private fun UserApiUser.toAuthUser(): AuthUser {
        val account = username.ifBlank { id }
        val displayName = name.ifBlank { "成语学习者" }
        return AuthUser(
            id = id,
            displayName = displayName,
            accountLabel = if (account.matches(PHONE_PATTERN)) maskPhone(account) else account,
            provider = if (username.startsWith("wx_")) AuthProvider.WECHAT else AuthProvider.PHONE
        )
    }

    private fun maskPhone(phone: String): String =
        "${phone.take(3)}****${phone.takeLast(4)}"

    companion object {
        internal val campaignRequests = CampaignRequests()
        private val impressionWorker = BackgroundRetry(CoroutineScope(SupervisorJob() + Dispatchers.IO))
        private val rewardWorker = BackgroundRetry(CoroutineScope(SupervisorJob() + Dispatchers.IO), cooldownMs = 1_000)
        private const val PENDING_REWARD_PREFIX = "pending_reward_"
        // Both the quiz and member screens share rotating refresh credentials.
        private val refreshMutex = Mutex()
        private val sessions = SessionFence()
        private const val KEY_LOGGED_IN = "logged_in"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_EXPIRES_AT = "expires_at"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_USER_NAME = "user_name"
        private const val KEY_USER_LABEL = "user_label"
        private const val KEY_PROVIDER = "provider"
        private const val KEY_GAME_ID = "game_id"
        private val PHONE_PATTERN = Regex("1[3-9]\\d{9}")

        fun validatePhoneAndPassword(phone: String, password: String): String? {
            if (!phone.matches(PHONE_PATTERN)) return "请输入有效的 11 位手机号"
            if (password.length < 8 || !password.any(Char::isLetter) || !password.any(Char::isDigit)) {
                return "密码至少 8 位，并同时包含字母和数字"
            }
            return null
        }
    }
}
