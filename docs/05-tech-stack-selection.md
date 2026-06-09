# HomeMatch 技术架构选型报告 v0.1

> 📌 **给技术负责人/老板拍板用的版本**。
> 配套文档：[01-requirements.md](01-requirements.md) · [02-architecture.md](02-architecture.md) · [00-decisions.md](00-decisions.md)
> 版本：v0.1（初稿，待复核）
> 日期：2026-06-04

---

## 0. 一句话总结

> **后端 Python+FastAPI，APP Flutter 跨端，AI 主力 DeepSeek，部署 Docker 上云，推送 APNs+FCM。不上 LangGraph、不上 ES、不上 Taro。**

---

## 1. 选型原则（5 条）

1. **MVP 优先**：能 4 周跑通验证 > 未来 1 年的扩展性
2. **主流成熟**：社区大、文档多、招人快、问题好搜
3. **团队友好**：降低学习成本，避免"招不到人"或"上手半年"
4. **可演进**：现在选的方案，二期能平滑升级到更复杂的（不锁死）
5. **性价比**：钱花在刀刃上，LLM 月预算 ≤ ¥5000

---

## 2. 架构总览（一图流）

```
┌────────────────────────────────────────────────────────────┐
│                       客户端                                 │
├──────────────┬──────────────┬──────────────────────────────┤
│  iOS APP     │ Android APP  │  Web 后台 (运营)             │
│  (Flutter)   │  (Flutter)   │  (Vue 3)                     │
└──────┬───────┴──────┬───────┴──────────────┬───────────────┘
       │ HTTPS        │ HTTPS                 │ HTTPS
       └──────────────┴──────────────────────┘
                      ▼
┌────────────────────────────────────────────────────────────┐
│                    FastAPI (Python)                          │
│              + slowapi 限流 + Sentry 监控                    │
└──────┬────────────┬────────────┬────────────┬───────────────┘
       │            │            │            │
       ▼            ▼            ▼            ▼
┌──────────┐  ┌────────┐  ┌──────────┐  ┌──────────────────────┐
│PostgreSQL│  │ Redis  │  │   RQ     │  │   第三方服务          │
│  15      │  │  7     │  │ Worker   │  │ • DeepSeek/Claude    │
└──────────┘  └────────┘  └────┬─────┘  │ • 阿里云 OSS         │
                               │         │ • 阿里云短信         │
                               ▼         │ • Firebase (FCM)     │
                       ┌──────────────┐  │ • APNs (Apple)       │
                       │  Pillow      │  └──────────────────────┘
                       │  水印任务     │
                       └──────────────┘
```

---

## 3. 后端技术栈（FastAPI 全家桶）

