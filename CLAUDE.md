# CLAUDE.md

> 此文件供 AI 编程助手（Claude Code / Codex / Cursor 等）读取，定义项目上下文与编码规范。
> 位置：项目根目录 [`/Users/wangxiao/WorkSpace/RD/CLAUDE.md`](./CLAUDE.md)
> 配套文档：[docs/01-requirements.md](./docs/01-requirements.md)

---

## 项目名称

**北京二手房独立经纪人撮合评价平台（代号：HomeMatch）**

## 项目描述

基于 AI Agent 的独立经纪人房客源撮合平台。

- **用户群体**：仅独立二手房经纪人，无经纪公司
- **角色**：每个经纪人可同时作为买方和卖方经纪人
- **核心闭环**：智能匹配 → 顺序邀约 → 方案握手 → 双向评价
- **MVP 范围**：不涉及交易、不分账、不绑定独家，仅沉淀角色与行为证据链
- **差异化**：贝壳找房链接作为信息增强输入，AI 自动解析+预填
- **v0.3 平台**：用户端从微信小程序切换到 iOS + Android APP（Flutter 跨端），详见 [docs/01-requirements.md](./docs/01-requirements.md)

## 核心理念

对标贝壳 ACN 的信息联卖效率，但不强制分边分佣；用 AI Agent 赋能单兵作战的独立经纪人。

---

## 技术架构

### 后端
- **语言/框架**：Python 3.11+ / FastAPI
- **数据库**：PostgreSQL 15（含 `tsvector` + GIN 索引 + 物化视图）
- **缓存**：Redis 7
- **任务队列**：**RQ**（Redis broker；不用 Celery，MVP 阶段过重）
- **状态机**：`transitions` 库 或 纯枚举
- **ORM**：SQLAlchemy 2.0
- **迁移**：Alembic

### APP 端（v0.3 切换）
- **跨端框架**：**Flutter 3.x**（Dart 3）
- **状态管理**：**Riverpod 2.x**
- **路由**：**go_router**
- **网络层**：**dio + retrofit**，自定义拦截器链（日志 / Auth / Refresh / Error / Sentry）
- **本地存储**：**Hive**（列表缓存、设置）
- **推送**：**firebase_messaging**（APNs + FCM 统一封装）
- **图片**：`image_picker` + `flutter_image_compress`
- **认证**：**微信登录为主** + Apple 登录（iOS 必选）+ 短信兜底 + JWT（存 Secure Storage）

### Web 管理后台
- **框架**：Vue 3 + Element Plus

### AI 服务
- **主力模型**：DeepSeek-V3（性价比）
- **兜底模型**：Claude / GPT-4o（评价异常检测、复杂语义任务）
- **接口协议**：OpenAI API 兼容
- **匹配引擎**：PG 全文检索 + 规则打分（**MVP 不上 Elasticsearch**）

### 基础设施
- **文件存储**：阿里云 OSS
  - **APP 直传**（不走后端中转）：后端签发 STS Token，APP 用 Token 直传
