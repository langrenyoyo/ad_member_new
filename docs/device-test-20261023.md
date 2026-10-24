# 2026-10-23 真机测试

- 设备：华为 JEF-AN20，ADB 47D0220908002529。
- 最新本地 debug APK assembleDebug 成功，覆盖安装成功，保留原数据。
- 后端：线上 admember.yunjizhilian.asia；测试账号 13800000000，会员 695018。
- 测试前后余额均 100.000000，冻结金币均 0；未触发提现、出款或手工加币。

## 结果

1. 已登录账号保持登录，首页、我的、广告测试页面可进入；横幅、原生广告有展示。
2. 北京时间 00:03:54 申请激励，00:03:57 展示快手视频，等待视频完成并关闭，未点击落地页。
3. 会话 ads_ZHjULZM5eC_UseoqOh-xE4Ar：收到 impression、client_metadata shown/reward/closed、client_complete pending、callback_received。
4. 客户端人民币 eCPM 209.92 解密成功，单次估算收益 0.20992 元。仅为客户端诊断，不等于最终结算收益。SDK title/app_name 为空，不能自动获得视频中显示的广告名称。
5. 00:04:28 服务端回调返回 HTTP 602，并记录 KeyError: 602。只读提取该次真实回调的 e_c/e_c_cny/s_id 在服务端验证，抛出 EcpmValidationError。未重放回调、未绕过验证。
6. 会话仍 impressed，completed_at、coin_log_id 为空，无该会话奖励流水，发奖验收失败。
7. 游戏 238 设备风控 enabled=False、limit_enabled=False；会员非白名单。本次无新设备验证记录，不能认定风控验证通过。未擅自更改全游戏规则。

## 后续

- 定位服务端 eCPM 密钥/Key ID 与真实密文的匹配及参数编码问题，不能用客户端解密成功替代服务端结算验证。
- 修复非标准状态码 602 在服务栈中的处理异常。
- 在明确的测试风控配置下验证设备校验、限次和豁免。
- 修复后再做一次同会话展示、回调、金币流水和余额的完整验收。

截图：artifacts/device-ad-attempt.png、device-ad-end.png、device-result.png。

## 后续定位及修复

- 真实回调中的 e_c/e_c_cny/s_id 长度分别为 5/9/6，均含占位符，s_id 不匹配任何已配置 Key ID。根因是平台传入字面占位符，不能据此认定私钥有误。
- 已将业务错误 601/602 映射到标准 HTTP 403/400，X-TAKU-Result-Code 保留业务码；成功回调仍返回 200。收益验证拒绝新增持久化日志 ecpm_placeholder/invalid_ecpm_proof。
- 27 项回调测试通过，包括成功结算、重复回调幂等、无效签名、无效证明及占位符拒绝后余额不变。
- 已部署 ad_member_new 并健康检查通过。服务器空参数探针返回 HTTP 400、X-TAKU-Result-Code: 602，无状态码 KeyError。
- 备份 main_from_txt.py.before-callback-20261022T171648Z（UTC 命名）。
- 等待 TAKU 控制台移除手工 e_c/e_c_cny/s_id 占位符并确认服务端加密，之后再真机验收。未绕过签名或收益证明校验，未手工补发本次奖励。

## 平台修改后复测（01:26–01:33 北京时间）

- 用户确认已修改后重新启动 APP。01:21:48 的最新控制台 is_test 探针已不含 e_c/e_c_cny/s_id 占位符，返回 200；探针不校验收益、不发奖，不能证明真实加密字段已启用。
- 新会话 ads_m2BHdCKxAPAKFebITufPo3zZ、ads_fFbp8ZcMoYw7EI1-efbOyCeF 均成功展示快手“天猫双11”互动素材，提示点击跳转体验拿奖励。等待后未见 SDK reward 事件；使用跳过并确认退出，未点击广告落地页。
- 两次均无该会话 callback_received、奖励流水或 coin_log_id。第一条仍 impressed，第二条 failed/client_fail。不能把先前 00:04 的失败回调当成本轮回调。
- 余额仍 100，冻结为 0，已停止 APP。此次无法验收新的服务端密文及发奖，需要支持仅观看完成奖励的测试广告素材，或在设备上由用户完成当前互动素材的奖励条件后继续核对。

