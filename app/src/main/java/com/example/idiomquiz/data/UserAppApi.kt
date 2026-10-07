package com.example.idiomquiz.data

import com.example.idiomquiz.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import com.example.idiomquiz.security.SecurityGuard

internal data class UserApiUser(
    val id: String,
    val username: String,
    val name: String,
    val imageUrl: String? = null,
    val gameId: Int? = null
)

internal data class UserApiSession(
    val user: UserApiUser?,
    val accessToken: String,
    val refreshToken: String,
    val expiresInSeconds: Long
)

data class AdSession(
    val id: String, val requestId: String, val adUnitId: String,
    val sessionToken: String, val rewardEnabled: Boolean, val rewardCoin: Long,
    val expiresAtEpochMillis: Long?,
    val takuUserId: String?,
    val takuExtraData: Any?
)

data class DeviceRiskConfig(
    val enabled: Boolean,
    val limitEnabled: Boolean,
    val dailyLimit: Int
)

data class DeviceRiskChallenge(
    val challengeId: String,
    val bizId: String,
    val expiresAt: String?
)

data class DeviceRiskVerification(
    val riskCheckId: String,
    val limited: Boolean,
    val remaining: Int?
)

data class AlipayAccount(
    val bound: Boolean,
    val accountMasked: String?,
    val realNameMasked: String?,
    val identityVerified: Boolean
)

data class WithdrawalOption(
    val id: String,
    val amountCents: Long,
    val coin: Long,
    val title: String
)

data class WithdrawalRecord(
    val id: String,
    val amountCents: Long,
    val coin: Long,
    val state: String,
    val createdAt: String,
    val payoutState: String?
)

data class AdHistoryRecord(
    val id: String,
    val placement: String,
    val adType: String,
    val status: String,
    val coinAdded: Long,
    val watchedAt: String?,
    val createdAt: String
)

internal class UserApiException(
    val statusCode: Int,
    val errorCode: String? = null,
    override val message: String
) : IOException(message)

internal class UserAppApi(context: android.content.Context) {
    private val appContext = context.applicationContext
    suspend fun register(username: String, password: String, deviceId: String): UserApiSession =
        requestJson(
            method = "POST",
            path = "auth/register",
            deviceId = deviceId,
            body = credentialsBody(username, password, deviceId)
        ).toSession()

    suspend fun login(username: String, password: String, deviceId: String): UserApiSession =
        requestJson(
            method = "POST",
            path = "auth/login",
            deviceId = deviceId,
            body = credentialsBody(username, password, deviceId)
        ).toSession()

    suspend fun refresh(refreshToken: String, deviceId: String): UserApiSession =
        requestJson(
            method = "POST",
            path = "auth/refresh",
            deviceId = deviceId,
            body = JSONObject()
                .put("refresh_token", refreshToken)
                .put("device_id", deviceId)
        ).toSession()

    suspend fun me(accessToken: String, deviceId: String): UserApiUser =
        requestJson(
            method = "GET",
            path = "me",
            deviceId = deviceId,
            accessToken = accessToken
        ).toUser()

    suspend fun bootstrap(accessToken: String, deviceId: String, gameId: Int): AppBootstrap =
        requestJson(
            method = "GET",
            path = "bootstrap?game_id=$gameId",
            deviceId = deviceId,
            accessToken = accessToken
        ).toBootstrap()

    suspend fun wallet(accessToken: String, deviceId: String): Long {
        val data = requestJson(
            method = "GET",
            path = "wallet",
            deviceId = deviceId,
            accessToken = accessToken
        ).optJSONObject("data")
        return data?.optLong("coin") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回金币余额")
    }

    suspend fun logout(accessToken: String, refreshToken: String?, deviceId: String) {
        requestJson(
            method = "POST",
            path = "auth/logout",
            deviceId = deviceId,
            accessToken = accessToken,
            body = JSONObject().apply {
                if (!refreshToken.isNullOrBlank()) put("refresh_token", refreshToken)
            }
        )
    }

