package com.example.idiomquiz.data

import org.json.JSONObject
import java.math.BigDecimal

internal data class MemberPage(val items: List<JSONObject>, val total: Int, val offset: Int) {
    val nextOffset: Int get() = offset + items.size
    val hasMore: Boolean get() = items.isNotEmpty() && nextOffset < total
}

internal fun parseMemberPage(response: JSONObject, offset: Int = 0): MemberPage {
    val data = response.getJSONObject("data")
    val items = data.getJSONArray("items")
    return MemberPage((0 until items.length()).map { items.getJSONObject(it) },
        data.getInt("total"), offset)
}

internal fun moneyInput(value: String): BigDecimal {
    val amount = value.trim().toBigDecimalOrNull()
    require(amount != null && amount.signum() > 0 && amount.scale() <= 2 && amount.precision() <= 12) {
        "请输入大于零、最多两位小数的金额"
    }
    return amount
}

internal fun validateNewPassword(password: String, confirmation: String) {
    require(password.length in 8..128 && password.any { it in 'a'..'z' || it in 'A'..'Z' } && password.any { it in '0'..'9' }) {
        "新密码须为 8～128 位，并包含英文字母和数字"
    }
    require(password == confirmation) { "两次输入的新密码不一致" }
}

internal fun withdrawalStatus(data: JSONObject): String = when (data.optJSONObject("payout")?.optString("state")) {
    "succeeded" -> "已到账"
    "failed" -> "打款失败"
    "rejected" -> "已拒绝"
    "pending_review" -> "待审核"
    "queued" -> "待打款"
    "processing" -> "打款处理中"
    else -> when {
        data.optJSONObject("payout") != null -> "状态待确认"
        data.optInt("status", -1) == 1 && data.optInt("plan_status", 0) == 1 &&
            !data.isNull("transferred_at") && data.optString("transferred_at").isNotBlank() -> "已转账（历史记录）"
        else -> when (data.optInt("status", -1)) { 0 -> "待审核"; 1 -> "审核通过"; 2, 4 -> "已驳回"; else -> "状态待确认" }
    }
}

internal fun centsText(value: Long): String = BigDecimal.valueOf(value, 2).toPlainString()
