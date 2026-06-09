# HomeMatch

> **北京二手房独立经纪人撮合评价平台**（代号：HomeMatch）
> 基于 AI Agent 的独立经纪人房客源撮合平台

[![Status](https://img.shields.io/badge/status-MVP-yellow)]() [![Flutter](https://img.shields.io/badge/Flutter-3.x-blue)]() [![FastAPI](https://img.shields.io/badge/FastAPI-latest-green)]()

---

## 项目简介

- **用户群体**：仅独立二手房经纪人，无经纪公司
- **角色**：每个经纪人可同时作为买方和卖方经纪人
- **核心闭环**：智能匹配 → 顺序邀约 → 方案握手 → 双向评价
- **MVP 范围**：不涉及交易、不分账、不绑定独家
- **差异化**：贝壳找房链接作为信息增强输入，AI 自动解析+预填
- **平台**：iOS + Android APP（Flutter 跨端），详见 [docs/01-requirements.md](./docs/01-requirements.md)

## 核心理念

对标贝壳 ACN 的信息联卖效率，但不强制分边分佣；用 AI Agent 赋能单兵作战的独立经纪人。

---

## 技术栈

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
- **网络层**：**dio + retrofit**，自定义拦截器链
- **本地存储**：**Hive**
- **推送**：**firebase_messaging**（APNs + FCM 统一封装）
- **认证**：**微信登录为主** + Apple 登录 + 短信兜底 + JWT

### AI 服务
- **主力模型**：DeepSeek-V3（性价比）
- **兜底模型**：Claude / GPT-4o（评价异常检测、复杂语义任务）

---

## 目录结构

```
RD/
├── CLAUDE.md                    ← 项目 AI 助手说明
├── README.md                    ← 本文件
├── docs/                        ← 设计文档
│   ├── 00-decisions.md          ← 20 条决策记录（ADR）
│   ├── 01-requirements.md       ← 需求总文档 v0.3
│   ├── 02-architecture.md       ← 架构设计 v0.1
│   ├── 03-api-spec.md           ← API 规范 v0.1
│   └── 04-ui-ux-guidelines.md   ← UI/UX 设计规范 v0.1
├── schemas/                     ← 数据库 schema、迁移
├── scripts/                     ← 启动脚本（后端/Flutter/调度器）
│   ├── start_backend.sh
│   ├── start_flutter.sh
│   ├── start_credit_cron.sh
│   └── stop_all.sh
├── backend/                     ← 后端代码（FastAPI）
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                ← 配置、日志、依赖、加密
│   │   ├── domains/             ← 业务域（auth, users, properties, ...）
│   │   ├── models/              ← SQLAlchemy models
│   │   ├── schemas/             ← Pydantic v2 schemas
│   │   ├── agents/              ← AI Agent 封装
│   │   └── workers/             ← RQ 任务
│   ├── scripts/                 ← CLI 脚本（含 credit_score_scheduler）
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── docker-compose.yml
└── mobile-app/                  ← Flutter APP（v0.3+）
    ├── lib/
    │   ├── main.dart
    │   ├── core/                ← theme, network, storage, push, image
    │   ├── features/            ← auth, home, demand, property, ...
    │   ├── router/              ← go_router 配置
    │   └── l10n/                ← 国际化（预留）
    ├── assets/
    ├── ios/
    ├── android/
    └── pubspec.yaml
```

---

## 快速开始

### 1. 启动后端
```bash
./scripts/start_backend.sh
```
> 启动 uvicorn，监听 `http://localhost:8000`

### 2. 启动 Flutter APP
```bash
./scripts/start_flutter.sh
```
> 编译并部署到 iPhone 17 Pro Simulator

### 3. 启动信用分调度器（每日 0 点重算）
```bash
./scripts/start_credit_cron.sh
```

### 停止所有
```bash
./scripts/stop_all.sh
```

### 一次性启动全部
```bash
./scripts/stop_all.sh && \
./scripts/start_backend.sh && \
./scripts/start_credit_cron.sh && \
./scripts/start_flutter.sh
```

---

## 业务规则摘要

1. **需求匹配**：需求发布后，系统推荐 **Top 5** 卖方经纪人
2. **顺序邀约（非竞合）**：买方从列表中选 1 人发起邀请；卖方 24h 内未响应自动失效
3. **方案握手**：卖方接受后 2h 内提交合作方案；买方确认后双方电子签名
4. **评价必填**：合作结束双方必须互评（1-5 星 + 文字 + 标签）
5. **信用分公式**：`信用分 = 评价均分 × 20 × 活跃系数`，范围 6-100
6. **淘汰规则**：虚假房源 → 一票冻结；15 天无维护 → 房源下架
7. **数据完整性**：所有操作带时间戳，软删除，**审计日志 append-only 不可篡改**
8. **脱敏规则**：向对方展示需求/房源时**隐藏真实姓名和联系方式**，直到握手成功

详细规则见 [docs/01-requirements.md](./docs/01-requirements.md)。

---

## 当前阶段

**MVP** — 仅实现核心流程：
- 房源录入 / 需求发布
- 智能匹配 Top 5
- 顺序邀约 + 方案握手
- 双向评价 + 信用分计算

**不做**：支付、分账、IM 通讯、跨城、经纪公司账号、视频带看、自动纠纷调解。

---

## 开发规范

详见 [CLAUDE.md](./CLAUDE.md)：
- 后端：RESTful + Pydantic v2 + Alembic 迁移 + RQ 异步任务
- APP：Riverpod 状态管理 + go_router 路由 + dio 拦截器链
- 测试：pytest（后端 ≥ 60% 覆盖率）+ flutter_test（关键流程）

---

## 文档

| 文档 | 说明 |
|---|---|
| [docs/00-decisions.md](./docs/00-decisions.md) | 20 条 ADR 决策记录 |
| [docs/01-requirements.md](./docs/01-requirements.md) | 需求总文档 |
| [docs/02-architecture.md](./docs/02-architecture.md) | 架构设计 |
| [docs/03-api-spec.md](./docs/03-api-spec.md) | API 规范 |
| [docs/04-ui-ux-guidelines.md](./docs/04-ui-ux-guidelines.md) | UI/UX 规范 |
| [CLAUDE.md](./CLAUDE.md) | AI 编程助手说明 |

---

## License

MIT
