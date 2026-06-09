# HomeMatch APP

> 北京二手房独立经纪人撮合评价平台 - 移动 APP
> Flutter 3 + Dart 3 / iOS + Android

---

## 🏃 5 分钟跑起来

### 前提条件

- macOS（已装 Xcode）
- 后端服务已启动（参考 [../backend/README.md](../backend/README.md)）
- 一个 iOS 模拟器 或 Android 模拟器

### 启动步骤

```bash
cd /Users/wangxiao/WorkSpace/RD/mobile-app

# 1. 装依赖
flutter pub get

# 2. 看可用的模拟器
flutter devices

# 3. 启动一个 iOS 模拟器（如果还没开）
open -a Simulator

# 4. 跑 APP
flutter run

# 或者指定设备
flutter run -d "iPhone 15"
```

APP 启动后会自动连本机后端 `http://localhost:8000`。

---

## 📂 项目结构

```
mobile-app/
├── lib/
│   ├── main.dart                  # 入口
│   ├── app.dart                   # 根 Widget（MaterialApp.router）
│   │
│   ├── core/                      # 基础设施
│   │   ├── theme/                 # Material 3 主题
│   │   ├── network/               # dio + 拦截器
│   │   ├── router/                # go_router 路由表
│   │   └── widgets/               # 通用组件（空状态、信用分徽章等）
│   │
│   ├── features/                  # 按业务功能分模块
│   │   ├── auth/                  # 登录（微信/短信）
│   │   ├── home/                  # 主页 Tab 容器
│   │   ├── demand/                # 需求 CRUD + 推荐
│   │   ├── property/              # 房源 CRUD
│   │   ├── invitation/            # 邀请列表 + 详情 + 接单
│   │   ├── cooperation/           # 合作看板 + 详情
│   │   ├── review/                # 评价
│   │   └── profile/               # 个人中心
│   │
│   └── l10n/                      # 国际化（预留）
│
├── ios/                           # iOS 原生工程（flutter create 生成）
├── android/                       # Android 原生工程
├── assets/                         # 图片、字体
├── pubspec.yaml                    # 依赖
└── README.md
```

---

## 🔌 后端联调

### API Base URL

```dart
// lib/core/network/dio_client.dart
const String kApiBaseUrl = 'http://localhost:8000';
```

iOS 模拟器/Android 模拟器访问 Mac 宿主都用 `localhost`。

### 后端需要启动

```bash
# 在另一个终端
cd /Users/wangxiao/WorkSpace/RD/backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### APP 端打通后的登录流程

1. APP 启动 → 跳到登录页
2. 点击"微信登录（开发模式）" → APP 调 `/v1/auth/wechat-login` 拿 token
3. 存 token 到 Secure Storage + 全局状态
4. 跳到主页（4 个 Tab：需求/房源/合作/我的）

### 6 个核心页面

| 页面 | 路径 | 接口 |
| --- | --- | --- |
| 登录 | `/login` | `POST /v1/auth/wechat-login` |
| 我的需求 | `/demands` | `GET /v1/demands` |
| 发布需求 | `/demands/new` | `POST /v1/demands` |
| AI 推荐 | `/demands/:id/recommendations` | `GET /v1/demands/:id/recommendations` |
| 我的房源 | `/properties` | `GET /v1/properties` |
| 发布房源 | `/properties/new` | `POST /v1/properties` |
| 邀请列表 | `/invitations` | `GET /v1/invitations` |
| 邀请详情 | `/invitations/:id` | `GET/POST /v1/invitations/:id/{accept,reject}` |
| 合作看板 | `/cooperations` | （二期：列表） |
| 合作详情 | `/cooperations/:id` | `GET /v1/cooperations/:id` |
| 评价 | `/cooperations/:id/review` | `POST /v1/cooperations/:id/review` |
| 个人中心 | `/profile` | `GET /v1/auth/me`（待接） |

---

## 🎨 设计规范

参考 [../docs/04-ui-ux-guidelines.md](../docs/04-ui-ux-guidelines.md)：

- **Material 3** 主题（自动暗色模式）
- 颜色：主品牌色 `#1976D2`（亮）/ `#90CAF9`（暗）
- 字体：系统默认（iOS SF / Android Roboto）
- 圆角：12dp 统一
- 触摸目标：≥ 48dp
- 信用分徽章：5 档颜色（红/橙/蓝/绿/金）

---

## 🧪 验证清单

启动后用 iOS 模拟器走一遍：

- [ ] **登录页** - 点"微信登录"看到 Loading → 跳主页
- [ ] **Tab 1: 需求** - 空状态 → 点 FAB → 表单 → 提交 → 看到新需求
- [ ] **需求卡片** - 点击 → 进推荐页
- [ ] **推荐页** - 看到 Top 5 卖方卡片（信用分徽章 + 匹配度）
- [ ] **邀请按钮** - 点"邀请合作" → 弹 SnackBar → 跳到邀请页
- [ ] **Tab 2: 房源** - 发布一个房源 → 看到列表
- [ ] **Tab 3: 合作** - 空状态（邀请被接后会显示合作）
- [ ] **Tab 4: 我的** - 看到头像 + 信用分 + 登出

---

## 🔧 已知限制（MVP 阶段）

- ❌ **不接真微信 SDK** - 用 mock wechat-login 模拟
- ❌ **不接真推送** - 推送架构在后端准备好了，APP 端没接 firebase_messaging
- ❌ **不接真相机/相册** - 实勘图上传在二期
- ❌ **不接 LLM 实时推荐解释** - 推荐理由是规则打分，不是 LLM
- ❌ **不做深链/Universal Link** - 二期加
- ❌ **不做引导页/新手教学** - 简洁优先

---

## 🐛 常见问题

| 问题 | 解决 |
| --- | --- |
| 启动报 `dart sdk 版本不匹配` | `flutter upgrade` 然后 `flutter pub get` |
| 模拟器连不上 `localhost` | iOS 模拟器正常应该可以；Android 用 `10.0.2.2` 替代 |
| 报 `NoSuchMethodError` | `flutter clean && flutter pub get` |
| 推送集成问题 | 二期再接 firebase_messaging |

---

## 📋 下一步

- [ ] 接入 firebase_messaging 实现真推送
- [ ] 接入微信开放平台 SDK 替换 mock
- [ ] 接入相机/相册 实现实勘图上传
- [ ] 接入 LLM 实时推荐解释（点击推荐卡 → 调 /v1/ai/explain-recommendation）
- [ ] 加 Universal Link / Deep Link
- [ ] 加引导页 + 隐私协议弹窗
- [ ] 加多语言（en-US）
- [ ] 加暗色主题精调

---

**版本**：v0.4 MVP 验证版
**与后端**：配套 [../backend/](../backend/) v0.4
**设计参考**：[../docs/04-ui-ux-guidelines.md](../docs/04-ui-ux-guidelines.md)
