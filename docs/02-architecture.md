# HomeMatch 架构设计 v0.1

> 配套文档：[01-requirements.md](01-requirements.md) | [03-api-spec.md](03-api-spec.md) | [04-ui-ux-guidelines.md](04-ui-ux-guidelines.md)
> 文档版本：v0.1（初稿，待复核）
> 撰写日期：2026-06-04

---

## 1. 总体架构

HomeMatch 整体采用**经典 3 层 + 第三方服务**架构：APP 端（Flutter）/ Web 后台（Vue）→ API 网关（FastAPI）→ 业务服务 + 数据层 + 第三方服务。

```
┌──────────────────────────────────────────────────────────────────────┐
│                          客户端 (Clients)                              │
├──────────────────────┬──────────────────────┬──────────────────────┤
│   iOS / Android APP  │   Web 管理后台        │   运营 CLI / 脚本     │
│   (Flutter 3.x)      │   (Vue 3)            │                       │
└──────────┬───────────┴──────────┬───────────┴──────────┬───────────┘
           │ HTTPS / JSON          │ HTTPS / JSON         │ HTTPS
           ▼                        ▼                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    API 网关 (FastAPI + Nginx)                          │
│  • 鉴权 (JWT)  • 限流 (slowapi)  • 错误处理  • 请求日志                 │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       业务服务 (FastAPI App)                            │
├──────────────────────────────────────────────────────────────────────┤
│  auth/        users/        properties/      demands/                │
│  matching/    invitations/  proposals/       cooperations/           │
│  reviews/     devices/      push/            upload/                 │
│  agents/      events/       admin/                                   │
└──────┬──────────┬───────────┬────────────┬────────────┬─────────────┘
       │          │           │            │            │
       ▼          ▼           ▼            ▼            ▼
┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐
│PostgreSQL│ │ Redis  │ │  RQ      │ │  Sentry  │ │  第三方服务     │
│  15      │ │  7     │ │  Worker  │ │          │ │                │
└──────────┘ └────────┘ └────┬─────┘ └──────────┘ │ 阿里云 OSS     │
                              │                    │ 阿里云短信     │
                              │                    │ DeepSeek API   │
                              ▼                    │ Firebase (FCM) │
                       ┌──────────────┐             │ Apple Push     │
                       │  Pillow       │             └────────────────┘
                       │  水印任务      │
                       └──────────────┘
```

---

## 2. 技术栈概览

| 层次 | 选型 | 版本 |
| --- | --- | --- |
| **APP 端** | Flutter + Dart | 3.x / Dart 3 |
| **APP 状态管理** | Riverpod | 2.x |
| **APP 路由** | go_router | 最新 |
| **APP 网络** | dio + retrofit | 最新 |
| **APP 存储** | Hive | 2.x |
| **Web 后台** | Vue 3 + Element Plus | Vue 3.4+ |
| **API 服务** | Python + FastAPI | 3.11+ / 0.110+ |
| **数据库** | PostgreSQL | 15 |
| **缓存/队列** | Redis | 7 |
| **任务队列** | RQ | 1.16+ |
| **ORM** | SQLAlchemy | 2.0+ |
| **迁移** | Alembic | 最新 |
| **推送（iOS）** | APNs (HTTP/2) | — |
| **推送（Android）** | FCM | — |
| **对象存储** | 阿里云 OSS | — |
| **短信** | 阿里云短信 | — |
| **AI** | DeepSeek-V3 + Claude | — |
| **监控** | Sentry | 最新 |
| **CI/CD** | GitHub Actions + fastlane | — |

---

## 3. 后端模块划分

后端采用**按业务域（Domain）分层**，避免按"controller/service/model"简单分层导致后期难以演化。

