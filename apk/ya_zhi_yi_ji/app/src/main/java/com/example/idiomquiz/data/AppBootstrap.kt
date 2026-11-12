package com.example.idiomquiz.data

import java.math.BigDecimal

data class AppBootstrap(
    val userId: String?,
    val username: String?,
    val coin: BigDecimal?,
    val freezeCoin: BigDecimal?,
    val gameId: Int,
    val gameName: String,
    val gameStatus: Int,
    val adStatus: Int,
    val adsEnabled: Boolean,
    val adAppId: String?,
    val adAppKey: String?,
    val placements: List<AdPlacement>,
    val serverTime: String?
) {
    companion object {
        // The current APP configuration is being tested against game_id=238.
        const val DEFAULT_GAME_ID = 238

        // Local ad configuration used for SDK and placement testing when the
        // remote bootstrap configuration cannot load an ad.
        fun localAdTest(): AppBootstrap = AppBootstrap(
            userId = null,
            username = null,
            coin = null,
            freezeCoin = null,
            gameId = DEFAULT_GAME_ID,
            gameName = "鸭只易记",
            gameStatus = 1,
            adStatus = 1,
            adsEnabled = true,
            adAppId = "a699037ab10b8d",
            adAppKey = "a099bd334103ce88aef9025470a783672",
            placements = listOf(
                AdPlacement("native", "native", "b69908e6c8e2e7", 0, BigDecimal.ZERO),
                AdPlacement("rewarded", "rewarded", "b699091dbe11a0", 0, BigDecimal.ZERO),
                AdPlacement("banner", "banner", "b6990935885f50", 0, BigDecimal.ZERO)
            ),
            serverTime = null
        )
    }
}

data class AdPlacement(
    val placement: String,
    val adType: String,
    val adUnitId: String,
    val cooldownSeconds: Long,
    val rewardCoin: BigDecimal
)

data class BootstrapResult(
    val bootstrap: AppBootstrap? = null,
    val error: String? = null,
    val sessionInvalid: Boolean = false
)