## 01:38 再次测试

- 会话 ads_tgFoZgsCznf16jFT-fGBVGcU 于北京时间 01:38:45 创建，01:38:46 展示天猫互动素材。
- 等待后仅有 ad_requested/impression，无 client_complete、callback_received、奖励流水，余额仍 100，冻结为 0。
- 手机保留在当前广告页面，已请求用户完成互动体验并返回后继续核对；本轮没有点跳过或强制停止 APP。

## 用户完成互动后的核对（01:43 至 01:47，北京时间）

- 同一会话 ads_tgFoZgsCznf16jFT-fGBVGcU 已有 SDK clicked、reward、closed 事件，以及 client_complete pending、callback_received ok。
- 01:43:24 收到真实 TAKU 回调，字段为 adsource_id、extra_data、network_firm_id、placement_id、reward_amount、reward_name、rv_play_dur、sign、trans_id、user_id。未收到 e_c、e_c_cny、s_id；此前的字面占位符已消失，但服务端加密收益证明仍缺失。
- 回调被记录为 callback_rejected / invalid_ecpm_proof，返回标准 HTTP 400；该次请求未再出现 KeyError: 602。
- 客户端人民币 eCPM 解密值 80.64，单次估算收益 0.08064 元，仅用于诊断，不能替代服务端结算证明。广告源 16204241，SDK request ID 为 0fb0b1f61d2af7368c1e4fe08e3db9c6。
- 再次只读查询线上数据库：余额 100.000000，冻结 0.000000；会话仍 impressed，completed_at 与 coin_log_id 为空，无奖励流水。未重放回调、手工补币或绕过校验。
- 截图 artifacts/reward-check.png 确认手机已返回 APP 广告测试页。动画导致 UI 层级抓取失败，未完成手机余额文字核验；余额以上线数据库结果为准。
- 下一步需在 TAKU 核实实际应用/广告位的服务端 eCPM 加密配置，必要时提交上述时间、广告源及 SDK request ID 给平台排查。不要重新添加未经支持的占位符；客户端解密成功和控制台测试回调 200 均不能证明真实服务端收益字段已经启用。

## 02:00 文档密钥同步与新一轮真机测试

- 按用户要求解析 serverdata.md 的服务端、客户端 eCPM Key 及各自 Key ID，两者均可加载为 1024 位 RSA 私钥；不记录密钥正文。
- 已同步到线上 TakuGlobalConfig 的对应映射，保留其他 Key ID。游戏 238 无文件级覆盖；更新后检查实际有效映射与文档规范化 PEM 完全一致。密钥按请求读取，无需重启。健康检查返回 ok。
- 同步前原值备份：/www/backup/ecpm-20261022T180000Z/global-ecpm.json，目录权限 0700，文件权限 0600。同步脚本 scripts/sync-ecpm-server.py 不包含密钥常量。
- 新会话 ads_Qq876wZ5PsIVALUku0kyUUSc 于北京时间 02:00:34 创建，02:00:36 展示。客户端人民币 eCPM 78.83 解密成功，SDK request ID 74591fa84dd118490687cfb0ac36bbf6，仅作客户端诊断。
- 首次核对只有 ad_requested/impression，没有 reward、client_complete、callback_received 或奖励流水。余额 100，冻结 0。本轮尚不能判断服务端加密回调是否恢复；01:43 的失败回调属于上一轮。
- 手机保留当前天猫互动广告，已请求用户完成体验并返回后继续核对。截图 artifacts/ecpm-new-ad.png。