| 选型 | 用途 | 为什么选 | 放弃了什么 |
| --- | --- | --- | --- |
| **Python 3.11+** | 主语言 | AI 库最丰富（PyTorch/LangChain/Transformers）；团队学习成本低；FastAPI 同步 | Go：AI 生态弱，需多服务拆分 |
| **FastAPI 0.110+** | Web 框架 | 异步性能好；自动生成 OpenAPI 文档（Swagger）；Pydantic v2 类型校验一流 | Flask：老旧、异步支持差；Django：太重、ORM 与 SQLAlchemy 重复 |
| **PostgreSQL 15** | 主数据库 | 关系型+JSONB 混合；tsvector 全文检索够用；事务强一致；运维成熟 | MySQL：JSON 支持弱；MongoDB：MVP 阶段事务不够；SQLite：不能并发写 |
| **SQLAlchemy 2.0** | ORM | Python 生态最成熟；类型提示友好；支持异步；防止 SQL 注入 | Tortoise ORM：生态小、招人难；手写 SQL：易出错 |
| **Alembic** | DB 迁移 | SQLAlchemy 官方；自动生成迁移脚本；版本可回滚 | 手改表：开发灾难 |
| **Pydantic v2** | 数据校验 | FastAPI 原生；类型驱动；性能是 v1 的 5-50 倍 | marshmallow：性能差；手写校验：重复劳动 |
| **Redis 7** | 缓存 + 倒计时 + 队列 broker | 一专多能；24h 邀请倒计时天然适配；社区成熟 | Memcached：数据结构少；etcd：太重 |
| **RQ 1.16+** | 任务队列 | 单进程就能跑；Redis 当 broker 不用额外组件；异步任务（LLM/水印/推送）| Celery：配置复杂、对 MVP 过重；dramatiq：生态小 |
| **slowapi** | HTTP 限流 | 装饰器风格；基于 Redis；防刷防 DDoS | 手写限流：易漏边界 |
| **python-jose + passlib** | JWT + 密码（兜底用） | 行业标准 | PyJWT：API 略弱 |
| **cryptography** | AES 加密 | 敏感字段（手机号）加密 | pycryptodome：API 老 |
| **Pillow** | 图片水印 | 实勘图加水印 | OpenCV：太重 |
| **firebase-admin** | FCM 推送 | 官方 SDK；同时支持 APNs | 第三方推送服务：贵 |
| **aliyun-python-sdk-core** | 阿里云 OSS/短信 | 官方 SDK | 七牛/腾讯云：业务不用 |
| **pydantic-settings** | 配置管理 | 12-factor；类型安全 | python-decouple：功能弱 |
| **uv** | 依赖管理 | 比 pip 快 10-100 倍；lockfile 锁定；Rust 写的 | pip：慢、依赖易漂；Poetry：慢 |
| **pytest + pytest-asyncio** | 测试 | 生态最广；异步测试友好 | unittest：太老 |

### 3.1 后端架构风格：**按业务域分层（DDD-lite）**

```
backend/app/
├── core/           # 基础设施（配置、日志、加密、限流、错误处理）
├── domains/        # 业务域（auth / users / properties / demands / ...）
│   └── {domain}/
│       ├── router.py      # FastAPI 路由
│       ├── service.py     # 业务逻辑
│       ├── schemas.py     # Pydantic 模型
│       ├── models.py      # SQLAlchemy ORM（也放 models/ 下）
│       └── dependencies.py
├── models/         # 跨域共享的 ORM
├── schemas/        # 跨域共享的 Pydantic
├── agents/         # AI Agent 封装（llm_client / matcher / review_analyzer）
└── workers/        # RQ 任务（watermark / push / credit_score）
```

- **不采用** 微服务（MQ/Service Mesh/K8s）—— MVP 单体足够
- **不采用** 严格 DDD（聚合根、领域事件）—— 团队成本太高
- **采用** 模块化单体（Modular Monolith）—— 内部按域切分，二期可拆分

---

## 4. APP 端技术栈（Flutter 全家桶）

| 选型 | 用途 | 为什么选 | 放弃了什么 |
| --- | --- | --- | --- |
| **Flutter 3.x (Dart 3)** | 跨端框架 | 一码双端；Material 3 + Cupertino；性能接近原生；国内大厂（阿里/字节/腾讯）生产验证 | React Native：Bridge 性能损耗；原生（Swift+Kotlin）：2 倍开发成本；uni-app/Taro：体验偏 H5 |
| **Riverpod 2.x** | 状态管理 | 类型安全；可测试；编译期查错；社区主流 | Provider：太老；Bloc：样板代码多；GetX：反模式 |
| **go_router** | 路由 | 声明式；支持 Deep Link；嵌套路由 | Navigator 2.0：API 复杂；AutoRoute：依赖重 |
| **dio + retrofit** | 网络层 | 拦截器机制；代码生成；类型安全 | http：功能弱；chopper：生态小 |
| **Hive 2.x** | 本地存储 | 纯 Dart、快、支持复杂对象；列表缓存首选 | SharedPreferences：KV 限制；Isar：依赖原生库 |
| **flutter_secure_storage** | 存 Token | 调 iOS Keychain / Android Keystore | Hive 存 Token：明文风险 |
| **firebase_messaging** | 推送 | APNs + FCM 统一封装；Flutter 官方推荐 | 个推/友盟：贵、SDK 重 |
| **image_picker + flutter_image_compress** | 选图 + 压缩 | 自动清 EXIF；客户端预压缩省流量 | wechat_assets_picker：只选图；image：API 复杂 |
| **cached_network_image** | 图片缓存 | 懒加载、占位、错误图 | ExtendedImage：太重 |
| **connectivity_plus** | 网络监听 | 弱网/断网检测；离线模式 | 手写轮询：浪费电 |
| **fluwx** 或 **wechat_kit** | 微信登录/分享 | 官方微信 SDK 封装 | 手撸：维护成本高 |
| **sign_in_with_apple** | Apple 登录 | iOS 必选合规 | — |
| **intl + flutter_localizations** | 国际化 | 预留 i18n；MVP 只做简中 | — |
| **sentry_flutter** | 崩溃监控 | 错误 + 性能 | Bugly：停止维护 |

