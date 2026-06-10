# CI Pipeline（P2-4 引入）

> 本文档说明 HomeMatch 的 GitHub Actions 持续集成配置。
> 配套文件：[`.github/workflows/backend-ci.yml`](../.github/workflows/backend-ci.yml) 和 [`.github/workflows/flutter-ci.yml`](../.github/workflows/flutter-ci.yml)

---

## 触发条件

| Workflow | 触发 | 路径过滤 |
|---|---|---|
| **Backend CI** | main push / PR / 手动 dispatch | `backend/**` + `.github/workflows/backend-ci.yml` |
| **Flutter CI** | main push / PR / 手动 dispatch | `mobile-app/**` + `.github/workflows/flutter-ci.yml` |

两个 workflow 互不依赖，并行运行。

## Backend CI 步骤

```yaml
1. checkout (actions/checkout@v4)
2. Setup Python 3.11 (actions/setup-python@v5) + cache pip
3. Install uv (pip install uv)
4. uv venv + uv pip install -e ".[dev]"  # 装 ruff/mypy/pytest/pytest-asyncio/pytest-cov
5. ruff check .                          # lint
6. mypy app/ (non-blocking)              # type check（MVP 阶段不 fail CI）
7. pytest --cov-fail-under=60            # 单测 + 60% 覆盖率门控
```

测试环境：
- `DATABASE_URL=sqlite:///./_test_ci.db`（文件式 SQLite，跨 connection 共享 schema）
- `REDIS_URL=redis://localhost:6379/0`（CI 不启 Redis，sms-code 测试用 in-memory mock 替身）
- `SMS_PROVIDER=mock`（验证码本地生成）

## Flutter CI 步骤

```yaml
1. checkout
2. Setup Flutter 3.44.1 (subosito/flutter-action@v2) + 缓存
3. flutter pub get
4. flutter analyze --no-fatal-infos
5. flutter test
```

## 60% 覆盖率门控

backend pytest 加 `--cov-fail-under=60`，当前实测 **66%**：
- 44 个测试通过
- 2281 行代码 / 678 行未覆盖
- 低覆盖模块（push/service 0%、workers/credit_score 0%）依赖外部服务，MVP 阶段豁免
- 新代码必须保持或提升覆盖率，否则 PR fail

## 本地复现 CI

```bash
# 后端
cd backend
source .venv/bin/activate
ruff check .
pytest tests/ --cov=app --cov-branch --cov-fail-under=60

# Flutter
cd mobile-app
export PATH="/opt/homebrew/flutter/bin:$PATH"
flutter analyze --no-fatal-infos
flutter test
```

## CI 状态

- 仓库：https://github.com/wx1213/Home-Match/actions
- 最新运行：在 push 到 main 后自动触发
- 失败时：PR 不能 merge，main 会被自动 commit 状态回滚

## 未来扩展

- [ ] 加 codecov.io 上传覆盖率徽章
- [ ] 加 release workflow（自动打包 APK/IPA）
- [ ] 加 e2e workflow（连接真实 PG/Redis 跑 e2e_test_v2.py）
- [ ] 加 PR 自动评论（@mention 测试覆盖率变化）
- [ ] 加 scheduled workflow（每天 0 点跑 e2e 兜底）