## 用户再次确认完成后的核对（02:37，北京时间）

- 截图 artifacts/ecpm-completed.png 确认手机已返回 APP 广告测试页面。
- 本轮 ads_Qq876wZ5PsIVALUku0kyUUSc 仍只有 shown/impression，没有 reward、closed、client_complete、callback_received 或奖励流水；completed_at、coin_log_id 均为空。不能将用户返回页面等同于 SDK 奖励已触发。
- 02:34:28 新增一条真实回调，但数据库新增 callback_received / callback_rejected 属于上一轮 ads_tgFoZgsCznf16jFT-fGBVGcU，可能是平台重试，不能当成本轮回调。该请求仍无 e_c、e_c_cny、s_id，返回 HTTP 400 / invalid_ecpm_proof。
- 余额仍 100.000000，冻结 0.000000。密钥已同步不等于服务端加密收益已验收；尚未收到可用于本轮解密验证的服务端密文。
- 只读检查 APP：showRewarded 为每次请求创建 ATRewardVideoAd，设置该会话 USER_ID / USER_CUSTOM_DATA，再 load；现有证据不足以判定会话串用或解释本轮事件缺失。未擅自修改结算规则、重放回调或补币。

## 02:46 再次真机回调测试

- 新会话 ads_U9mAZbttWG557hYtbhC8yLwd 于北京时间 02:46:33 创建，02:46:35 展示；服务端已保存 SDK shown/clicked/reward/closed 和 client_complete pending。
- 客户端人民币 eCPM 31.17 解密成功，SDK request ID 592ecbbbe076f63b51c9759607039c90，仅作诊断。
- 02:47:00 同时间窗出现 GET /api/callbacks/taku/reward%26rv_play_dur%3D24845，返回 404。该请求将参数放进路径，未命中奖励回调路由；日志没有可绑定会话的查询参数，不能单凭时间宣称已完成该请求与会话的严格关联。
- 本轮无 callback_received、coin_log_id 或奖励流水，余额仍 100，冻结 0。02:44:08 的 200 是仅带 is_test 的探针，不代表真实回调成功。
- 需在 TAKU 恢复受支持的完整回调参数模板：第一个查询参数使用 ?，后续参数使用 &，不能把分隔符编码为路径中的 %26 / %3D。保留签名、交易、用户及 extra_data 业务参数，不添加未经支持的 eCPM 占位符。尚无法验证本轮服务端加密字段。
- 截图 artifacts/callback-retest-ad.png、artifacts/callback-retest-result.png。未修改服务器路由去兼容缺少签名和会话参数的异常路径，未重放或手工补币。

## 02:58 至 03:02 回调复测

- 新会话 ads_CEev3XHmYWp0GwmsvsSOruRw 于北京时间 02:58:09 创建，02:58:11 展示。客户端 eCPM 38.19 CNY 解密成功，SDK request ID 7d4f9ede07ef304de9767d8c104cc329。
- 观察到京东落地页，执行一次返回后手机回到 APP 广告测试页；本轮出现 client_complete pending，但无 callback_received、coin_log_id 或奖励流水。余额 100，冻结 0。
- 03:00:12 同时间窗请求 GET /api/callbacks/taku/reward%26rv_play_dur%3D120860 返回 404，仍未命中奖励回调路由。此异常请求不含可用于严格关联会话的查询参数，时间对应不能替代绑定验证。
- 02:53 至 02:54 的 200 请求均只有 is_test，属于控制台探针，不能验收真实回调或加密收益。
- 尚未验证服务端密文和发奖成功，需核对平台实际发送的完整 URL 及参数模板。截图 artifacts/recheck-ad.png、artifacts/recheck-return.png。未改变服务器校验或手工发奖。

## 03:13 完整 URL 建议后的复测