```
backend/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── core/                      # 基础设施
│   │   ├── config.py              # pydantic-settings 配置
│   │   ├── security.py            # JWT 加密/解密
│   │   ├── database.py            # SQLAlchemy 引擎
│   │   ├── redis.py               # Redis 客户端
│   │   ├── logging.py             # 结构化日志
│   │   ├── errors.py              # 统一异常类
│   │   ├── pagination.py          # Cursor 分页
│   │   ├── ratelimit.py           # 限流
│   │   └── crypto.py              # AES 加密
│   │
│   ├── domains/                   # 业务域
│   │   ├── auth/                  # 认证
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   └── dependencies.py    # FastAPI Depends
│   │   ├── users/
│   │   ├── properties/            # 房源
│   │   ├── demands/               # 需求
│   │   ├── matching/              # 匹配算法
│   │   ├── invitations/           # 邀请
│   │   ├── proposals/             # 方案
│   │   ├── cooperations/          # 合作
│   │   ├── reviews/               # 评价
│   │   ├── devices/               # 设备/推送
│   │   ├── push/                  # 推送发送
│   │   ├── upload/                # OSS STS 签名
│   │   ├── events/                # 事件日志
│   │   ├── agents/                # AI Agent 封装
│   │   │   ├── link_parser.py     # 贝壳链接解析（占位）
│   │   │   ├── matcher.py         # 匹配算法
│   │   │   ├── proposal_gen.py    # 方案生成
│   │   │   ├── review_analyzer.py # 评价异常检测
│   │   │   └── llm_client.py      # LLM 统一客户端
│   │   └── admin/                 # 运营后台 API
│   │
│   ├── models/                    # SQLAlchemy ORM
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── property.py
│   │   └── ...
│   │
│   ├── schemas/                   # Pydantic v2
│   │   ├── common.py
│   │   ├── user.py
│   │   └── ...
│   │
│   └── workers/                   # RQ 任务
│       ├── queue.py
│       ├── watermark.py           # Pillow 加水印
│       ├── credit_score.py        # 每日信用分重算
│       ├── push_send.py           # 推送发送
│       └── expire_checker.py      # 邀请/方案超时检查
│
├── tests/                         # pytest
├── alembic/                       # 数据库迁移
├── pyproject.toml                 # uv 依赖
├── docker-compose.yml             # 本地开发
├── Dockerfile
└── .env.example
```

---

## 4. APP 端架构（Flutter）

### 4.1 分层

```
mobile-app/
├── lib/
│   ├── main.dart                  # 入口
│   ├── app.dart                   # MaterialApp + Router
│   │
│   ├── core/                      # 基础设施
│   │   ├── config/
│   │   ├── theme/                 # 主题、颜色、字体
│   │   ├── network/               # dio + 拦截器
│   │   ├── storage/               # Hive 封装
│   │   ├── router/                # go_router 配置
│   │   ├── errors/                # 异常类
│   │   ├── push/                  # firebase_messaging 封装
│   │   ├── image/                 # 图片压缩、EXIF 清除
│   │   ├── auth/                  # Token 管理、刷新
│   │   ├── analytics/             # Sentry + 事件埋点
│   │   └── widgets/               # 通用组件库
│   │
│   ├── features/                  # 按业务域分模块
│   │   ├── auth/                  # 登录/注册
│   │   │   ├── data/              # repository
│   │   │   ├── domain/            # 业务逻辑
│   │   │   └── presentation/      # UI
│   │   ├── home/                  # 首页/匹配推荐
│   │   ├── demand/                # 需求发布
│   │   ├── property/              # 房源录入
│   │   ├── invitation/            # 邀请响应
│   │   ├── proposal/              # 方案提交/确认
│   │   ├── cooperation/           # 合作看板
│   │   ├── review/                # 评价
│   │   ├── profile/               # 个人中心
│   │   └── notification/          # 通知中心
│   │
│   └── l10n/                      # 国际化
│
├── assets/                        # 图片、字体
├── ios/                           # iOS 原生工程
├── android/                       # Android 原生工程
├── pubspec.yaml
└── README.md
```

### 4.2 关键架构决策

#### 状态管理（Riverpod）

```dart
// 推荐用 @riverpod 代码生成
@riverpod
class DemandForm extends _$DemandForm {
  @override
  DemandFormState build() => const DemandFormState();
  
  void updatePriceRange(RangeValues range) { ... }
  void submit() async { ... }
}
```

#### 网络层（dio 拦截器）

```dart
// 拦截器链（按顺序）
1. LogInterceptor        // 打印请求
2. AuthInterceptor       // 注入 JWT
3. RefreshInterceptor    // 401 时自动 refresh
4. ErrorInterceptor      // 统一错误处理
5. SentryInterceptor     // 上报异常
```

#### 路由（go_router）

```dart
// 路由表
/login                    // 登录
/tabs                     // Tab 主页
  /home                   // 推荐
  /cooperations           // 合作
  /profile                // 我的
/demands/new              // 需求发布
/properties/new           // 房源录入
/invitations/:id          # 邀请详情
/cooperations/:id         # 合作详情
/notifications            # 通知中心
```

#### 缓存策略

| 数据 | 缓存位置 | 过期 |
| --- | --- | --- |
| 登录 token | `flutter_secure_storage`（Keychain/Keystore） | Refresh Token 30 天 |
| 用户基本信息 | Hive | 24h |
| 推荐列表 | Hive | 5min |
| 合作列表 | Hive | 1min |
| 房源列表 | Hive | 5min |

