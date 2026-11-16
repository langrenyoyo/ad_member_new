package com.example.idiomquiz

import com.example.idiomquiz.ui.invitationUrl
import com.example.idiomquiz.ui.invitationQrMatrix
import com.google.zxing.BinaryBitmap
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import org.junit.Assert.assertEquals
import org.junit.Test

class InvitationLinkTest {
    @Test fun urlCarriesGameAndInviteAndDoesNotLinkDirectlyToApk() {
        assertEquals("https://example.com/invite.html?game_id=238&invite_code=A1B2C3",
            invitationUrl("https://example.com/api/app/v1/", 238, "A1B2C3"))
        assertEquals("http://127.0.0.1:18080/invite.html?game_id=238&invite_code=A1B2C3",
            invitationUrl("http://127.0.0.1:18080/api/app/v1/", 238, "A1B2C3"))
    }
    @Test fun displayedQrDecodesToTheSameBrowserInvitation() {
        val url = invitationUrl("https://admember.yunjizhilian.asia/api/app/v1/", 238, "C0T3SO")
        val matrix = invitationQrMatrix(url)
        val pixels = IntArray(matrix.width * matrix.height) { i ->
            if (matrix[i % matrix.width, i / matrix.width]) 0xff000000.toInt() else 0xffffffff.toInt()
        }
        val source = RGBLuminanceSource(matrix.width, matrix.height, pixels)
        assertEquals(url, MultiFormatReader().decode(BinaryBitmap(HybridBinarizer(source))).text)
    }
    @Test(expected = IllegalArgumentException::class)
    fun rejectsUrlInjectionInInvite() { invitationUrl("https://example.com/api/", 238, "A1&x=1") }
}
