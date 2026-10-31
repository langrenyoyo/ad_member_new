# 插激组合真机验证（2026-10-28）

结论：在华为 JEF-AN20 真机上，已确认一次点击依次展示 **插屏 → 激励 → 插屏**，末尾插屏关闭后返回 APP 并开始冷却。本轮中间激励选择退出，未满足 SDK 奖励条件，因此不构成成功发奖路径的验收。

## 环境

- 设备：华为 JEF-AN20，ADB `47D0220908002529`。
- 包名：`com.heshangzhilian.yazhiyiji`。
- APK：`apk/鸭只易记-补贴提现插屏-20261028-debug.apk`，14:33 覆盖安装，保留登录数据。
- APK SHA256：`381f17bbc9215b3388c128ccc3b45e630cb5d9ef3efa3883103c4abfd0d51d6d`。
- 测试会员：695018；业务应用 238；测试前余额 100.030070，冻结 0。
- 以下时间均为北京时间。

## 连续观察的一组

14:59:14 点击一次“获取更多金币”，创建会话 `ads_mHi_EIbKIPB3ZZK9dkpOWO6u`。

| 步骤 | 真机证据 | 结果 |
| --- | --- | --- |
| 第 1 条插屏 | 梦幻西游；前台为快手 `FeedDownloadActivity` | 关闭后进入激励 |
| 第 2 条激励 | 天猫双11；前台为 `KsRewardVideoActivity`；服务端 SDK 元数据 `RewardedVideo / Kuaishou Ads` | 点击跳过并在确认弹窗选择“坚持退出” |
| 第 3 条插屏 | 桃园：将帅录；新的 `FeedDownloadActivity` 实例 | 关闭视频及素材尾页后返回 APP |
| 组后 | APP 显示“激励视频冷却中（88秒）”，后续恢复“获取更多金币” | 请求入口恢复正常，观察中未见额外第 4 条全屏广告 |

截图：

- `artifacts/device-group-round2-first.png`
- `artifacts/device-group-round2-reward.png`
- `artifacts/device-group-round2-exit-dialog.png`
- `artifacts/device-group-round2-tail.png`
- `artifacts/device-group-round2-finished.png`

设备 logcat 缓冲区滚动较快，末次保存的 `artifacts/device-group-round2-logcat.txt` 仅保留后续横幅刷新，不能作为完整顺序日志。点击和会话号来自当时读取的工具输出。SDK 插屏回调目前没有独立业务日志，本次插屏判断综合使用实际素材截图、前台 Activity 变化和已安装版本中的串行调用实现；服务端只记录中间激励会话，不应声称服务端已有两条插屏曝光审计。

## 服务端只读核对

- 14:59:14：`ad_requested / ok`。
- 14:59:58：`impression / ok`，SDK `shown / RewardedVideo / Kuaishou Ads`。
- 15:02:10：`client_fail / failed`，存在 SDK `closed` 元数据。
- 会话最终为 `failed`，`coin_log_id=None`；未见 SDK reward 事件。
- 会员余额仍为 `100.030070`，冻结为 `0.000000`。

该素材显示“点击跳转拿奖励”“体验几秒就能获得奖励”，本轮没有进入第三方体验，而是选择退出。不能把这次未发奖解释为组合编排失败，也不能据此宣布组合下的成功发奖已验收。

14:35 的上一轮会话 `ads_DZ2tmtS0TcA7TWhe6lwVjI0o` 曾观察到首插屏与激励，但中途会话暂停、设备转到 USB 设置，未连续记录末尾插屏，因此不计入完整顺序通过证据。

本轮没有修改代码或生产配置，没有手工补发奖励。补贴和提现入口插屏不在本轮验证范围。
