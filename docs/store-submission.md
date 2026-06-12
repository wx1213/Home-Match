# HomeMatch 商店提审材料（[Sprint3-#14]）

> 本文档是提审 App Store + Google Play 需要的全部材料和填表说明。
> ops / product 同学提审前对照清单逐项准备。

## 1. 必备材料清单

### 1.1 通用

- [ ] **隐私政策 URL**（要求 https）—— `https://homematch.com/privacy`
- [ ] **用户协议 / 服务条款 URL** —— `https://homematch.com/terms`
- [ ] **公司名称**（中文 + 英文）
- [ ] **公司 D-U-N-S Number**（Apple 开发者账号需要）
- [ ] **客服邮箱**（`support@homematch.com`）
- [ ] **客服电话**（**必填** Apple 商店；非中国要 +86）
- [ ] **版权声明**（© 2026 HomeMatch Inc.）

### 1.2 iOS App Store

- [ ] **App 图标**（1024×1024 PNG，无 alpha）
- [ ] **iPhone 6.7"** 截图 × 3-10 张（1290×2796）
- [ ] **iPhone 6.5"** 截图 × 3-10 张（1242×2688，可选）
- [ ] **iPhone 5.5"** 截图 × 3-10 张（1242×2208，可选）
- [ ] **iPad 12.9"** 截图（2048×2732，如果支持 iPad）
- [ ] **App 预览视频**（30s，1080p，可选但强烈推荐）
- [ ] **App 名称**（≤ 30 字符）—— "HomeMatch 房客源"
- [ ] **副标题**（≤ 30 字符）—— "独立经纪人撮合平台"
- [ ] **关键词**（≤ 100 字符，逗号分隔）——
  ```
  二手房,经纪人,撮合,合作,北京,房产,信用,评价
  ```
- [ ] **类别**：主 "商务" / 副 "生活"
- [ ] **年龄分级**：4+
- [ ] **价格**：免费
- [ ] **版权**：`© 2026 HomeMatch Inc.`
- [ ] **登录信息**（tester 账号 + 密码，Apple 审核用）——
  - 后端 staging 环境的 dev user
  - 见 `docs/05-dev-users.md`
- [ ] **出口合规信息**（Encryption: No）

### 1.3 Google Play

- [ ] **App 图标**（512×512 PNG）
- [ ] **Feature Graphic**（1024×500 JPG/PNG，商店首图）
- [ ] **手机截图** × 2-8 张（每张 ≥ 320px，推荐 1080×1920）
- [ ] **App 名称**（≤ 50 字符）—— "HomeMatch 房客源"
- [ ] **简短描述**（≤ 80 字符）——
  ```
  独立二手房经纪人专属撮合平台：智能匹配 Top 5、顺序邀约、方案握手、双向评价。
  ```