- 新会话 ads_cwaTq-zQZwN3yNolXfvj9dCb 于北京时间 03:13:49 创建，03:13:51 展示，已记录 client_complete pending。
- 03:14:11 同时间窗 GET /api/callbacks/taku/reward%26rv_play_dur%3D19339 返回 404，异常路径仍存在。该请求缺少可用于严格绑定会话的查询参数，不能仅凭时间认定其会话身份。
- 本轮没有 callback_received、completed_at、coin_log_id 或奖励流水；余额仍 100，冻结 0。03:12:08 控制台请求的 200 不能替代本轮真实回调验收。
- 手机已回到广告测试页并显示激励视频冷却，截图 artifacts/urltest-ad.png。需要检查实际应用/广告位的已保存 URL 与平台发送日志，不能据此断言新配置的生效时间或密钥错误。未修改服务端校验和钱包。

## 03:22 新一轮复测

- 会话 ads_FfKc27LFHiTrt2JjLCqc0Tmt 于北京时间 03:22:08 创建，03:22:09 展示；已收到 SDK shown/reward/closed 和 client_complete pending。客户端人民币 eCPM 40.74 解密成功，SDK request ID 8177f8b03ea45b578035517dffa4bc41。等待并多次查询后，本轮无 callback_received 或奖励流水，余额仍 100，冻结 0。
- 03:22:53 收到正常路径 /api/callbacks/taku/reward 的真实回调，数据库绑定的是上一轮 ads_cwaTq-zQZwN3yNolXfvj9dCb，不能计入本轮。已记录 callback_received 及 callback_rejected / invalid_ecpm_proof，HTTP 400。
- 最新回调字段：adsource_id、extra_data、network_firm_id、placement_id、reward_amount、reward_name、rv_play_dur、sign、trans_id、user_id。e_c、e_c_cny、s_id 仍缺失。该请求已到达正确路由，但不能证明本轮回调已经恢复或服务端密钥解密成功。
- 截图 artifacts/latest-callback.png、artifacts/latest-ad.png。已在奖励事件后点击广告关闭按钮，没有点击落地页或修改结算校验。

## 04:15 至 04:19 真机回调复测

- 本轮会话 ads_9PjQz38qod5dNeJZCDoc75Ti 于北京时间 04:15:31 创建，04:15:33 展示，已记录 client_complete pending、callback_received ok、callback_rejected / invalid_ecpm_proof。
- 04:18:42 真实回调命中正确接口，HTTP 400。本次可以通过数据库流程记录确认本轮收到了回调，不再仅靠时间推断。
- 回调实际字段为 adsource_id、extra_data、network_firm_id、placement_id、reward_amount、reward_name、rv_play_dur、sign、trans_id、user_id。e_c、e_c_cny、s_id 全部缺失；这是未提供收益证明，不能认定私钥解密失败。
- 客户端人民币 eCPM 40.62 解密成功，SDK request ID 13ba2bc13ddbea1b11e527409815602a，仅作诊断。余额仍 100.000000，冻结 0.000000，completed_at、coin_log_id 为空，无本轮奖励流水。
- 截图 artifacts/reward-next.png、artifacts/reward-next-ad.png。手机已返回广告测试页。未重放回调、修改密钥或绕过收益校验。

## 2026-10-24 00:10 北京时间：再次真机广告回调

- 设备：华为 JEF-AN20，ADB `47D0220908002529`；线上后端；未安装广告下载的第三方应用。
- 新会话：`ads_zLHHJImaqnuPqICRdZcOb_iw`，广告源 16204242。APP 侧先展示并产生 impression；广告页面完成任务后显示“恭喜获得奖励”，随后返回 APP。
- 服务器收到该会话的 TAKU 回调并命中正确接口，但回调 eCPM 证明校验失败（`invalid_ecpm_proof`，HTTP 400）；未生成奖励流水，余额仍为 100 金币，冻结金币为 0。
- 当前回调仍未提供可验证的有效服务端 eCPM 证明（不能以客户端解密 eCPM 代替服务端核验），因此没有手工补币或放宽校验。
- 手机临时保持唤醒的设置已恢复为息屏 30 秒、插电不保持唤醒。
- 证据截图：`artifacts/new-attempt.png`、`artifacts/after-cancel-install2.png`、`artifacts/back-app2.png`。

