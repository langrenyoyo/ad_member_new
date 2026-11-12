package com.example.idiomquiz

import com.example.idiomquiz.data.AuthRepository
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AuthRepositoryTest {
    @Test
    fun validatesPhoneAndPassword() {
        assertEquals(
            "请输入有效的 11 位手机号",
            AuthRepository.validatePhoneAndPassword("1380013800", "123456")
        )
        assertEquals(
            "密码至少 8 位，并同时包含字母和数字",
            AuthRepository.validatePhoneAndPassword("13800138000", "123456")
        )
        assertNull(AuthRepository.validatePhoneAndPassword("13800138000", "abc12345"))
    }
}