---

## 5. Web 后台架构（Vue 3）

```
admin-web/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   ├── stores/             # Pinia
│   ├── api/                # axios 封装
│   ├── views/
│   │   ├── Login.vue
│   │   ├── Dashboard.vue
│   │   ├── Users.vue
│   │   ├── Properties.vue
│   │   ├── Demands.vue
│   │   ├── Cooperations.vue
│   │   ├── Reviews.vue
│   │   ├── Reports.vue
│   │   └── AppVersions.vue
│   ├── components/
│   └── utils/
├── public/
├── package.json
└── vite.config.ts
```

---

## 6. 数据流

### 6.1 推荐生成数据流

```
买方发布需求
    ↓
demands 写入 PG
    ↓
matching 服务异步计算
    ↓
查询 properties（区域/价格/户型）
    ↓
计算匹配分数（多维加权）
    ↓
取 Top 5 sellers
    ↓
写 inv_recommendations 表（缓存 5min）
    ↓
返回给 APP
```

### 6.2 推送数据流

```
关键事件发生（如：新邀请）
    ↓
写入 PG（如 invitations）
    ↓
触发 RQ 任务
    ↓
PushService 查 devices 表拿 fcm_token
    ↓
调 Firebase Admin SDK
    ↓
FCM / APNs 推送
    ↓
APP 端 firebase_messaging 接收
    ↓
通知栏弹出 / APP 内更新
```

### 6.3 图片上传数据流

```
APP 选图/拍照
    ↓
客户端 flutter_image_compress 压缩 + 清 EXIF
    ↓
APP 请求 /v1/upload/sign 拿 STS Token
    ↓
APP 用 STS Token 直传 OSS
    ↓
OSS 触发回调（可选）/ APP 通知后端
    ↓
RQ 任务：Pillow 加水印 → 覆盖回 OSS
    ↓
property.images[] 更新
```

---

## 7. 关键设计

### 7.1 状态机（邀请）

```python
# app/domains/invitations/state_machine.py
from transitions import Machine

states = ['pending', 'accepted', 'rejected', 'expired', 'proposal_review', 
          'handshaked', 'in_progress', 'pending_review', 'completed', 'closed']

transitions = [
    {'trigger': 'accept', 'source': 'pending', 'dest': 'accepted'},
    {'trigger': 'reject', 'source': 'pending', 'dest': 'rejected'},
    {'trigger': 'expire', 'source': 'pending', 'dest': 'expired'},
    {'trigger': 'submit_proposal', 'source': 'accepted', 'dest': 'proposal_review'},
    {'trigger': 'confirm', 'source': 'proposal_review', 'dest': 'handshaked'},
    {'trigger': 'decline', 'source': 'proposal_review', 'dest': 'closed'},
    # ...
]

class InvitationStateMachine:
    def __init__(self, invitation):
        self.invitation = invitation
        self.machine = Machine(
            model=self.invitation,
            states=states,
            transitions=transitions,
            initial='pending',
        )
```

### 7.2 信用分计算

```python
# app/domains/reviews/credit_score.py
def compute_credit_score(user_id: int) -> float:
    """每日定时任务调用，结果缓存到 users.credit_score"""
    reviews = get_user_reviews(user_id)
    rating_avg = sum(r.rating for r in reviews) / len(reviews) if reviews else 3.0
    
    activity_count = count_recent_responses(user_id, days=30)
    activity_factor = min(1.0, 0.3 + 0.7 * min(1, activity_count / 10))
    
    base_score = rating_avg * 20
    return round(base_score * activity_factor, 1)
```

### 7.3 LLM 调用

```python
# app/domains/agents/llm_client.py
class LLMClient:
    def __init__(self):
        self.deepseek = OpenAI(base_url="https://api.deepseek.com", api_key=settings.DEEPSEEK_KEY)
        self.claude = anthropic.Anthropic(api_key=settings.ANTHROPIC_KEY)
        self.monthly_tokens = 0
    
    async def complete(self, prompt: str, task_type: str = "default") -> str:
        # 月度预算检查
        if self.monthly_tokens > settings.LLM_HARD_CAP:
            return self._fallback(prompt, task_type)
        
        # 任务路由
        if task_type == "review_anomaly":
            return await self._call_claude(prompt)
        else:
            return await self._call_deepseek(prompt)
```

### 7.4 限流

