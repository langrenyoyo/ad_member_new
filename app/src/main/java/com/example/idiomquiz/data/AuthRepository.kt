package com.example.idiomquiz.data

import android.content.Context
import kotlinx.coroutines.CancellationException
import java.io.IOException
import java.util.UUID
import org.json.JSONObject

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

    fun currentUser(): AuthUser? {
        if (!preferences.getBoolean(KEY_LOGGED_IN, false)) return null
        if (accessToken().isNullOrBlank() && refreshToken().isNullOrBlank()) return null
        return readStoredUser()
    }

    suspend fun registerWithPhone(phone: String, password: String): AuthResult {
        val normalizedPhone = phone.trim()
        val validationError = validatePhoneAndPassword(normalizedPhone, password)
        if (validationError != null) return AuthResult(error = validationError)
        return authenticate {
            api.register(normalizedPhone, password, deviceId())
        }
    }

    suspend fun loginWithPhone(phone: String, password: String): AuthResult {
        val normalizedPhone = phone.trim()
        val validationError = validatePhoneAndPassword(normalizedPhone, password)
        if (validationError != null) return AuthResult(error = validationError)
        return authenticate {
            api.login(normalizedPhone, password, deviceId())
        }
    }

    suspend fun initializeApp(gameId: Int): BootstrapResult {
        val accessToken = accessToken()
        if (accessToken.isNullOrBlank()) {
            return BootstrapResult(error = "请先登录后再初始化应用")
        }
        val deviceId = deviceId()
        return try {
            BootstrapResult(bootstrap = api.bootstrap(accessToken, deviceId, gameId))
        } catch (error: UserApiException) {
            if (error.statusCode != 401) {
                if (error.statusCode == 403) clearSession()
                return bootstrapFailure(error)
            }
            refreshAndBootstrap(gameId, deviceId)
        } catch (error: IOException) {
            BootstrapResult(error = "初始化服务连接失败，请稍后重试")
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            BootstrapResult(error = "服务器返回了无法识别的初始化数据")
        }
    }

    suspend fun walletBalance(): Long {
        val token = accessToken() ?: error("请先登录后再获取金币余额")
        return api.wallet(token, deviceId())
    }

    suspend fun adHistory(gameId: Int): List<AdHistoryRecord> {
        val token = accessToken() ?: error("请先登录后再查看广告记录")
        return api.adHistory(token, deviceId(), gameId)
    }

    suspend fun requestAd(gameId: Int, placement: String, adType: String): AdSession? {
        val token = accessToken() ?: return null
        return api.requestAd(token, deviceId(), gameId, placement, adType)
    }

    suspend fun adImpression(session: AdSession) {
        val token = accessToken() ?: return
        api.adImpression(token, deviceId(), session)
    }

    suspend fun adComplete(session: AdSession, watchedSeconds: Int): JSONObject {
        val token = accessToken() ?: return org.json.JSONObject()
        return api.adComplete(token, deviceId(), session, watchedSeconds)
    }

    suspend fun adFail(session: AdSession, reason: String) {
        val token = accessToken() ?: return
        api.adFail(token, deviceId(), session, reason)
    }

    /** The user API document does not define a WeChat authorization endpoint yet. */
    fun loginWithWeChat(): AuthResult = AuthResult(
        error = "用户接口暂未提供微信登录，请先使用手机号和密码登录"
    )

    suspend fun restoreSession(): AuthUser? {
        val cachedUser = currentUser()
        val accessToken = accessToken()
        val refreshToken = refreshToken()
        if (accessToken.isNullOrBlank() && refreshToken.isNullOrBlank()) {
            clearSession()
            return null
        }

        if (!accessToken.isNullOrBlank()) {
            try {
                val user = api.me(accessToken, deviceId()).toAuthUser()
                saveUser(user)
                return user
            } catch (error: UserApiException) {
                if (error.statusCode != 401) {
                    if (error.statusCode in listOf(403, 404)) clearSession()
                    return cachedUser
                }
            } catch (error: IOException) {
                return cachedUser
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                return cachedUser
            }
        }

        if (refreshToken.isNullOrBlank()) {
            clearSession()
            return null
        }

        return try {
            val session = api.refresh(refreshToken, deviceId())
            saveTokens(session)
            val user = session.user?.toAuthUser()
                ?: api.me(session.accessToken, deviceId()).toAuthUser()
            saveUser(user)
            user
        } catch (error: UserApiException) {
            if (error.statusCode == 401 || error.statusCode == 403 || error.statusCode == 404) {
                clearSession()
                null
            } else {
                cachedUser
            }
        } catch (error: IOException) {
            cachedUser
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            cachedUser
        }
    }

    suspend fun logout() {
        val accessToken = accessToken()
        val refreshToken = refreshToken()
        try {
            if (!accessToken.isNullOrBlank()) {
                api.logout(accessToken, refreshToken, deviceId())
            }
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            // The local session must still be removed when the network is unavailable.
        } finally {
            clearSession()
        }
    }

    private suspend fun authenticate(request: suspend () -> UserApiSession): AuthResult = try {
        val session = request()
        saveTokens(session)
        val user = session.user?.toAuthUser()
            ?: api.me(session.accessToken, deviceId()).toAuthUser()
        saveUser(user)
        AuthResult(user = user)
    } catch (error: UserApiException) {
        AuthResult(error = readableError(error))
    } catch (error: IOException) {
        AuthResult(error = "网络连接失败，请检查网络后重试")
    } catch (error: CancellationException) {
        throw error
    } catch (_: Exception) {
        AuthResult(error = "服务器返回了无法识别的数据，请稍后重试")
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

    private suspend fun refreshAndBootstrap(gameId: Int, deviceId: String): BootstrapResult {
        val refreshToken = refreshToken() ?: run {
            clearSession()
            return BootstrapResult(error = "登录凭证已失效，请重新登录", sessionInvalid = true)
        }
        return try {
            val session = api.refresh(refreshToken, deviceId)
            saveTokens(session)
            BootstrapResult(bootstrap = api.bootstrap(session.accessToken, deviceId, gameId))
        } catch (error: UserApiException) {
            if (error.statusCode == 401 || error.statusCode == 403) {
                clearSession()
                bootstrapFailure(error).copy(
                    error = "登录凭证已失效，请重新登录",
                    sessionInvalid = true
                )
            } else {
                bootstrapFailure(error)
            }
        } catch (error: IOException) {
            BootstrapResult(error = "初始化服务连接失败，请稍后重试")
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            BootstrapResult(error = "服务器返回了无法识别的初始化数据")
        }
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
        preferences.edit()
            .putBoolean(KEY_LOGGED_IN, false)
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_EXPIRES_AT)
            .remove(KEY_USER_ID)
            .remove(KEY_USER_NAME)
            .remove(KEY_USER_LABEL)
            .remove(KEY_PROVIDER)
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
            provider = AuthProvider.PHONE
        )
    }

    private fun maskPhone(phone: String): String =
        "${phone.take(3)}****${phone.takeLast(4)}"

    companion object {
        private const val KEY_LOGGED_IN = "logged_in"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_EXPIRES_AT = "expires_at"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_USER_NAME = "user_name"
        private const val KEY_USER_LABEL = "user_label"
        private const val KEY_PROVIDER = "provider"
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