- **水印处理**：客户端预压缩+清 EXIF + 服务端 Pillow 双层水印（[D-010](./docs/00-decisions.md#d-010) + [D-017](./docs/00-decisions.md#d-017)）
- **推送通道**：[D-014](./docs/00-decisions.md#d-014)
  - iOS：APNs（HTTP/2）
  - Android：FCM
  - 后端：`firebase-admin` 统一封装
- **部署**：Docker（单机起步）→ 二期 K8s / 阿里云 ACK
- **CI/CD**：GitHub Actions + **fastlane**（iOS/Android 自动化打包）
- **配置管理**：pydantic-settings + 12-factor
- **依赖管理**：uv（Python）+ pubspec.yaml（Flutter）
- **错误监控**：Sentry（APP+后端）+ 自建事件日志（业务）
- **限流**：`slowapi`（HTTP 层）+ Redis 滑动窗口（LLM 层）

### 明确**不上**（二期再说）
- ❌ LangGraph
- ❌ Elasticsearch
- ❌ 微信小程序 / Taro
- ❌ 独立 IM 通讯（用 APNs/FCM 推送代替）
- ❌ 支付 / 分账
- ❌ 多租户 / SaaS 化
- ❌ Android 厂商推送聚合（华为/小米/OPPO/vivo）

---

## 核心数据模型（10 张表，v0.3）

详细字段见 [docs/01-requirements.md §5](./docs/01-requirements.md)。

**主表**：

| 表 | 说明 |
| --- | --- |
| `users` | 经纪人；含 phone_encrypted、phone_hash、apple_user_id、wechat_unionid、credit_score |
| `properties` | 房源；含 source_url（贝壳链接）、status（有效/下架/冻结） |
| `demands` | 需求；含 price_range、viewing_time、source_url |
| `invitations` | 邀请；含 status、expired_at（24h 倒计时） |
| `proposals` | 合作方案 |
| `cooperations` | 合作主记录；含 status、memo_content、signed_at |
| `reviews` | 评价；含 rating、comment |

**v0.3 新增表**：

| 表 | 说明 |
| --- | --- |
| `devices` | 推送设备；含 fcm_token、platform、app_version、last_active_at |
| `app_versions` | APP 版本管理；含 latest_version、min_supported_version、force_update |
| `event_logs` | 业务事件日志；含 event_name、event_data(JSONB)、app_version、platform |

**辅助表**：
- `audit_logs`（append-only）：关键操作的时间戳+操作人+动作
- `agent_messages`：AI Agent 对话历史（用于训练/调优）
- `community_prices`：小区均价缓存（用于价格偏离校验）

---

## 业务规则

1. **需求匹配**：需求发布后，系统推荐 **Top 5** 卖方经纪人（多维匹配：区域/价格/户型/看房时间/信用/活跃度）
2. **顺序邀约（非竞合）**：买方从列表中选 1 人发起邀请；卖方 24h 内未响应自动失效，本轮淘汰
3. **方案握手**：卖方接受后 2h 内提交合作方案；买方确认后双方电子签名，握手成功
4. **评价必填**：合作结束双方必须互评（1-5 星 + 文字）
5. **信用分公式**：`信用分 = 评价均分 × 活跃系数`（待产品确认活跃系数具体公式）
6. **淘汰规则**：
   - 虚假房源 → **一票冻结**（最严）
   - 15 天无维护 → 房源下架
   - 多次不响应 / 恶意抢单 → 降权
7. **数据完整性**：所有操作带时间戳，软删除，**审计日志 append-only 不可篡改**
8. **脱敏规则**：向对方展示需求/房源时**隐藏真实姓名和联系方式**，直到握手成功

### 信用分公式（[D-002](./docs/00-decisions.md#d-002)）

```
基础分   = 评价均分 × 20                  // 1-5 星 → 20-100 分
活跃系数 = min(1.0, 0.3 + 0.7 × min(1, 近30天有效响应数/10))
信用分   = 基础分 × 活跃系数              // 范围: 6 - 100
```

- 每日定时任务计算并缓存（避免每次实时聚合）
- `users` 表需 `credit_score`（最终值）+ `rating_avg` + `activity_count_30d` 字段
- 邀请超时淘汰是**本轮不可见**，下轮重新计算（[D-001](./docs/00-decisions.md#d-001)）

---

## 开发规范

### 后端
- **API 设计**：RESTful 风格，前缀 `/api/v1/`
- **数据校验**：所有请求/响应使用 Pydantic v2 模型
- **依赖管理**：所有依赖锁定版本（uv/Poetry 的 lockfile 提交）
- **数据库迁移**：schema 变更**必须**走 Alembic；禁止手动改表
- **异步任务**：长时间操作（LLM 调用、爬虫、水印）必须走 RQ
- **配置**：所有环境变量通过 `pydantic-settings` 注入；**禁止**硬编码
- **Secrets**：绝不入 git；`.env*` 加入 `.gitignore`；团队用 vault/密钥管理服务
- **日志**：结构化（JSON），含 `request_id`、`user_id`、`action`
- **错误处理**：统一异常处理器返回 RFC 7807 风格错误体
- **LLM 调用**：封装为独立 service 类，带**重试 + 降级 + 限流**

### APP 端（Flutter）
- **状态管理**：Riverpod 2.x（用 `@riverpod` 代码生成）
- **路由**：go_router，支持 Deep Link（[D-019](./docs/00-decisions.md#d-019)）
- **网络**：dio + 拦截器链，统一处理 token / 错误 / Sentry
- **本地存储**：Hive（列表缓存、用户设置）
- **图片处理**：image_picker + flutter_image_compress（[D-017](./docs/00-decisions.md#d-017)）
- **推送**：firebase_messaging 统一封装（[D-014](./docs/00-decisions.md#d-014)）
- **UI 规范**：见 [docs/04-ui-ux-guidelines.md](./docs/04-ui-ux-guidelines.md)

### 前端（Web 后台）
- **框架**：Vue 3 + Composition API
- **状态管理**：Pinia
- **UI**：Element Plus
- **测试**：Playwright（关键流程）

### 测试
- **后端**：pytest + pytest-asyncio；目标覆盖率 ≥ 60%（MVP）
- **APP**：flutter_test + integration_test（关键流程：登录、发布需求、邀请接单、握手）
- **Web 后台 e2e**：Playwright（登录、查看合作看板、查看评价）
- **关键流程单测必覆盖**：邀请状态机、信用分计算、贝壳链接解析降级、推送消息体构造

---

## 编码时注意事项

### 业务逻辑
- ✅ 始终考虑**移动端适配**（按钮/卡片适合手指点击，最小 44pt）
- ✅ AI 生成内容**必须有明确用户确认步骤**，避免自动决策引发纠纷
- ✅ **数据脱敏**是默认行为，向对方展示前必须过滤敏感字段
- ✅ 邀请/方案都有**倒计时**，必须用 Redis（不要在内存里算）
- ✅ 状态变更要写 `audit_logs`
- ✅ APP 端要支持**离线缓存**（[D-018](./docs/00-decisions.md#d-018)）：Hive 存最近一次请求的列表
- ✅ 所有写接口必须走 `current_user` Depends 校验越权

### 异常处理
- ✅ **贝壳链接解析 MVP 降级**（[D-009](./docs/00-decisions.md#d-009)）：只存 URL + 简单可达性校验，不解析内容
- ✅ LLM 调用超时/失败 → 自动降级到规则匹配
- ✅ 微信授权失败 / Apple 登录失败 → 引导用户重试，记录错误码
- ✅ 上传实勘图失败 → 重试 + 提示，不丢用户数据

### 安全
- ✅ 所有写接口必须鉴权（JWT/session）
- ✅ 越权访问必须拦截（用户 A 不能操作用户 B 的房源）
- ✅ 文件上传校验 MIME + 大小，防止恶意文件
- ✅ SQL 拼接必须走 ORM 参数化
- ✅ **手机号 AES-256-GCM 加密存储**（[D-011](./docs/00-decisions.md#d-011)）：
  - 密钥从环境变量读取，**绝不**入库
  - 加密格式：`base64(iv) + ":" + base64(ciphertext) + ":" + base64(tag)`
  - 索引用 HMAC-SHA256 哈希以支持精确查询
  - MVP **不收集**身份证（避免合规复杂度）
- ✅ LLM 调用防护（[D-008](./docs/00-decisions.md#d-008)）：
  - **Soft cap ¥2000 / 月**（达此值通知管理员）
  - **Hard cap ¥5000 / 月**（达此值强制降级到规则匹配）
  - 网关层 token 计数 + 月度聚合
  - Sentry 集成 LLM 调用日志
- ✅ **APP 端安全**：
  - HTTPS Only（生产强制）
  - JWT 存 `flutter_secure_storage`（iOS Keychain / Android Keystore）
  - 考虑启用**证书固定（cert pinning）**
  - 不在日志/截屏/分享中泄露 token / 用户敏感信息

### 性能
- ✅ 列表查询必须分页（**Cursor 游标**，非 offset）
- ✅ Top 5 推荐结果**缓存 5 分钟**（避免重复计算）
- ✅ LLM 调用走异步任务，不要阻塞 HTTP 响应
- ✅ 大图上传 OSS 前客户端压缩
- ✅ **APP 端性能**：
  - 冷启动 < 2s
  - 列表帧率 ≥ 50fps
  - 图片懒加载
  - 下采样到显示尺寸（避免 4K 图放 100×100 缩略图）

---

## Vibe Coding 指南（AI 生成代码时遵守）

当使用 Claude / Codex / Cursor 生成代码时：

1. **先读 [docs/01-requirements.md](./docs/01-requirements.md)**，再开始动键盘
2. **明确文件归属**：新文件放在 `backend/app/domains/{module}/` 或 `mobile-app/lib/features/{module}/` 下，不要散落
3. **每个函数先想清楚输入输出**，再写实现
4. **API 接口定义与数据模型保持一致**（Pydantic model 名字 = 字段名）
5. **关键流程（如邀请状态机）写完必须画状态图或加状态注释**
6. **包含基本的错误处理和验证**，不允许 `except: pass`
7. **不要生成 TODO 占位**（除非明确告知是"待实现"）
8. **不要过度设计**（MVP 阶段拒绝工厂模式、依赖注入容器、复杂抽象）
9. **生成 SQL 后先确认**有没有 N+1、缺失索引
10. **生成前端组件后先确认**移动端断点（375px / 768px）

---

## 当前阶段

**MVP**。仅实现核心流程（房源录入 / 需求发布 / 智能匹配 Top 5 / 顺序邀约 / 方案握手 / 双向评价 / 信用分计算）。

**不做**：支付、分账、IM 通讯、跨城、经纪公司账号、视频带看、自动纠纷调解。

**重点验证**：匹配效率 + 合作闭环 + 用户留存。

---

## 目录约定（建议，v0.3）

```
RD/
├── CLAUDE.md                    ← 本文件
├── docs/                        ← 设计文档
│   ├── 00-decisions.md          ← 20 条决策记录（ADR）
│   ├── 01-requirements.md       ← 需求总文档 v0.3
│   ├── 02-architecture.md       ← 架构设计 v0.1
│   ├── 03-api-spec.md           ← API 规范 v0.1
│   └── 04-ui-ux-guidelines.md   ← UI/UX 设计规范 v0.1
├── schemas/                     ← 数据库 schema、迁移（待生成）
│   └── 001_init.sql
├── prototypes/                  ← 页面原型（待生成，可用 Figma 替代）
├── backend/                     ← 后端代码（待初始化，FastAPI）
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                ← 配置、日志、依赖、加密
│   │   ├── domains/             ← 业务域（auth, users, properties, ...）
│   │   ├── models/              ← SQLAlchemy models
│   │   ├── schemas/             ← Pydantic v2 schemas
│   │   ├── agents/              ← AI Agent 封装（llm_client, matcher, ...）
│   │   └── workers/             ← RQ 任务（watermark, credit_score, push）
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── docker-compose.yml
├── mobile-app/                  ← Flutter APP（待初始化，v0.3 新增）
│   ├── lib/
│   │   ├── main.dart
│   │   ├── core/                ← theme, network, storage, push, image
│   │   ├── features/            ← auth, home, demand, property, ...
│   │   ├── router/              ← go_router 配置
│   │   └── l10n/                ← 国际化（预留）
│   ├── assets/                  ← 图片、字体
│   ├── ios/                     ← iOS 原生工程
│   ├── android/                 ← Android 原生工程
│   └── pubspec.yaml
├── admin-web/                   ← Vue 后台（待初始化）
│   └── ...
└── _inbox/                      ← 原始资料归档（不参与构建）
    ├── source-01-ima-mvp-requirements.md
    ├── source-02-deepseek-development-doc.md
    └── source-03-deepseek-techstack-review.md
```

**Vibe Coding 时**：先根据模块路径判断文件应放在哪。例：
- 邀请状态机 → `backend/app/domains/invitations/state_machine.py`
- 匹配算法 → `backend/app/agents/matcher.py`
- 信用分计算 → `backend/app/domains/reviews/credit_score.py`
- 推荐卡片组件 → `mobile-app/lib/features/home/widgets/seller_card.dart`
- 倒计时组件 → `mobile-app/lib/core/widgets/countdown_text.dart`

---

## 变更记录

| 日期 | 变更 | 备注 |
| --- | --- | --- |
| 2026-06-04 | 初稿 | 基于 3 份原始资料整合 |
| 2026-06-04 | v0.2 | 11 个开放问题拍板；新增 [docs/00-decisions.md](./docs/00-decisions.md) 决策记录 |
| 2026-06-04 | v0.3 | **平台切换：WeChat MP → iOS/Android APP（Flutter）**；新增 D-012 ~ D-020 共 9 条 APP 相关决策；新增 [docs/02-architecture.md](./docs/02-architecture.md) / [03-api-spec.md](./docs/03-api-spec.md) / [04-ui-ux-guidelines.md](./docs/04-ui-ux-guidelines.md)；目录结构新增 `mobile-app/` |
| 2026-06-04 | v0.4 | 登录调整为**微信为主**（D-013）；新增 D-021 MVP 不阻塞开发；新增 [docs/00-summary.md](./docs/00-summary.md) 大白话摘要 |