### 结论

SDK 展示、观看完成提示和服务端回调链路均可观测；奖励发放仍被服务端 eCPM 证明校验阻断。需要 TAKU 在该广告位实际下发可验证的服务端 eCPM 加密字段（并确认 s_id 与服务端 Key ID 对应）后，才能重新验收到账。

## 2026-10-24 再次验证（TAKU 控制台确认密钥后）

- TAKU 控制台截图显示服务端 eCPM Key、客户端 eCPM Key 均已配置；广告聚合中实际启用的是快手激励广告源，Taku ADX 行显示为未启用。
- 新会话：`ads_tA3NdLIgqbCehy9yB8rz3RbL`。APP 已产生展示、点击、SDK reward、closed 和 client_complete pending，广告页自动返回 APP。
- 等待回调后，线上服务仍未收到绑定到该新会话的 TAKU 回调；余额保持 100 金币，冻结金币 0。
- 同一观察窗口内唯一的新回调仍绑定上一会话 `ads_zLHHJImaqnuPqICRdZcOb_iw`，且请求不含 eCPM 证明字段，服务端记录 `invalid_ecpm_proof`，未发奖。
- 因此截图可证明密钥已保存，尚不能证明“当前启用的快手广告源”向 TAKU 回调实际下发服务端 eCPM 加密字段；本轮未手工补币、未放宽校验。

## 2026-10-24 23:10 至 23:22 再次真机复测

- 设备：华为 JEF-AN20（Android 12，ADB `47D0220908002529`）。生产包 `com.heshangzhilian.yazhiyiji` 已覆盖安装最新 debug APK，并保留登录数据；APK SHA256 为 `98A5F2A966C9F823883EC63B3E0940B357D1AC3B81D45C573C9ED701DA67DB16`，设备端更新时间为 23:10:50。
- 测试账号 `13800000000`、会员 `695018`。测试前余额 `100.000000`，冻结余额 `0.000000`。
- 新会话 `ads_hx3HKnNhzu0iqsTgeV0Iys80` 于北京时间 23:14:30 创建，23:14:32 展示快手“梦幻西游”激励素材。SDK 已记录 `shown`、`reward`、`clicked`、`closed`；素材页面显示“已完成任务，恭喜获得奖励”。客户端解密人民币 eCPM 为 `0.01 CNY`，仅为诊断值，不具备服务端结算资格。
- 广告 SDK 随后自动进入下载/安装界面；本轮未主动确认下载或安装，并返回 APP。设备 23 点后唯一的第三方包变更是被测生产包在 23:10:50 更新，没有新安装广告应用。
- 北京时间 23:14:43，真实 TAKU 回调到达并正确绑定该会话。请求包含 `adsource_id`、`extra_data`、`network_firm_id`、`placement_id`、`reward_amount`、`reward_name`、`rv_play_dur`、`scenario_id`、`sign`、`trans_id`、`user_id`，仍缺少 `e_c`、`e_c_cny`、`s_id`。服务端记录 `callback_received` 后以 `invalid_ecpm_proof` 拒绝，HTTP 400。
- 延迟到 23:22 再查：会话仍为 `impressed`，`completed_at`、`coin_log_id` 为空，奖励流水数为 0；余额仍为 `100.000000`，冻结余额仍为 `0.000000`。客户端完成请求多次重试，服务端均记录为 `client_complete pending`。
- 线上 `backend/app/main_from_txt.py` 的修改时间及服务启动时间均为 2026-10-23 01:16:45，线上文件不含本地当前实现已有的 `client_reward_granted` 逻辑。因此本轮 APK 虽为最新版本，生产后端仍按旧的严格回调路径运行，本地新增的即时 SDK 奖励及后续 TAKU 核检流程尚未部署。
- 证据截图：`artifacts/retest-ad-page-20261024.png`、`artifacts/retest-ad-active-20261024.png`、`artifacts/retest-installer-20261024.png`、`artifacts/retest-final-20261024.png`。

