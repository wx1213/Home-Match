# HomeMatch Backend

> 北京二手房独立经纪人撮合评价平台 - 后端服务
> FastAPI + PostgreSQL + Redis + RQ

---

## 🏃 快速开始（5 分钟跑起来）

### 方式 1：本地 Python（最快，验证代码逻辑）

```bash
# 1. 进入项目
cd RD/backend

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖（核心即可，不装 dev 也能跑）
pip install fastapi uvicorn[standard] pydantic pydantic-settings \
            sqlalchemy alembic psycopg2-binary redis rq \
            python-jose[cryptography] passlib[bcrypt] \
            cryptography slowapi httpx pillow \
            email-validator phonenumbers

# 4. 复制环境变量
cp .env.example .env

# 5. 启动（不需要 PG/Redis 也能起，只是个别接口会失败）
uvicorn app.main:app --reload --port 8000

# 6. 浏览器访问
# Swagger UI: http://localhost:8000/docs
# ReDoc:     http://localhost:8000/redoc
# 健康检查:   http://localhost:8000/v1/health
```

### 方式 2：Docker Compose（推荐，完整环境）

```bash
# 1. 启动 PG + Redis
docker compose up -d postgres redis

# 2. 安装 Python 依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. 跑数据库迁移
alembic upgrade head

# 4. 启动 API
uvicorn app.main:app --reload

# 5. (新终端) 启动 RQ Worker
rq worker --url redis://localhost:6379/0
```

---

## 📂 项目结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── core/                   # 基础设施
│   │   ├── config.py           # 配置（pydantic-settings）
│   │   ├── database.py         # SQLAlchemy 引擎 + Session
│   │   ├── redis_client.py     # Redis 客户端
│   │   ├── security.py         # JWT + 密码
│   │   ├── crypto.py           # AES-256 手机号加密
│   │   ├── logging.py          # JSON 结构化日志
│   │   ├── errors.py           # 业务异常 + 统一错误处理
│   │   └── ratelimit.py        # slowapi 限流
│   ├── api/v1/                 # API 路由汇总
│   │   ├── router.py
│   │   └── health.py
│   ├── domains/                # 业务域
│   │   └── auth/               # 认证域
│   │       ├── router.py       # 路由
│   │       ├── service.py      # 业务逻辑
│   │       └── schemas.py      # Pydantic 模型
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── base.py
│   │   └── user.py
│   ├── schemas/                # 跨域 Pydantic
│   │   └── common.py
│   ├── agents/                 # AI Agent 封装（待开发）
│   └── workers/                # RQ 任务（待开发）
├── alembic/                    # 数据库迁移
│   ├── env.py
│   └── versions/
│       └── 0001_init_users.py
├── tests/                      # pytest 测试
│   ├── conftest.py
│   └── test_health.py
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🔌 当前已实现的接口

| Method | Path | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/` | 服务信息 | ❌ |
| GET | `/v1/health` | 健康检查（DB+Redis） | ❌ |
| POST | `/v1/auth/sms-code` | 发送短信验证码 | ❌ |
| POST | `/v1/auth/login` | 短信登录（兜底） | ❌ |
| POST | `/v1/auth/wechat-login` | **微信登录（主）** | ❌ |
| POST | `/v1/auth/apple-login` | Apple 登录（iOS 必选） | ❌ |
| POST | `/v1/auth/refresh` | 刷新 Token | ❌ |
| GET | `/v1/auth/me` | 当前用户信息 | ✅ |
| GET | `/docs` | Swagger UI | ❌ |
| GET | `/redoc` | ReDoc | ❌ |

> 完整接口规范见 [../docs/03-api-spec.md](../docs/03-api-spec.md)

---

## 🧪 验证功能

### 1. 看 Swagger UI
浏览器打开 `http://localhost:8000/docs`

### 2. 跑测试
```bash
pytest
# 输出示例：
# tests/test_health.py::test_root PASSED
# tests/test_health.py::test_docs_available PASSED
# tests/test_health.py::test_openapi_available PASSED
# tests/test_health.py::test_health_check PASSED
# tests/test_health.py::test_sms_code_validation PASSED
```

### 3. 测试短信登录流程（需要 Redis）
```bash
# 1. 启动 Redis
docker compose up -d redis

# 2. 启动后端
uvicorn app.main:app --reload

# 3. 发验证码（mock 模式验证码固定 1234）
curl -X POST http://localhost:8000/v1/auth/sms-code \
  -H "Content-Type: application/json" \
  -d '{"phone": "13800138000", "purpose": "login"}'

# 4. 登录
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "13800138000", "sms_code": "1234"}'

# 期望返回 access_token + user 信息
```