    suspend fun deviceRiskConfig(accessToken: String, deviceId: String, gameId: Int): DeviceRiskConfig {
        val data = requestJson("GET", "device-risk/config?game_id=$gameId", deviceId, accessToken)
            .optJSONObject("data") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回设备风控配置")
        return DeviceRiskConfig(
            enabled = data.booleanOrFalse("enabled"),
            limitEnabled = data.booleanOrFalse("limit_enabled"),
            dailyLimit = data.optInt("daily_limit", 0)
        )
    }

    suspend fun deviceRiskChallenge(
        accessToken: String,
        deviceId: String,
        gameId: Int,
        installId: String
    ): DeviceRiskChallenge {
        val data = requestJson(
            "POST", "device-risk/challenge", deviceId, accessToken,
            JSONObject().put("game_id", gameId).put("install_id", installId)
        ).optJSONObject("data") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回设备风控挑战")
        return DeviceRiskChallenge(
            challengeId = data.stringOrNull("challenge_id") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回挑战 ID"),
            bizId = data.stringOrNull("biz_id") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回业务 ID"),
            expiresAt = data.stringOrNull("expires_at")
        )
    }

    suspend fun deviceRiskVerify(
        accessToken: String,
        deviceId: String,
        challengeId: String,
        aliyunDeviceToken: String
    ): DeviceRiskVerification {
        val data = requestJson(
            "POST", "device-risk/verify", deviceId, accessToken,
            JSONObject().put("challenge_id", challengeId).put("aliyun_device_token", aliyunDeviceToken)
        ).optJSONObject("data") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回设备风控校验结果")
        return DeviceRiskVerification(
            riskCheckId = data.stringOrNull("risk_check_id") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回风控校验凭证"),
            limited = data.booleanOrFalse("limited"),
            remaining = if (data.isNull("remaining")) null else data.optInt("remaining")
        )
    }

    suspend fun getAlipay(accessToken: String, deviceId: String): AlipayAccount {
        val data = requestJson("GET", "me/alipay", deviceId, accessToken).optJSONObject("data") ?: JSONObject()
        return AlipayAccount(
            bound = data.booleanOrFalse("bound") || !data.stringOrNull("account").isNullOrBlank(),
            accountMasked = data.stringOrNull("account") ?: data.stringOrNull("account_masked"),
            realNameMasked = data.stringOrNull("real_name") ?: data.stringOrNull("real_name_masked"),
            identityVerified = data.booleanOrFalse("identity_verified")
        )
    }

    suspend fun bindAlipay(accessToken: String, deviceId: String, account: String, realName: String, currentPassword: String): AlipayAccount {
        val data = requestJson(
            "PUT", "me/alipay", deviceId, accessToken,
            JSONObject().put("account", account).put("real_name", realName).put("current_password", currentPassword)
        ).optJSONObject("data") ?: JSONObject()
        return AlipayAccount(
            bound = true,
            accountMasked = data.stringOrNull("account") ?: data.stringOrNull("account_masked") ?: account,
            realNameMasked = data.stringOrNull("real_name") ?: data.stringOrNull("real_name_masked") ?: realName,
            identityVerified = data.booleanOrFalse("identity_verified")
        )
    }

    suspend fun withdrawalOptions(accessToken: String, deviceId: String, gameId: Int): List<WithdrawalOption> {
        val data = requestJson("GET", "withdrawal-options?game_id=$gameId", deviceId, accessToken).optJSONObject("data") ?: return emptyList()
        val items = data.optJSONArray("items") ?: data.optJSONArray("options") ?: return emptyList()
        return buildList {
            for (index in 0 until items.length()) {
                val item = items.optJSONObject(index) ?: continue
                val amount = item.optLong("amount_cents", item.optLong("amount", 0L))
                val coin = item.optLong("coin", item.optLong("tixian_coin", 0L))
                add(WithdrawalOption(item.opt("id").toString(), amount, coin, item.stringOrNull("title") ?: "提现 ${amount / 100.0} 元"))
            }
        }
    }