### 本轮结论

广告请求、展示、SDK 奖励事件、关闭事件及真实 S2S 回调链路均可观测，但金币到账闭环仍未通过。当前同时存在生产后端版本未更新，以及 TAKU 真实回调不提供服务端 eCPM 证明字段两个问题；本轮未重放回调、未手工补币、未安装广告应用，也未放宽签名或 eCPM 校验。

## 2026-10-24 23:31 至 2026-10-25 00:17：SDK 奖励替代结算验收

- 按业务决定暂不以缺失的 `e_c`、`e_c_cny`、`s_id` 阻塞用户奖励。替代路径为：服务端签发一次性广告会话和固定奖励快照，客户端仅在 TAKU SDK `reward` 事件后提交完成；服务端校验登录会员、设备、会话令牌、会话状态及幂等键后发放服务端快照中的固定金币。客户端解密 eCPM 仅用于诊断，不能决定发奖金额。
- 本地专项测试 `python -m unittest backend.tests.test_taku_callback backend.tests.test_member_policy` 共 64 项全部通过，覆盖即时发奖、重复提交、并发提交、迟到补发、错误签名拒绝，以及后续回调只更新核检、不重复发奖。
- 23:31:22 最小发布 `backend/app/main_from_txt.py`、`backend/app/member_policy.py` 并重启线上服务，健康检查通过。发布前备份数据库和代码至 `/www/backup/ad-member-client-reward-20261024T153119Z`。
- 历史待确认会话 `ads_hx3HKnNhzu0iqsTgeV0Iys80` 在 APP 重启后自动补发成功，生成金币流水 `21`，金额 `0.010000`，余额由 `100.000000` 增至 `100.010000`。
- 新真实会话 `ads__Uq_xQqiPYbKCoPfbx_IrlDQ` 在 SDK `reward` 后即时发奖成功，生成金币流水 `22`，金额 `0.010000`，余额增至 `100.020000`。真实 TAKU 回调仍无 eCPM 证明时被记录为 `taku_reconciliation_received / ecpm_missing_or_invalid`，返回成功且未二次加币；平台重试同样只新增核检记录。
- 第二个新真实会话 `ads_bo1Qx8b11NssAbk1mA-PAX8C` 在退出广告后由 APP 持久化补发，生成金币流水 `23`，金额 `0.010000`，余额增至 `100.030000`。
- 三个会话最终均为 `rewarded`，各自 `client_reward`、`client_reward_granted` 和金币流水数量均为 1；冻结余额始终为 `0.000000`。APP 重启与回调重试后没有重复加币。
- 手机最终显示金币 `100.03`。证据截图：`artifacts/client-reward-my2.png`（首次补发后 100.01）、`artifacts/client-reward-live-ad.png`、`artifacts/client-reward-final-balance.png`（最终 100.03）。本轮未安装广告应用、未手工补币、未伪造或重放 TAKU 回调。

### 替代流程结论

发奖闭环已通过：真实广告展示 -> TAKU SDK 奖励事件 -> 服务端一次性会话结算 -> 金币流水 -> APP 余额更新。缺失 eCPM 证明的 S2S 回调已降级为后续核检信号，不再阻塞已由 SDK 确认的用户奖励，也不会触发第二次发奖。该方案承担客户端 SDK 奖励上报相对于服务端加密收益证明更弱的可信度，因此继续保留设备风控、固定奖励快照、会话令牌、七天补发窗口、数据库锁和幂等约束。