```python
# app/core/ratelimit.py
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

# HTTP 层
@app.post("/v1/auth/sms-code")
@limiter.limit("5/minute;30/hour")
async def send_sms_code(...): ...

# LLM 层（Redis 滑动窗口）
async def check_llm_quota(user_id: int) -> bool:
    key = f"llm:quota:{user_id}:{current_month()}"
    used = await redis.incr(key)
    if used == 1:
        await redis.expire(key, 30 * 86400)  # 30 天
    return used <= settings.LLM_USER_LIMIT
```

---

## 8. 部署拓扑

### 8.1 开发环境

```
localhost
├── 5432  PostgreSQL
├── 6379  Redis
├── 8000  FastAPI (uvicorn --reload)
├── 8001  RQ Worker
├── 5173  Admin Web (Vite dev)
└── Flutter Emulator / 真机
```

### 8.2 测试 / 生产环境

```
阿里云 ECS × 2 (4C8G)
├── 1: API 服务 (FastAPI × 2 进程 + Nginx)
└── 2: RQ Worker × 1 + 监控

阿里云 RDS PostgreSQL 15 (1C2G 起)
阿里云 Redis (1G 起)
阿里云 OSS (Standard)
阿里云短信
DeepSeek API
Firebase (海外账号)
```

> 初期单机起步，用户量起来再拆。

---

## 9. 第三方服务依赖

| 服务 | 用途 | 关键配置 |
| --- | --- | --- |
| **阿里云 OSS** | 实勘图、合作备忘录 | Bucket 名、Region、STS 角色 |
| **阿里云短信** | 验证码、通知 | 签名、模板、AccessKey |
| **DeepSeek** | LLM 主力 | API Key、月预算 |
| **Anthropic Claude** | LLM 兜底 | API Key |
| **Firebase** | FCM 推送 | project_id、Service Account JSON |
| **Apple Developer** | APNs + App Store | 证书、Bundle ID、Team ID |
| **Sentry** | 错误监控 | DSN、环境（dev/prod） |
| **App Store Connect** | iOS 分发 | Apple ID |
| **国内安卓市场** | Android 分发 | 各市场账号（华为/小米/OPPO/vivo/应用宝） |

---

## 10. 安全设计

| 维度 | 措施 |
| --- | --- |
| **通信** | HTTPS Only（生产强制）；iOS/Android 证书固定（cert pinning） |
| **认证** | JWT（Access 2h + Refresh 30d）；Refresh Token 存 Secure Storage |
| **越权** | 所有写接口通过 `current_user` Depends 校验资源所有权 |
| **数据加密** | 手机号 AES-256-GCM（[D-011](00-decisions.md#d-011)）；身份证暂不收集 |
| **SQL 注入** | 全部走 SQLAlchemy 参数化 |
| **XSS** | APP 端默认不渲染 HTML；Web 后台 CSP 头 |
| **CSRF** | 纯 API + JWT 鉴权，天然防 CSRF |
| **文件上传** | MIME + 扩展名 + 大小校验；OSS STS Token 限时（5min） |
| **短信防刷** | 单手机号 60s 重发限制 + 5 次错误锁定 1h |
| **API 防滥用** | slowapi 限流 + Redis 滑动窗口 |
| **审计** | `audit_logs` 表 append-only；关键操作带 `request_id` |

---

## 11. 性能与扩展

| 指标 | 目标 | 措施 |
| --- | --- | --- |
| **API 响应** | P95 < 500ms | 异步 I/O、Redis 缓存、PG 索引 |
| **推荐生成** | < 3s | 预计算 + 物化视图 + 5min 缓存 |
| **推送延迟** | < 5s | RQ 异步 + 失败重试 3 次 |
| **APP 冷启动** | < 2s | Flutter AOT、懒加载、启动预热 |
| **图片加载** | 首屏 < 1s | OSS CDN + 客户端缓存 + WebP |
| **PG 连接** | 100 并发 | PgBouncer 连接池 |

---

## 12. 监控告警

| 维度 | 工具 | 告警阈值 |
| --- | --- | --- |
| **API 异常** | Sentry | 错误率 > 1% 通知 |
| **API 性能** | Sentry | P95 > 2s 通知 |
| **PG 慢查询** | PG `pg_stat_statements` | > 1s 记录 |
| **Redis 内存** | 阿里云监控 | > 80% 告警 |
| **LLM 成本** | 自建计数 | 月支出 > ¥2000 通知 |
| **推送失败率** | 自建日志 | > 5% 通知 |
| **APP 崩溃率** | Sentry | > 0.5% 通知 |

---

## 13. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-06-04 | 初稿，配合 v0.3 需求文档 |