    suspend fun createWithdrawal(accessToken: String, deviceId: String, gameId: Int, amountCents: Long, requestKey: String): WithdrawalRecord {
        val data = requestJson(
            "POST", "withdrawals", deviceId, accessToken,
            JSONObject().put("request_key", requestKey).put("game_id", gameId).put("amount_cents", amountCents)
        ).optJSONObject("data") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回提现结果")
        return data.toWithdrawalRecord()
    }

    suspend fun withdrawals(accessToken: String, deviceId: String): List<WithdrawalRecord> {
        val data = requestJson("GET", "withdrawals?limit=20&offset=0", deviceId, accessToken).optJSONObject("data") ?: return emptyList()
        val items = data.optJSONArray("items") ?: return emptyList()
        return buildList {
            for (index in 0 until items.length()) items.optJSONObject(index)?.let { add(it.toWithdrawalRecord()) }
        }
    }

    private fun JSONObject.toWithdrawalRecord(): WithdrawalRecord {
        val payout = optJSONObject("payout")
        return WithdrawalRecord(
            id = opt("id").toString(),
            amountCents = optLong("amount_cents", optLong("amount", 0L)),
            coin = optLong("coin", optLong("coin_amount", 0L)),
            state = stringOrNull("status") ?: stringOrNull("state") ?: "unknown",
            createdAt = stringOrNull("created_at").orEmpty(),
            payoutState = payout?.stringOrNull("state")
        )
    }

    suspend fun requestAd(
        accessToken: String,
        deviceId: String,
        gameId: Int,
        placement: String,
        adType: String,
        riskCheckId: String? = null,
        clientRequestId: String = "android-${System.currentTimeMillis()}"
    ): AdSession =
        requestJson("POST", "ads/request", deviceId, accessToken, JSONObject()
            .put("game_id", gameId).put("placement", placement).put("ad_type", adType)
            .put("device_id", deviceId).put("client_request_id", clientRequestId)
            .apply { if (!riskCheckId.isNullOrBlank()) put("risk_check_id", riskCheckId) })
            .toAdSession()

    suspend fun adImpression(accessToken: String, deviceId: String, session: AdSession) {
        requestJson("POST", "ads/${session.id}/impression", deviceId, accessToken, JSONObject()
            .put("event_id", "imp-${System.currentTimeMillis()}").put("session_token", session.sessionToken)
            .put("occurred_at", java.time.Instant.now().toString()))
    }

    suspend fun adComplete(
        accessToken: String,
        deviceId: String,
        session: AdSession,
        watchedSeconds: Int,
        userId: String,
        extraData: JSONObject
    ): JSONObject =
        requestJson("POST", "ads/${session.id}/complete", deviceId, accessToken, JSONObject()
            .put("event_id", "complete-${System.currentTimeMillis()}").put("session_token", session.sessionToken)
            .put("provider_event_id", "android-${System.currentTimeMillis()}").put("watched_seconds", watchedSeconds)
            .put("occurred_at", java.time.Instant.now().toString())
            .put("user_id", userId)
            .put("extra_data", extraData))

    suspend fun adFail(accessToken: String, deviceId: String, session: AdSession, reason: String) {
        requestJson("POST", "ads/${session.id}/fail", deviceId, accessToken, JSONObject()
            .put("event_id", "fail-${System.currentTimeMillis()}").put("reason", reason))
    }

    suspend fun adHistory(accessToken: String, deviceId: String, gameId: Int): List<AdHistoryRecord> {
        val data = requestJson(
            "GET",
            "ads/history?game_id=$gameId&limit=50&offset=0",
            deviceId,
            accessToken
        ).optJSONObject("data") ?: return emptyList()
        val items = data.optJSONArray("items") ?: data.optJSONArray("records") ?: return emptyList()
        return buildList {
            for (index in 0 until items.length()) {
                val item = items.optJSONObject(index) ?: continue
                add(
                    AdHistoryRecord(
                        id = item.opt("id").toString(),
                        placement = item.optString("placement"),
                        adType = item.optString("ad_type"),
                        status = item.optString("status"),
                        coinAdded = item.optLong("coin_added", 0L),
                        watchedAt = item.optString("watched_at").takeIf { it.isNotBlank() },
                        createdAt = item.optString("created_at")
                    )
                )
            }
        }
    }

