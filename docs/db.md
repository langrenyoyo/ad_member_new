# 数据库设计

本数据库设计服务于 `https://ad.leadink.cn/` 整站一比一复刻项目。表结构只实现目标后台已确认的业务能力，采用自研等价实现，不复制第三方源码、私有接口、私有数据或未授权资源。

## 1. 设计原则

- 运营明细与汇总分离
- 广告原始记录保留，展示层做归一化
- 导入批次和失败行必须可追溯
- 核心查询字段建立索引
- 主体、游戏、会员、广告、提现、补贴、收益和风控模块均按对标后台逐页补齐字段
- 页面显示名称与数据库内部字段解耦，保留目标后台字段别名和历史数据兼容字段

## 2. 核心表

| 表 | 作用 | 关键字段 |
|---|---|---|
| `admin_users` | 后台账号 | `username`, `password_hash`, `role`, `status`, `avatar` |
| `agents` | 主体 | `name`, `user_name`, `status`, `game_ad_status` |
| `agent_analysis_config` | 主体分析的图表分组 | `agent_id` 主键、`buckets` JSON 文本、创建/更新时间；coin/success/apps 各存 name/minimum/maximum 数组，GET 不创建，PATCH 合并分组，随主体删除清理；迁移 `e923_agent_analysis` |
| `games` | 游戏 | `agent_id`, `name`, `game_key`, `status`, `ad_status` |
| `members` | 会员 | `agent_id`, `game_id`, `username`, `coin`, `vip`, `is_white` |
| `ad_records` | 广告记录 | `user_id`, `game_id`, `agent_id`, `ad_group`, `is_fu`, `fu_type`, `is_look`, `request_id` |
| `ad_import_batches` | 导入批次 | `file_name`, `operator_name`, `total`, `accepted`, `rejected`, `status` |
| `ad_import_errors` | 导入失败行 | `batch_id`, `row_number`, `request_id`, `message`, `raw_data` |
| `withdrawals` | 提现单 | `status`, `plan_status`, `exchange_value`, `reason`, `audit_operator_name`, `audited_at`, `transferred_at` |
| `subsidies` | 补贴单 | `price`, `tx_price`, `status`, `sub_msg`, `audit_operator_name`, `audited_at` |
| `coin_logs` | 金币流水 | `user_id`, `coin_before`, `coin`, `coin_after`, `type`, `remark` |
| `risk_records` | 风控历史 | `tagcode`, `tags`, `hardware_main_id`, `ip`, `action`, `risk_level` |

## 2.1 模块与数据边界

| 对标模块 | 数据边界 | 主要关联 |
|---|---|---|
| 仪表盘 | 只读汇总和最近活动 | 主体、游戏、会员、广告、提现 |
| 主体管理 | 主体基本资料、状态、广告开关 | `agents` |
| 游戏管理 | 游戏资料、主体归属、广告状态 | `games` -> `agents` |
| 会员管理 | 会员资料、金币、VIP、白名单状态 | `members` -> `agents`, `games` |
| 广告列表 | 广告明细、收益、代码位、请求链路 | `ad_records` -> `members`, `games`, `agents` |
| 用户提现 | 提现申请、审核、转账结果 | `withdrawals` -> `members` |
| 补贴申请 | 补贴申请、审核结果、交易金额 | `subsidies` -> `members`, `games` |
| 收益管理/金币流水 | 金币变动前后值、业务类型、备注 | `coin_logs` -> `members` |
| 白名单 | 会员白名单标志 | `members.is_white=1` |
| 风控历史 | 风控标签、设备、IP、处置动作 | `risk_records` |
| 设备风控 | 参考为会员名单，入选规则待确认 | 不能使用 `risk_records.id` 代替会员 ID；当前接口 503 |
| 个人资料 | 后台账号资料和凭证 | `admin_users` |
| 教程 | 认证只读目录与正文 | `public/target-book.json`，本轮未建表；九张外链原图未恢复 |

## 3. 广告表规则

2026-09-18：`e922_admin_avatar` 为 `admin_users` 新增非空 `avatar VARCHAR(1024)`，默认 `/assets/img/avatar.png`，仅存头像路径。临时数据库完整升级/回退通过；现有开发库仍存在历史启动补列与 Alembic 版本戳不一致，旧迁移重复 `ad_group` 失败，未强行 stamp。开发启动沿既有补列逻辑增加头像列。详见 [个人资料核验](profile-parity-verification.md)。

### 3.1 显示映射
- `is_fu = 0` -> `激励`
- `is_fu = 1` -> `副广`
- `fu_type = 1` -> `开屏`
- `fu_type = 2` -> `Banner`
- `fu_type = 3` -> `插屏`
- `fu_type = 4` -> `信息流`

### 3.2 兼容字段
- `pre_ecpm`：展示用 ECPM
- `ad_network_rit_id`：广告代码位展示别名
- `create_time`：兼容时间戳字段

### 3.3 约束
- `request_id` 建议唯一
- 导入时同文件重复 `request_id` 必须拒绝
- 成功记录但 `coin` 或 `ecpm` 为 0 时应保留并进入告警

## 4. 索引建议

- `admin_users.username`
- `agents.user_name`
- `games.agent_id`
- `members.username`
- `members.agent_id`
- `members.game_id`
- `ad_records.request_id`
- `ad_records.user_id`
- `ad_records.game_id`
- `ad_records.agent_id`
- `ad_import_errors.batch_id`
- `withdrawals.status`
- `subsidies.status`

## 5. 数据流

1. 运营端导入 CSV
2. 后端解析并校验
3. 成功行写入 `ad_records`
4. 失败行写入 `ad_import_errors`
5. 告警接口按 `ad_records` 和 `ad_import_errors` 动态聚合
