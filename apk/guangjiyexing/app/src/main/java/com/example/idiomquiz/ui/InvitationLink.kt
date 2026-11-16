package com.example.idiomquiz.ui

import java.net.URI

internal fun invitationUrl(apiBase: String, gameId: Int, code: String): String {
    require(gameId > 0 && Regex("[A-Z0-9]{6}").matches(code))
    val base = URI(apiBase)
    require(base.scheme in listOf("https", "http") && base.host != null)
    return URI(base.scheme, null, base.host, base.port, "/invite.html",
        "game_id=$gameId&invite_code=$code", null).toASCIIString()
}
