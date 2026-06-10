# 测试与覆盖率（P1/P2 累计）

> 本文档汇总 HomeMatch 的测试策略、覆盖率和持续保障机制。
> 配套：[CI 流水线](./07-ci-pipeline.md) | [dev 用户管理](./05-dev-users.md)

---

## 测试总览

| 范围 | 框架 | 测试数 | 覆盖率 |
|---|---|---|---|
| 后端单元 + 集成 | pytest + pytest-asyncio | 44 | **66%** |
| 前端 widget + 数据 | flutter_test | 6 | N/A（widget 测，无需 coverage gate） |
| E2E（脚本） | httpx | scripts/e2e_test_v2.py | N/A（需真实 PG/Redis） |

## 后端测试矩阵

### 1. 基础设施（5 tests）
- `test_health.py`：根路径、Swagger UI、OpenAPI schema、健康检查、sms-code 验证
- **P1-1 修复**：sms-code 走 `dependency_overrides` 注入 in-memory 替身，不依赖 Redis

### 2. 越权矩阵（16 tests）
- `test_authorization.py`：**P1-3** 核心
- 覆盖 11 个域（properties / demands / invitations / cooperations / proposals / reviews / users）
- 每个域验证：A 访问 B 资源 → 403，第三方 C → 403，无 token → 401
- 已知缺口：`GET /properties/{id}` 等 5 个 endpoint 无 auth check（待 P2-7+）

### 3. 状态机非法 transition（9 tests）
- `test_state_machine.py`：**P1-5** 核心
- 9 个场景：double accept、accept 后 reject、handshaked 后再 decline 等
- 全局 MachineError handler 兜底：monkeypatch sm.accept 抛 MachineError → 409

### 4. 推荐降级（4 tests）
- `test_recommendation_degradation.py`：**P1-4** 核心
- 4 个场景：safe_get 抛 ConnectionError、safe_setex 抛、缓存 JSON corrupt、正常路径
- mock `redis_client.get/setex` 抛异常，验证 matcher 降级到 DB 计算

### 5. 信用分公式（10 tests）
- `test_credit_score.py`：**P2-6** 核心（纯函数，最高 ROI）
- 覆盖：下限 6、满分 100、半满、活跃 cap、四舍五入、None 容错

## 前端测试矩阵

| 文件 | 测试 |
|---|---|
| `widget_test.dart`（P1-1 修复） | HomeMatchApp 编译 smoke + MaterialApp 渲染 |
| `dev_user_tile_test.dart`（P1-0） | DevIdentity fromJson + #userId 徽章渲染 |
| `app_env_test.dart`（P2-1） | 默认值 + summary 含 [DEV] 标记 |

## 覆盖率分布（66% 整体）

```
高覆盖（≥80%）：
  app/schemas/*          100%   Pydantic 模型
  app/models/*          90%+   SQLAlchemy ORM
  app/main.py            84%   FastAPI 入口
  app/agents/matcher.py  85%   匹配引擎
  app/domains/invitations/router.py  75%

中覆盖（50-80%）：
  app/domains/proposals/router.py   78%
  app/domains/properties/router.py  67%
  app/domains/demands/router.py     60%

低覆盖（<50%）：
  app/domains/users/router.py        38%  (dev-identities 等查询未覆盖)
  app/domains/reviews/router.py      38%  (review 提交未 e2e 覆盖)
  app/domains/reviews/credit_score.py 31% (DB 集成部分靠 e2e)

零覆盖（依赖外部服务）：
  app/domains/push/service.py         0%  (firebase-admin)
  app/workers/credit_score.py         0%  (RQ 后台任务)
```

## 持续保障

1. **CI 门控**：[`.github/workflows/backend-ci.yml`](../.github/workflows/backend-ci.yml) 加 `--cov-fail-under=60`
2. **本地复现**：`cd backend && pytest --cov=app --cov-fail-under=60 tests/`
3. **提交前自检**：`ruff check .` 必须 `All checks passed!`
4. **PR 流程**：CI 不通过 → 不能 merge

## 写新测试的最佳实践

1. **纯函数最高 ROI**（如 `compute_credit_score`）：无需 DB，无需 setup，10 个 case 1 分钟
2. **状态机非法转移**（如 `double_accept`）：setup 一个合法状态 + 触发非法动作
3. **越权**（如 `B 改 A`）：建 A/B/C + 用对应 token 调 API + 断言 403
4. **降级**（如 `Redis down`）：monkeypatch `redis_client.get` 抛 ConnectionError
5. **避免 boot 完整 APP**（widget 测试）：会触发 auto-login dio 调用，fake_async 下变未释放 Timer

## 未来扩展

- [ ] 后端 push/service 单测（mock firebase-admin）
- [ ] 后端 workers/credit_score 集成测试（mock RQ）
- [ ] 前端 integration_test（登录/发布需求/邀请接单关键流程）
- [ ] E2E 在 CI 跑（加 PG/Redis service 容器）
- [ ] Coverage 历史趋势（codecov.io 徽章）