- [ ] **完整描述**（≤ 4000 字符）—— 见 [section 5](#5-app-描述文案)
- [ ] **类别**：商务
- [ ] **标签**：房产、商务
- [ ] **Data Safety 表单**（见 [section 4](#4-data-safety-表单-google-play))
- [ ] **Content Rating**：所有人
- [ ] **Target API Level**：≥ 34（Android 14）
- [ ] **隐私政策 URL**

---

## 2. 截图需求

每个截图必须是真实业务页面的渲染图（不是设计稿）。

**建议 5 张**：
1. 首页 / 房源列表（首屏）
2. 需求详情页 + 推荐 Top 5
3. 邀请 / 合作页面
4. 信用分 / 评价页面
5. 个人中心 / 房源管理

> 渲染方式：在 iPhone 17 Pro 模拟器上 `flutter run`，
> 用 `Cmd+S` 截屏；或用 [fastlane snapshot](https://docs.fastlane.tools/getting-started/cross-platform/tips/).

---

## 3. iOS Privacy Manifest

已配置：[mobile-app/ios/Runner/PrivacyInfo.xcprivacy](../mobile-app/ios/Runner/PrivacyInfo.xcprivacy)

**Xcode 添加步骤**：
1. Xcode → Runner target → **Build Phases** → **Copy Bundle Resources**
2. 点 `+` → Add `ios/Runner/PrivacyInfo.xcprivacy`
3. 确保 Target Membership 勾上 Runner

**已声明的 API 类别**：
| API | 原因 |
|---|---|
| UserDefaults | CA92.1 自己写入 |
| File timestamp | C617.1 显示给用户 |
| Disk space | E174.1 APP 功能所需 |
| System boot time | 35F9.1 Sentry crash 报告 |

**收集的数据**：
- 手机号（关联用户，目的：APP 功能）
- 用户 ID（同上）
- 图片/视频（同上）

**未跟踪**（NSPrivacyTracking = false）。

---

## 4. Data Safety 表单（Google Play）

在 Google Play Console → App content → Data safety 填写：

### 4.1 Data shared with third parties

| 数据类型 | 第三方 | 共享场景 | 用户可控制 |
|---|---|---|---|
| 无 | — | — | — |

（我们不向任何第三方共享用户数据。微信/Apple 登录由 OAuth 协议，但不在 APP 端缓存）

### 4.2 Data collected by this app

| 数据类型 | 收集 | 必需？ | 目的 |
|---|---|---|---|
| **Phone number** | ✓ | ✓ 必需 | App functionality（登录） |
| **User IDs** | ✓ | ✓ 必需 | App functionality（认证 + 信用分） |
| **Photos and videos** | ✓ | ✓ 必需 | App functionality（房源图） |
| **App activity** (login / match results) | ✓ | ✓ 必需 | App functionality（撮合推荐） |
| **App info and performance** (crash logs) | ✓ | ✓ 必需 | App functionality（稳定性） |
| **Location** (from photo EXIF) | ✗ | — | 服务端 [Sprint3-#13] 已强制清理 EXIF，**不收集** |

### 4.3 Security practices

- [x] Data is encrypted in transit（HTTPS）
- [x] Users can request data deletion（[隐私政策 URL] 中提供联系方式）
- [x] App has been independently reviewed（公司内部安全审计）

---

## 5. App 描述文案

### 5.1 中文长描述（Google Play / App Store 都用）

```
HomeMatch 是专为北京独立二手房经纪人打造的撮合评价平台。
我们相信专业经纪人值得更好的合作工具。

【核心功能】
• 智能匹配：需求发布后，系统推荐 Top 5 卖方经纪人
  （多维度：区域 / 价格 / 户型 / 看房时间 / 信用 / 活跃度）
• 顺序邀约：从 Top 5 中选 1 人发起邀请，避免抢单恶性竞争
  24h 内未响应自动失效，本轮淘汰
• 方案握手：卖方 2h 内提交合作方案，买方确认后双方电子签名，握手成功
• 双向评价：合作结束双方必须互评（1-5 星 + 文字），形成信用闭环
• 信用分：评价均分 × 活跃系数 = 信用分（6-100 分），信用越好曝光越高

【差异化】
• 贝壳链接增强：粘贴贝壳找房链接，AI 自动解析房源信息预填
• 隐私保护：真实姓名和联系方式对未握手的对方隐藏
• 无中间商：仅独立经纪人，无经纪公司账号
• 独立 IM：暂不内置聊天（用微信/电话），避免消息碎片化

【适用对象】
• 北京独立二手房经纪人
• 同时是买方和卖方经纪人
• 想找靠谱同行合作的从业者

【数据安全】
• 手机号 AES-256-GCM 加密存储
• 身份证不收集（合规优先）
• HTTPS only（生产强制）
• APP 端 JWT 存 Secure Storage（iOS Keychain / Android Keystore）

【技术架构】
• 后端：FastAPI + PostgreSQL + Redis
• 移动端：iOS / Android（Flutter 跨端）
• AI：DeepSeek 主力 + 兜底规则
• 部署：阿里云
```

### 5.2 英文短描述（Apple 副标题用）

```
Independent real estate agents matching & review platform for Beijing
```

---

## 6. 提审流程时间线

| 阶段 | 步骤 | 估时 |
|---|---|---|
| **D-7** | 准备截图 + 隐私政策 URL 上线 | 半天 |
| **D-6** | Apple 开发者账号 D-U-N-S 验证（首次） | 2-3 周 |
| **D-3** | TestFlight 内部测试（≤ 100 台设备） | 1 天 |
| **D-1** | 提交 App Store Review | 1 天 |
| **D-Day** | Apple 审核（首次 24-48h，加急后 24h 内） | 1-2 天 |
| **D+1** | Google Play 内部测试（封闭轨道） | 1 天 |
| **D+3** | Google Play 公开测试（开放轨道） | 1-2 周 |
| **D+14** | Google Play 正式上架 | 1 天 |

**关键路径**：D-U-N-S 验证（2-3 周）→ 截图 + 隐私政策上线 → TestFlight → 正式审核。

---

## 7. 商店上架后监控

- [ ] 评分 / 评论监控（提审后每天看）
- [ ] Crashlytics / Sentry dashboard 每天看
- [ ] 用户反馈邮件 24h 内回复
- [ ] 隐私政策修改后**必须**在 14 天内同步到 APP 内