### 4.1 APP 架构风格：**Feature-first Clean Architecture**

```
mobile-app/lib/
├── main.dart
├── app.dart                  # MaterialApp + 主题 + 路由
├── core/                     # 基础设施
│   ├── theme/                # 颜色/字体/间距
│   ├── network/              # dio 客户端 + 拦截器
│   ├── storage/              # Hive 封装
│   ├── push/                 # firebase_messaging 封装
│   ├── image/                # 压缩/EXIF 清除
│   ├── auth/                 # Token 管理
│   ├── analytics/            # Sentry + 事件埋点
│   ├── widgets/              # 通用组件（按钮、卡片、列表项...）
│   └── errors/               # 异常类
├── features/                 # 按业务功能分模块
│   └── {feature}/
│       ├── data/             # repository（数据访问）
│       ├── domain/           # 业务模型 + 用例
│       └── presentation/     # UI（pages + widgets）
├── router/                   # go_router 配置
└── l10n/                     # 国际化资源
```

- **不采用** 严格 Clean Architecture（太多抽象层）—— MVP 不需要
- **采用** Feature-first 分模块 + 简化版分层（data / domain / presentation）—— 够用、好测试、好拆分
- **状态管理** 用 Riverpod 2.x + `@riverpod` 代码生成

---

## 5. Web 管理后台技术栈

| 选型 | 用途 | 为什么选 |
| --- | --- | --- |
| **Vue 3 + Composition API** | 框架 | 国内生态最广；Element Plus 完善；招人快 |
| **TypeScript** | 语言 | 类型安全；减少维护成本 |
| **Pinia** | 状态管理 | Vue 官方推荐 |
| **Element Plus** | UI 库 | 房产业务类后台标配；表格/表单/审批流组件齐全 |
| **Vite 5** | 构建 | 启动快、HMR 流畅 |
| **Axios** | HTTP | 拦截器机制；业界标准 |
| **Vue Router 4** | 路由 | 官方 |
| **Playwright** | E2E 测试 | 跨浏览器；比 Cypress 更适合后台 |

---

## 6. AI / LLM 技术栈

| 选型 | 用途 | 为什么选 | 成本 |
| --- | --- | --- | --- |
| **DeepSeek-V3** | 主力模型（推荐生成、方案辅助、链接解析） | 性价比最高；中文强；OpenAI API 兼容 | ¥0.001/1k tokens |
| **Claude Sonnet** 或 **GPT-4o** | 兜底模型（评价异常检测、复杂语义） | 任务精度高 | 较贵，按调用计费 |
| **pg_trgm + tsvector** | 文本相似度/全文检索 | PG 内置，MVP 不上 ES | 免费 |
| **scikit-learn** | 简单匹配算法（规则打分 + 加权） | 团队熟悉；解释性强 | 免费 |
| **LangChain**（**仅必要时**） | LLM 编排 | 二期需要复杂 Agent 编排时再上 | — |
| **❌ LangGraph** | — | **MVP 不上**，流程是线性状态机，引入增加学习成本 | — |

