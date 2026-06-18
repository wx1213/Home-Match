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

---

## iOS 推送配置（C4 引入）

> 配套 commit：`feat(push): APP iOS 集成`
> 涉及文件：[`ios/Runner/Info.plist`](../mobile-app/ios/Runner/Info.plist) / [`ios/Runner/AppDelegate.swift`](../mobile-app/ios/Runner/AppDelegate.swift) / [`ios/Runner/Runner.entitlements`](../mobile-app/ios/Runner/Runner.entitlements) / [`ios/Runner/GoogleService-Info.plist`](../mobile-app/ios/Runner/GoogleService-Info.plist)

### 必需的手动步骤（dev 同学首次配 iOS 推送时执行一次）

#### 1. 替换 GoogleService-Info.plist

当前文件是**占位**（让 build 通过；Firebase init 在 runtime 会失败 → app 自动 fallback 到本地通知）。

替换为真实凭证：

1. 打开 [Firebase Console](https://console.firebase.google.com/) → 项目 homematch（或对应 dev/staging/prod）
2. Project Settings → Your apps → iOS app
3. 确认 Bundle ID 是 `cn.hmatch.app`
4. 下载 `GoogleService-Info.plist`
5. 覆盖 [`ios/Runner/GoogleService-Info.plist`](../mobile-app/ios/Runner/GoogleService-Info.plist)
6. 删除 Pods 重新装：`cd ios && rm -rf Pods Podfile.lock && pod install`

#### 2. 关联 Runner.entitlements（Xcode 必做）

1. 用 Xcode 打开 `ios/Runner.xcworkspace`
2. 左侧 Runner target → "Build Settings" → 搜索 "Code Signing Entitlements"
3. 填入：`Runner/Runner.entitlements`
4. 确认后重新 build

> 不做这步也能 build 成功，但 APNs 推送会静默失败（无 entitlement）。

#### 3. Apple Developer 后台配置

1. Apple Developer → Certificates, Identifiers & Profiles
2. App IDs → `cn.hmatch.app` → 勾上 **Push Notifications** capability
3. 创建 APNs Auth Key（.p8） → 上传到 Firebase Console → Project Settings → Cloud Messaging → APNs Authentication Key
4. 同样 .p8 文件存到 `backend/secrets/apns_key.p8`（与 `APNS_KEY_PATH` env 对应）

### dev 模式（无 Firebase 凭证）

不做上面 1~3 步时，APP 行为：
- 启动 → `Firebase.initializeApp()` 失败 → 静默 catch
- `FirebaseMessaging.getToken()` 抛异常 → 不注册 device
- 推送**完全跳过**，APP 仍能正常运行（业务接口不依赖推送）
- 后端 log 不会有 "device registered"

### 验证

启动 backend + flutter run 后：
- 登录 dev_alice → 模拟器设置 → 看是否弹出通知权限弹窗（场景化触发：进入合作/邀请页时）
- 在 Firebase Console → Cloud Messaging → 创建通知 → 选 iOS app → 发
- 模拟器通知中心收到 + 通知横幅
- 后端 log: `POST /v1/devices/register` 200

