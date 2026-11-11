# 广告类型与内容采集修复（2026-11-08）

## 问题与修复

- 管理后台原来默认只查询激励广告。现在首次进入和重置筛选均查询全部广告，可按激励/副广以及副广类型筛选。
- Android 原来没有向服务端上报开屏、横幅、插屏、信息流的展示记录。现在在 SDK 的实际展示回调中上报，并采集点击、关闭事件；不把加载成功当作展示成功。
- 广告内容统一采集 SDK 提供的广告名称、应用名称、包名、素材 ID、广告主、广告平台、广告源 ID 和平台广告位 ID。信息流同时读取 SDK 原生素材对象。
- 后台广告列表和 APP 广告历史返回内容字段，并区分“已采集”“SDK 未提供名称”“未采集”。
- 上报先保存在 APP 私有目录的持久队列中，网络失败后可在后续触发时重试，最长保留 24 小时；事件绑定原账号，避免切换账号后串记录。超过重试窗口或服务端拒绝的事件无法继续补传。

## 广告类型

| ad_type / placement | is_fu | fu_type | 展示名称 |
| --- | --- | --- | --- |
| rewarded | 0 | APP 历史为 null | 激励视频 |
| splash | 1 | 1 | 副广 · 开屏 |
| banner | 1 | 2 | 副广 · 横幅 |
| interstitial | 1 | 3 | 副广 · 插屏 |
| native | 1 | 4 | 副广 · 信息流 |

广告形式与内容品类是不同维度。游戏、交友、电商、金融等内容品类仍按既有人工复核规则处理，不根据广告名称自动推断，也不以客户端上报内容决定收益。

## 新增副广事件接口

`POST /api/app/v1/ads/secondary-events`

使用现有 APP 登录鉴权和设备请求头。成功返回 HTTP 202。

```json
{
  "game_id": 238,
  "impression_id": "e0ebac50-9a88-43e6-8ae8-255e50fe4ef9",
  "placement": "interstitial",
  "ad_type": "interstitial",
  "ad_unit_id": "实际配置的插屏广告位ID",
  "event": "shown",
  "occurred_at": "2026-11-08T08:00:00Z",
  "network": "SDK 返回的广告平台",
  "source_id": "SDK 返回的广告源ID",
  "title": "SDK 返回的广告名称",
  "app_name": "SDK 返回的应用名称",
  "app_package": "com.example.ad",
  "creative_id": "SDK 返回的素材ID",
  "advertiser": "SDK 返回的广告主",
  "network_placement_id": "SDK 返回的平台广告位ID"
}
```

必填：`game_id`、`impression_id`、`placement`、`ad_type`、`ad_unit_id`、`event`、`occurred_at`。内容字段可选，不存在时传空字符串或省略。

- `impression_id` 必须为 UUID；同一次展示的展示、点击、关闭事件共用该值，不同展示使用不同值。
- `event` 为 `shown`、`clicked`、`closed`，相同账号、应用、展示标识、事件重复提交不会重复入库。
- `placement` 和 `ad_type` 必须一致，且为上述四种副广类型；广告位必须匹配该会员所属应用的当前后台配置。
- `occurred_at` 必须包含时区，允许过去 24 小时内或未来 5 分钟以内。
- 只有 `shown` 创建广告列表记录，点击/关闭不会额外增加观看次数。
- 返回 `data.recorded` 和 `data.ad_session_id`；重复事件返回 `recorded=false`。

副广会话使用 `taku_secondary` 标识，金币固定为 0，不进入激励结算、金币流水、奖励分账或激励内容标签样本统计。激励完成接口明确拒绝副广结算。

## 激励元数据与查询

现有 `POST /api/app/v1/ads/{ad_session_id}/metadata` 保持兼容，在原字段上补充 `app_package`、`advertiser`、`network_placement_id`；继续要求该会话的 `session_token`。允许会话创建后 24 小时内重试元数据，不因补报修改激励会话状态。

管理后台 `GET /api/v1/ads` 与 APP `GET /api/app/v1/ads/history` 统一返回：

| 字段 | 含义 |
| --- | --- |
| ad_title | 人工复核名称优先，否则 SDK 名称/应用名称 |
| ad_app_name / ad_app_package | 广告应用名称、包名 |
| ad_creative_id | 素材 ID |
| ad_advertiser | 广告主 |
| ad_network / ad_source_id / ad_network_placement_id | 实际广告平台、广告源和平台广告位 |
| ad_content_status | reported / sdk_not_provided / not_collected |
| ad_content_source | manual_review / client_reported / unknown |
| ad_behaviors | SDK 已上报的展示、点击等行为 |

APP 历史另外返回 `is_fu`、`fu_type`、`ad_type_label`。原分页参数保持兼容。后台列表不传 `is_fu` 查询全部，传 `0` 查询激励，传 `1` 查询副广。

## 验证与生效条件

本地已通过 66 项后台测试（新增副广 8 项、会员洞察 13 项、分页 4 项、TAKU 回调 41 项），Android 编译及 9 项定向单元测试，以及隔离模拟接口的后台浏览器验证。测试覆盖四种副广、幂等、乱序事件、账号隔离、错误广告位、补报、不发金币、名称缺失和列表筛选。浏览器验证未访问生产接口。

验证证据：`artifacts/ad-*-20261108.log`、`artifacts/ad-types-20261108/browser-verification.json`、`artifacts/ad-types-20261108/admin-ad-types.png`。

此次仅完成本地代码修改，尚未推送、部署或真机验收。生效需要更新后台及静态资源，并重新构建安装 APP；先部署后台，再发布 APP。本次沿用既有会话、事件、广告记录表，无新增表结构迁移。Android 位于独立嵌套仓库 `apk/test_android`，交付时需同时包含该仓库修改。

历史上未上报的副广与内容无法补回。部分广告源不通过 SDK 提供名称、包名或素材 ID，此时保留可获得的来源信息并明确显示缺失状态；本次不承诺识别所有广告的具体商品或名称。真实 SDK 返回字段仍需新版 APP 真机验收。
