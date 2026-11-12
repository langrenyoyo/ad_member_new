# Project-specific ProGuard rules.
# Aliyun device risk SDK uses reflection and requires its public API to remain intact.
-keep class net.security.device.api.** { *; }
-dontwarn net.security.device.api.**