### 6.1 任务路由规则
- 简单任务（匹配打分、模板填充）→ **不调 LLM**，用规则 + 缓存
- 中等任务（推荐解释、方案辅助）→ DeepSeek-V3
- 高精度任务（评价异常、纠纷调解）→ Claude / GPT-4o
- 所有 LLM 调用经统一 `LLMClient` 封装，**带重试 / 降级 / 限流**

### 6.2 成本控制
- 月度预算：**Soft cap ¥2,000 / Hard cap ¥5,000**
- 超出自动降级到规则匹配
- 所有调用打 Sentry + 自建 `event_logs`

---

## 7. 第三方服务依赖

| 服务 | 用途 | 选型理由 | MVP 阶段 | 资质要求 |
| --- | --- | --- | --- | --- |
| **阿里云 OSS** | 文件存储（实勘图、头像、合作备忘录） | 行业标准；支持 STS 直传；CDN 加速 | 测试 Bucket 免费 | 营业执照 |
| **阿里云短信** | 验证码、通知 | 大陆首选；100 条/天免费测试 | 测试签名 | 营业执照 + 业务场景说明 |
| **DeepSeek API** | LLM 主力 | 性价比；中文强 | 充值即用 | — |
| **Anthropic Claude API** | LLM 兜底 | 质量高 | 充值即用 | 信用卡 |
| **Firebase** | FCM 推送 | 行业标准；Flutter 友好 | 免费层够用 | 海外账号（公司或个人均可） |
| **Apple APNs** | iOS 推送 | Apple 官方 | 必须 | Apple Developer 账号（$99/年） |
| **Sentry** | 错误监控 | 业界标配；免费层够 MVP | 免费 | — |
| **微信开放平台** | 微信登录、分享 | 国内必备 | **测试号**先跑 | 营业执照+对公验证（正式） |
| **Apple Developer** | iOS 上架 | 必选 | — | $99/年 + D-U-N-S 编号 |
| **华为/小米/OPPO/vivo 开发者** | Android 上架 | 必选 | — | 营业执照+软著 |

> **D-021 重要**：MVP 阶段不阻塞开发，使用各服务的"开发模式/测试额度"验证功能。资质申请可与开发并行（4-6 周）。

---

## 8. DevOps 与工具链

| 选型 | 用途 |
| --- | --- |
| **Docker + Docker Compose** | 本地开发 + 单机部署；二期迁 K8s |
| **GitHub Actions** | CI（自动跑测试）+ CD（自动部署） |
| **fastlane** | iOS/Android 自动化打包、签名、上传 |
| **Nginx** | 反向代理 + HTTPS 终止 + 静态资源 |
| **阿里云 ACK** | 二期 K8s 托管（生产环境） |
| **阿里云 RDS PostgreSQL** | 托管数据库（生产） |
| **阿里云 Redis** | 托管缓存（生产） |
| **阿里云 CDN** | 静态资源 + OSS 加速 |
| **.env + 12-factor** | 配置管理（不硬编码、不入库） |

### 8.1 本地开发环境

```bash
# 一行启动 PG + Redis
docker compose up -d postgres redis

# 后端开发模式
uv run uvicorn app.main:app --reload --port 8000

# APP 端
cd mobile-app
flutter run                          # 跑模拟器
flutter run -d <device-id>          # 跑真机
```

---

## 9. 选型对比表（"拒绝了什么、为什么"汇总）