    private suspend fun requestJson(
        method: String,
        path: String,
        deviceId: String,
        accessToken: String? = null,
        body: JSONObject? = null
    ): JSONObject = withContext(Dispatchers.IO) {
        val connection = (URL("$BASE_URL$path").openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            doInput = true
            useCaches = false
            instanceFollowRedirects = true
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("X-App-Id", APP_ID)
            setRequestProperty("X-App-Version", BuildConfig.VERSION_NAME)
            setRequestProperty("X-Platform", "android")
            setRequestProperty("X-Device-Id", deviceId)
            val security = SecurityGuard.evaluate(appContext)
            setRequestProperty("X-Device-Risk", security.headerValue)
            setRequestProperty("X-Device-Blocked", security.blocked.toString())
            if (!accessToken.isNullOrBlank()) {
                setRequestProperty("Authorization", "Bearer $accessToken")
            }
            if (body != null) doOutput = true
        }

        try {
            if (body != null) {
                connection.outputStream.bufferedWriter(Charsets.UTF_8).use { writer ->
                    writer.write(body.toString())
                }
            }

            val statusCode = connection.responseCode
            val responseBody = readBody(connection, statusCode)
            if (statusCode !in 200..299) {
                throw responseError(statusCode, responseBody)
            }
            if (responseBody.isBlank()) JSONObject() else JSONObject(responseBody)
        } finally {
            connection.disconnect()
        }
    }

    private fun credentialsBody(username: String, password: String, deviceId: String): JSONObject =
        JSONObject()
            .put("username", username)
            .put("password", password)
            .put("device_id", deviceId)
            .put("app_id", APP_ID)
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("platform", "android")

