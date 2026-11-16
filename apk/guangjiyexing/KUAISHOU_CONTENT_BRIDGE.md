# 快手激励素材字段桥接

适用版本：TAKU 6.6.51、快手适配器 5.6.10.1.1.2、快手 SDK 5.6.10.1。

当前 TAKU 适配器没有将 `KsRewardVideoAd.getKSAdInfoDatas()` 的素材字段转交给 APP。本工程使用 Android Gradle Plugin 的 ASM 构建插桩，在 `KSATRewardedVideoAdapter.getNetworkInfoMap()` 返回前转交该适配器持有的广告对象，由 `KuaishouRewardContent` 调用快手公开 getter。此桥接是项目自己的兼容修改，并非 TAKU 官方新增功能；SDK 缓存文件和原 AAR 不作修改。

- 只提取单条明确素材中的商品名、应用名、正数素材 ID；不把来源、描述或发布者冒充名称/广告主。
- 多条素材缺少本次实际展示对象的可靠标识时，不任意取第一条。
- 返回普通元数据 Map，内部弱引用当前广告，供 shown/reward/closed 阶段重新读取；不会把广告对象或弱引用作为事件字段序列化上报。
- getter 不可用、返回空列表、空值或占位文字时，保留原有字段；已有内容不会被后续空值清除。
- 原适配器继续负责竞价、缓存、加载、展示和奖励回调。此功能不触发额外曝光，也不决定金币发放。
- 构建校验目标字段 `g: KsRewardVideoAd` 及唯一 `getNetworkInfoMap()` 方法；不匹配时构建失败。升级上述 SDK/适配器前必须重新检查版本、字节码差异和真机行为，即使字段名恰好未变也不能直接认定兼容。

移除此兼容修改时，删除 `app/build.gradle.kts` 中的 `KuaishouContentBridgeFactory` 和 `androidComponents` 插桩注册，并删除客户端对 `KuaishouRewardContent.refresh()` 的调用。

2026-11-12 真机结果：最终版 1.0.4（5）在 shown/reward/closed 阶段都实际进入桥接，快手 `getKSAdInfoDatas()` 均返回空列表。名称采集尚未通过；发奖正常。请向快手/TAKU 确认当前广告位和投放素材提供此接口数据的条件。接口存在不等于每条广告一定返回内容。