### 4. 测试微信登录（mock 模式）
```bash
# 没配 AppID 时自动用 mock
curl -X POST http://localhost:8000/v1/auth/wechat-login \
  -H "Content-Type: application/json" \
  -d '{"code": "test_wechat_code_123456"}'

# 期望返回 access_token + user 信息（自动创建新用户）
```

---

## ⚙️ 配置说明

所有配置在 `.env`（从 `.env.example` 复制）：

- `APP_ENV`: development / staging / production
- `DATABASE_URL`: PostgreSQL 连接串
- `REDIS_URL`: Redis 连接串
- `JWT_SECRET`: JWT 密钥（**生产必须改**）
- `PHONE_ENCRYPTION_KEY`: 手机号加密密钥（base64 编码的 32 字节）
- `SMS_PROVIDER`: aliyun / mock（开发用 mock）
- `WECHAT_APP_ID` / `WECHAT_APP_SECRET`: 正式资质
- `WECHAT_TEST_APP_ID` / `WECHAT_TEST_APP_SECRET`: 微信测试号（开发用）

> 参考 [D-021](../docs/00-decisions.md#d-021) —— 资质不到位时用"开发模式"验证。

---

## 🛠 常用命令

```bash
# 启动开发服务器
uvicorn app.main:app --reload

# 数据库迁移
alembic upgrade head           # 应用所有迁移
alembic revision -m "msg"      # 生成新迁移
alembic downgrade -1           # 回滚一次

# 启动 RQ Worker
rq worker --url redis://localhost:6379/0

# 启动调度器（每日信用分重算等）
rq scheduler

# 测试
pytest                        # 跑全部测试
pytest -v --tb=short          # 详细输出
pytest --cov=app              # 覆盖率
pytest tests/test_health.py   # 跑单个文件

# 代码质量
ruff check app/               # lint
ruff format app/              # format
mypy app/                     # type check
```

---

## 📋 业务规则速查

| 规则 | 值 | 决策 |
| --- | --- | --- |
| 邀请超时 | 24h | [D-001](../docs/00-decisions.md) |
| 方案超时 | 2h | [D-001](../docs/00-decisions.md) |
| 信用分范围 | 6-100 | [D-002](../docs/00-decisions.md) |
| 评价可见性 | 双方实名，第三方脱敏 | [D-004](../docs/00-decisions.md) |
| LLM 月预算 | Soft ¥2000 / Hard ¥5000 | [D-008](../docs/00-decisions.md) |
| 登录方式 | **微信为主**，Apple 必选（iOS），短信兜底 | [D-013](../docs/00-decisions.md) |
| 强制更新 | 软提示 + 硬阻断 | [D-016](../docs/00-decisions.md) |

---

## 🚧 下一步

- [ ] 跑通 PG + Redis + RQ 完整环境
- [ ] 完成 9 张剩余表的 ORM + 迁移
- [ ] 实现房源/需求 CRUD
- [ ] 实现邀请状态机 + Top 5 推荐算法
- [ ] 实现方案提交 + 握手
- [ ] 实现评价 + 信用分计算
- [ ] 接入 LLM（DeepSeek-V3）
- [ ] 接入推送（firebase-admin）
- [ ] 接入对象存储（oss2）
- [ ] 单元测试覆盖到核心业务

---

## 📞 问题排查

| 问题 | 解决 |
| --- | --- |
| 启动报 `ModuleNotFoundError: No module named 'app'` | 确认在 `backend/` 目录运行，且用了 `uvicorn app.main:app` |
| `psycopg2` 安装失败 | 用 `psycopg2-binary`（已配），或 `pip install psycopg2-binary` |
| Redis 连接失败 | 启动 Redis：`docker compose up -d redis` 或 `brew install redis && redis-server` |
| PG 连接失败 | 启动 PG：`docker compose up -d postgres` |
| 短信发送 500 | 确认 `SMS_PROVIDER=mock` 或配置阿里云密钥 |
| `alembic` 找不到 | 在 backend 目录运行 `alembic upgrade head` |

---

**v0.4 状态**：后端骨架已就绪，核心 8 个接口已实现（短信+微信+Apple 登录 + 验证码 + 刷新 + 健康检查）。下一步：补完 9 张剩余表 + 业务核心流程。
