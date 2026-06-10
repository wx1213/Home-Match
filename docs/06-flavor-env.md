# Flutter Flavor / Env 配置（P2-1/2/3）

> 本文档说明 HomeMatch APP 的编译时环境变量配置方案。
> 配套代码：[`mobile-app/lib/core/env/app_env.dart`](../mobile-app/lib/core/env/app_env.dart)

---

## 方案概览

所有环境配置通过 `--dart-define=KEY=VALUE` 在编译时注入，**无 `.env` 文件依赖**。
配置集中在 `AppEnv` 单例，编译时为常量（`String.fromEnvironment` / `bool.fromEnvironment`）。

## 配置项

| Key | 类型 | 默认 | 说明 |
|---|---|---|---|
| `API_BASE_URL` | String | `http://localhost:8000` | 后端 base URL（dev 默认本地） |
| `ENV_NAME` | String | `development` | 环境名（development/staging/production） |
| `PRODUCTION` | bool | `false` | 是否生产环境（影响埋点/监控分流） |
| `ENABLE_DEV_LOGIN` | bool | `true` | 是否启用 dev 自动登录 + 🐛 切换器 |
| `VERBOSE_DEV_LOG` | bool | `false` | 启动横幅等 dev 日志 |

## 用法

### 本地开发（默认）

```bash
flutter run -d <device>
```

默认：`apiBaseUrl=http://localhost:8000`，dev login 启用。

### 指向测试/staging 环境

```bash
flutter run -d <device> \
  --dart-define=API_BASE_URL=https://test-api.homematch.com \
  --dart-define=ENV_NAME=staging \
  --dart-define=ENABLE_DEV_LOGIN=true
```

### 生产构建（关闭 dev 入口）

```bash
flutter build apk --release \
  --dart-define=API_BASE_URL=https://api.homematch.com \
  --dart-define=ENV_NAME=production \
  --dart-define=PRODUCTION=true \
  --dart-define=ENABLE_DEV_LOGIN=false
```

iOS 同理：
```bash
flutter build ios --release \
  --dart-define=API_BASE_URL=https://api.homematch.com \
  --dart-define=PRODUCTION=true \
  --dart-define=ENABLE_DEV_LOGIN=false
```

## P2-3 守卫行为

| 入口 | `enableDevLogin=true`（dev） | `enableDevLogin=false`（生产） |
|---|---|---|
| 启动时 `main()` 自动登录 | ✅ 调 `_doLogin` 走 mock wechat 登录 | ❌ 跳过，进登录页等用户真实登录 |
| `switchDevUser()` | ✅ 切换 dev 身份 | ❌ no-op（debug 模式打日志） |
| 个人中心 🐛 切换器按钮 | ✅ 显示 | ❌ 隐藏 |

## 安全注意

- 不要把敏感信息（API secret、JWT signing key 等）放 `AppEnv` — 会被打包进二进制
- 生产构建务必传 `PRODUCTION=true` + `ENABLE_DEV_LOGIN=false`，否则用户能切到 dev 身份看其他人的数据
- CI/CD 必须强制注入 `API_BASE_URL`（避免漏配置导致 dev base URL 被打到生产）

## 测试

`mobile-app/test/app_env_test.dart` 验证默认行为：
- 默认 `apiBaseUrl = 'http://localhost:8000'`
- 默认 `enableDevLogin = true`
- `summary` 包含 `[DEV]` 标记

## 历史

- **2026-06-10 P2-1/2/3**：引入 `AppEnv` 单例 + `--dart-define` 注入 + dev 守卫
- 之前：硬编码 `kApiBaseUrl = 'http://localhost:8000'`，dev 切换器永远显示（生产风险）