    private fun readBody(connection: HttpURLConnection, statusCode: Int): String {
        val stream = if (statusCode in 200..299) {
            connection.inputStream
        } else {
            connection.errorStream
        } ?: return ""
        return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    private fun responseError(statusCode: Int, body: String): UserApiException {
        val root = runCatching { JSONObject(body) }.getOrNull()
        val error = root?.optJSONObject("error")
        val errorCode = error?.stringOrNull("code")
        val detail = root?.opt("detail")?.let { value ->
            when (value) {
                is String -> value
                is JSONObject -> value.optString("msg").takeIf { it.isNotBlank() }
                is org.json.JSONArray -> value.optJSONObject(0)?.optString("msg")?.takeIf { it.isNotBlank() }
                else -> null
            }
        }
        val message = error?.stringOrNull("message") ?: detail
            ?: when (statusCode) {
                401 -> "登录凭证无效或已过期"
                403 -> "账号或设备不可用"
                404 -> "用户接口不存在"
                429 -> "请求太频繁，请稍后再试"
                else -> "服务器请求失败（$statusCode）"
            }
        return UserApiException(statusCode, errorCode, message)
    }

    private fun JSONObject.toSession(): UserApiSession {
        val data = optJSONObject("data") ?: this
        val accessToken = data.stringOrNull("access_token")
            ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回登录凭证")
        val refreshToken = data.stringOrNull("refresh_token")
            ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回刷新凭证")
        val user = data.optJSONObject("user")?.toUser()
        return UserApiSession(
            user = user,
            accessToken = accessToken,
            refreshToken = refreshToken,
            expiresInSeconds = optLongValue(data, "expires_in")
        )
    }

    private fun JSONObject.toUser(): UserApiUser {
        val data = optJSONObject("data") ?: this
        val userObject = data.optJSONObject("user") ?: data
        val id = userObject.stringOrNull("id")
            ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回用户信息")
        return UserApiUser(
            id = id,
            username = userObject.stringOrNull("username") ?: "",
            name = userObject.stringOrNull("name").orEmpty(),
            imageUrl = userObject.stringOrNull("image_url"),
            gameId = userObject.intOrNull("game_id")
        )
    }

    private fun JSONObject.toBootstrap(): AppBootstrap {
        val data = optJSONObject("data") ?: this
        val game = data.optJSONObject("game")
            ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回游戏配置")
        val gameId = game.intOrNull("id")
            ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回游戏 ID")
        val adConfig = data.optJSONObject("ad_config")
        val placements = adConfig?.optJSONArray("placements")?.toAdPlacements().orEmpty()
        val user = data.optJSONObject("user")
        return AppBootstrap(
            userId = user?.stringOrNull("id"),
            username = user?.stringOrNull("username"),
            coin = user?.longOrNull("coin"),
            freezeCoin = user?.longOrNull("freeze_coin"),
            gameId = gameId,
            gameName = game.stringOrNull("name").orEmpty(),
            gameStatus = game.intOrNull("status") ?: 0,
            adStatus = game.intOrNull("ad_status") ?: 0,
            adsEnabled = adConfig?.booleanOrFalse("enabled") ?: false,
            adAppId = adConfig?.stringOrNull("app_id"),
            adAppKey = adConfig?.stringOrNull("app_key"),
            placements = placements,
            serverTime = data.stringOrNull("server_time")
        )
    }

    private fun JSONObject.toAdSession(): AdSession {
        val data = optJSONObject("data") ?: this
        val reward = data.optJSONObject("reward")
        return AdSession(
            id = data.stringOrNull("ad_session_id") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回广告会话"),
            requestId = data.stringOrNull("request_id").orEmpty(),
            adUnitId = data.stringOrNull("ad_unit_id") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回广告位"),
            sessionToken = data.stringOrNull("session_token") ?: throw UserApiException(502, "INVALID_RESPONSE", "服务器未返回广告会话凭证"),
            rewardEnabled = reward?.optBoolean("enabled", false) ?: false,
            rewardCoin = reward?.optLong("coin", 0L) ?: 0L,
            expiresAtEpochMillis = data.stringOrNull("expires_at")?.let {
                runCatching { Instant.parse(it).toEpochMilli() }.getOrNull()
            },
            takuUserId = data.stringOrNull("taku_user_id"),
            takuExtraData = data.opt("taku_extra_data")
                ?.takeIf { it != JSONObject.NULL }
        )
    }

    private fun JSONArray.toAdPlacements(): List<AdPlacement> = buildList {
        for (index in 0 until length()) {
            val placement = optJSONObject(index) ?: continue
            val placementName = placement.stringOrNull("placement") ?: continue
            val adType = placement.stringOrNull("ad_type") ?: continue
            val adUnitId = placement.stringOrNull("ad_unit_id") ?: continue
            add(
                AdPlacement(
                    placement = placementName,
                    adType = adType,
                    adUnitId = adUnitId,
                    cooldownSeconds = placement.longOrNull("cooldown_seconds") ?: 0L,
                    rewardCoin = placement.longOrNull("reward_coin") ?: 0L
                )
            )
        }
    }

    private fun JSONObject.stringOrNull(key: String): String? {
        val value = opt(key)
        return if (value == null || value == JSONObject.NULL) null else value.toString().takeIf { it.isNotBlank() }
    }

    private fun JSONObject.intOrNull(key: String): Int? =
        when (val value = opt(key)) {
            is Number -> value.toInt()
            else -> value?.toString()?.toIntOrNull()
        }

    private fun JSONObject.longOrNull(key: String): Long? =
        when (val value = opt(key)) {
            is Number -> value.toLong()
            else -> value?.toString()?.toLongOrNull()
        }

    private fun JSONObject.booleanOrFalse(key: String): Boolean =
        when (val value = opt(key)) {
            is Boolean -> value
            is Number -> value.toInt() != 0
            else -> value?.toString()?.toBooleanStrictOrNull() ?: false
        }

    private fun optLongValue(json: JSONObject, key: String): Long =
        when (val value = json.opt(key)) {
            is Number -> value.toLong()
            else -> value?.toString()?.toLongOrNull() ?: 0L
        }

    companion object {
        const val BASE_URL = "https://admember.yunjizhilian.asia/api/app/v1/"
        const val APP_ID = "ad-member"
        private const val CONNECT_TIMEOUT_MS = 15_000
        private const val READ_TIMEOUT_MS = 20_000
    }
}