| 类别 | ❌ 拒绝了 | 为什么 |
| --- | --- | --- |
| 后端语言 | Go | AI 生态弱；团队 Python 熟 |
| 后端框架 | Django | 太重；ORM 重复 |
| 后端框架 | Flask | 老旧；异步弱 |
| 数据库 | MySQL | JSON 支持弱 |
| 数据库 | MongoDB | MVP 事务不够 |
| 数据库 | Elasticsearch | 10 万级数据不需要；运维贵 |
| 缓存 | Memcached | 数据结构少 |
| 队列 | Celery | 对 MVP 过重 |
| ORM | Tortoise / SQLModel | 生态小 |
| 跨端 | React Native | Bridge 性能损耗；团队不熟 RN |
| 跨端 | 原生（Swift+Kotlin） | 2 倍开发成本 |
| 跨端 | uni-app / Taro | 体验偏 H5 |
| 跨端 | KMM | 学习成本高 |
| 状态管理 | Provider / Bloc | Riverpod 更现代 |
| 推送 SDK | 个推/友盟 | 贵；SDK 重 |
| LLM 框架 | LangGraph | MVP 不需要；增加学习成本 |
| 微服务 | K8s + Service Mesh | 单体足够 |
| 严格 DDD | 聚合根/领域事件 | 团队成本高 |
| 严格 Clean Arch | 4-5 层抽象 | MVP 过设计 |
| SaaS 化 | 多租户 | MVP 不做 |
| 支付 | 微信支付/支付宝 | MVP 不分账 |
| IM | 融云/环信 | MVP 用推送+微信分享代替 |

---

## 10. 总结：3 行话告诉团队

1. **后端**：Python + FastAPI + PG + Redis + RQ，写起来快，AI 友好，4 周跑通核心流程
2. **APP**：Flutter 一码双端，主流房产 APP 体验，3 周出可用版本
3. **AI**：DeepSeek 主力 + Claude 兜底，月预算 ≤ ¥5000，规则匹配做降级

> **总成本估算**：开发期（4-8 周）+ 服务器（¥500-1500/月）+ LLM（¥300-500/月）+ 短信（¥100-300/月）≈ **¥1000-2000/月 运营成本**。业务资质到位后上架再增 Apple Developer $99/年 + 安卓市场 0-600 元/市场。

---

## 11. 立即可装的依赖清单

### 11.1 后端

```bash
# Python 依赖（pyproject.toml）
fastapi = "^0.110"
uvicorn[standard] = "^0.27"
sqlalchemy = "^2.0"
alembic = "^1.13"
psycopg2-binary = "^2.9"
redis = "^5.0"
rq = "^1.16"
pydantic = "^2.6"
pydantic-settings = "^2.2"
python-jose = {extras = ["cryptography"], version = "^3.3"}
passlib = "^1.7"
slowapi = "^0.1.9"
cryptography = "^42.0"
pillow = "^10.2"
firebase-admin = "^6.5"
oss2 = "^2.18"  # 阿里云 OSS

# 测试
pytest = "^8.0"
pytest-asyncio = "^0.23"
httpx = "^0.27"  # 测试 API
```

### 11.2 APP（pubspec.yaml）

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.5
  go_router: ^14.0.0
  dio: ^5.4.0
  retrofit: ^4.0.0
  hive: ^2.2.3
  hive_flutter: ^1.1.0
  flutter_secure_storage: ^9.0.0
  firebase_core: ^2.27.0
  firebase_messaging: ^14.7.0
  image_picker: ^1.0.0
  flutter_image_compress: ^2.2.0
  cached_network_image: ^3.3.0
  connectivity_plus: ^6.0.0
  fluwx: ^5.4.0  # 微信
  sign_in_with_apple: ^5.0.0
  intl: ^0.19.0
  sentry_flutter: ^8.0.0

dev_dependencies:
  build_runner: ^2.4.0
  riverpod_generator: ^2.4.0
  hive_generator: ^2.0.1
  retrofit_generator: ^8.0.0
  json_serializable: ^6.7.0
  freezed: ^2.4.0
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter
```

### 11.3 docker-compose.yml（本地开发）

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: homa
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: homa
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  rq-worker:
    build: ./backend
    command: rq worker --url redis://redis:6379
    depends_on: [redis, postgres]
    volumes: [./backend:/app]
volumes:
  pgdata:
```

---

## 12. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-06-04 | 初稿，汇总 v0.4 决策后的技术选型 |
