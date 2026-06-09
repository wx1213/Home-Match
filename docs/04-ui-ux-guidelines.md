# HomeMatch UI/UX 设计规范 v0.1

> 配套文档：[01-requirements.md](01-requirements.md) | [02-architecture.md](02-architecture.md)
> 文档版本：v0.1（初稿，待复核）
> 撰写日期：2026-06-04
> 适用：Flutter APP（iOS + Android），目标"主流房产 APP"体验

---

## 0. 设计原则（5 条铁律）

1. **移动优先**：所有交互按 375×812（iPhone 13 mini）设计基准
2. **即时反馈**：每个操作 < 100ms 必须有视觉反馈（按钮按下态、骨架屏、转圈）
3. **容错设计**：操作可撤销；危险操作需二次确认；网络错误友好提示
4. **一致体验**：跨页面同功能表现一致（按钮位置、颜色、文案）
5. **平台适配**：iOS 遵循 HIG，Android 遵循 Material Design 3，**但功能与信息架构保持一致**

---

## 1. 平台规范适配

### 1.1 iOS（Human Interface Guidelines）
- 顶部导航栏：标准 44pt
- 底部 Tab Bar：49pt + 安全区
- 字体：San Francisco（系统默认）
- 返回手势：左滑返回（系统默认）
- 圆角：8pt / 12pt
- 主色应用 iOS 系统色（推荐蓝/绿）

### 1.2 Android（Material Design 3）
- AppBar：标准 56dp
- 底部 NavigationBar：80dp
- 字体：Roboto（系统默认）
- 返回手势：系统返回键 / 手势
- 圆角：8dp / 12dp / 16dp
- 主色应用 Material You（动态取色）

### 1.3 Flutter 实现策略

```dart
// 在 MaterialApp 级别启用 Material 3
MaterialApp(
  theme: ThemeData(useMaterial3: true, ...),
  // 平台自适应组件（按需）
  // 如需纯 iOS 风格，可改用 CupertinoApp
)
```

**默认策略**：
- 用 Material 3 组件库（功能更全、生态更丰富）
- 关键页面（如启动页、卡片）做平台细节适配
- 同一 App 同一功能，外观**保持一致**，避免分裂感

---

## 2. 视觉系统

### 2.1 颜色（Material 3 调色板）

#### 主色（Primary）
| 用途 | Light | Dark | 对比度 |
| --- | --- | --- | --- |
| **Primary**（主品牌色） | `#1976D2` | `#90CAF9` | ✅ |
| **Primary Container** | `#BBDEFB` | `#0D47A1` | — |
| **On Primary** | `#FFFFFF` | `#000000` | ✅ |
| **Secondary**（强调色） | `#26A69A` | `#80CBC4` | ✅ |

#### 中性色
| 用途 | Light | Dark |
| --- | --- | --- |
| **Background** | `#FAFAFA` | `#121212` |
| **Surface** | `#FFFFFF` | `#1E1E1E` |
| **Surface Variant** | `#F5F5F5` | `#2C2C2C` |
| **On Surface** | `#1C1B1F` | `#E6E1E5` |
| **On Surface Variant** | `#49454F` | `#CAC4D0` |
| **Outline** | `#79747E` | `#938F99` |

#### 状态色
| 状态 | Light | Dark | 用途 |
| --- | --- | --- | --- |
| **Success** | `#2E7D32` | `#66BB6A` | 成功（邀请已接受、合作达成） |
| **Warning** | `#F57C00` | `#FFA726` | 警告（即将超时、房源待核实） |
| **Error** | `#C62828` | `#EF5350` | 错误（操作失败、信用过低） |
| **Info** | `#1976D2` | `#42A5F5` | 提示（系统通知、引导） |

#### 信用分颜色
| 分数 | 颜色 | 含义 |
| --- | --- | --- |
| 90+ | `#FFD700`（金） | 优质 |
| 75-89 | `#2E7D32`（绿） | 良好 |
| 60-74 | `#1976D2`（蓝） | 一般 |
| 40-59 | `#F57C00`（橙） | 偏低 |
| <40 | `#C62828`（红） | 风险 |

### 2.2 字体

| 用途 | 字号 | 字重 | 行高 | 用途示例 |
| --- | --- | --- | --- | --- |
| **Display Large** | 32 | w700 | 40 | 启动页 Slogan |
| **Display Medium** | 28 | w700 | 36 | 引导页标题 |
| **Headline Large** | 24 | w700 | 32 | 页面标题 |
| **Headline Medium** | 20 | w600 | 28 | 区块标题 |
| **Title Large** | 18 | w600 | 24 | 卡片标题 |
| **Title Medium** | 16 | w600 | 22 | 列表项标题 |
| **Body Large** | 16 | w400 | 24 | 正文 |
| **Body Medium** | 14 | w400 | 20 | 次要正文 |
| **Body Small** | 12 | w400 | 16 | 辅助文字 |
| **Label Large** | 14 | w600 | 20 | 按钮文字 |
| **Label Medium** | 12 | w600 | 16 | 标签、Tag |
| **Label Small** | 10 | w500 | 14 | 角标 |

**字体选择**：
- iOS：San Francisco（系统）
- Android：Roboto（系统）
- 中文回退：PingFang SC（iOS）/ 思源黑体（Android）
- 数字特殊处理：`tabular-figures` 数字等宽（信用分、价格）

### 2.3 间距系统（8pt 网格）

| 名称 | 数值 | 用途 |
| --- | --- | --- |
| `xxs` | 4 | 标签内边距、Tag 间距 |
| `xs` | 8 | 文字与图标间距、列表项内边距 |
| `sm` | 12 | 卡片内边距 |
| `md` | 16 | 区块内边距、卡片间距 |
| `lg` | 24 | 大区块间距 |
| `xl` | 32 | 页面顶部/底部留白 |
| `xxl` | 48 | 大标题与正文间距 |

### 2.4 圆角

| 名称 | 数值 | 用途 |
| --- | --- | --- |
| `none` | 0 | 全屏图、分割线 |
| `sm` | 8 | 按钮、Tag、输入框 |
| `md` | 12 | 卡片、弹窗 |
| `lg` | 16 | 大卡片、Banner |
| `xl` | 24 | 头像 |
| `full` | 9999 | 圆形头像、胶囊按钮 |

### 2.5 阴影（Z 轴层次）

```dart
// 三档阴影
ShadowLevel 1 (卡片):  blurRadius 8,  offset (0, 2),  color rgba(0,0,0,0.08)
ShadowLevel 2 (弹窗):  blurRadius 16, offset (0, 4),  color rgba(0,0,0,0.12)
ShadowLevel 3 (FAB):   blurRadius 24, offset (0, 8),  color rgba(0,0,0,0.16)
```

### 2.6 暗色模式

- **必须支持**系统级暗色模式（iOS: Dark Mode / Android: Dark Theme）
- 主品牌色在暗色下**降低饱和度**（避免刺眼）
- Surface 用 `#121212` 而非纯黑（OLED 省电 + 减少眼疲劳）
- 图片/插画需要暗色版本（用 `ColorFiltered` 降亮度）

```dart
// Theme 切换示例
themeMode: ThemeMode.system  // 跟随系统
// 或
themeMode: settings.isDarkMode ? ThemeMode.dark : ThemeMode.light
```

---

## 3. 组件库

### 3.1 基础组件

| 组件 | 说明 | 关键属性 |
| --- | --- | --- |
| **HMButton** | 主按钮 | variants: primary / secondary / tertiary / danger / ghost；size: sm / md / lg；loading 状态 |
| **HMTextField** | 输入框 | label / hint / error / counter；密码模式；验证码模式（6 位独立框） |
| **HMCard** | 卡片 | elevation (1-3)；clickable / not clickable |
| **HMAppBar** | 顶部导航 | title / leading / actions；支持渐变背景 |
| **HMTabBar** | 底部 Tab | 3-5 项；badge 角标 |
| **HMListTile** | 列表项 | leading / title / subtitle / trailing；支持箭头 |
| **HMEmptyState** | 空状态 | illustration / title / subtitle / action |
| **HMErrorState** | 错误状态 | icon / title / message / retry button |
| **HMSkeleton** | 骨架屏 | 矩形 / 圆角 / 文本行 |
| **HMToast** | 轻提示 | success / warning / error / info；自动消失 |
| **HMModal** | 弹窗 | title / content / actions；底部抽屉样式 |
| **HMBadge** | 角标 | dot / number / text |
| **HMTag** | 标签 | filled / outlined；可关闭 |
| **HMAvatar** | 头像 | image / initial；size: xs / sm / md / lg / xl |
| **HMNetworkImage** | 网络图 | 缓存、占位、错误图、渐显 |

### 3.2 业务组件

| 组件 | 说明 |
| --- | --- |
| **PropertyCard** | 房源卡片（图、价、关键信息、Tag） |
| **SellerCard** | 卖方卡片（脱敏头像、姓名、信用分、匹配度、房源） |
| **DemandSummaryCard** | 需求摘要卡（区域、价格、户型、可看时间） |
| **InvitationCard** | 邀请卡（角色、房源/需求摘要、倒计时、状态） |
| **ProposalCard** | 方案卡（内容预览、查看全文、确认/拒绝） |
| **CooperationTimeline** | 合作时间线（待响应→方案待审→已握手→合作中→待评价） |
| **CreditScoreBadge** | 信用分徽章（颜色 + 数字 + tooltip） |
| **CountdownText** | 倒计时文字（24h/2h 自动转红+震动） |

---

## 4. 导航模式

### 4.1 整体结构

```
SplashScreen
  └→ LoginScreen
        └→ MainScreen (Tab Bar)
              ├─ Tab 1: HomePage        （推荐/匹配）
              ├─ Tab 2: CooperationsPage（合作看板）
              └─ Tab 3: ProfilePage     （我的）
              
Push/Pop: 详情页（房源详情、邀请详情、合作详情、设置）
Modal:    拍照/选图、扫码、确认弹窗
```

### 4.2 Tab Bar 设计

- **3 个 Tab**（不是 5 个，简洁）
- 图标 + 文字（不带徽章时仅图标）
- 选中态：主色 + 粗体
- 未选中态：次要色 + 常规

| Tab | 图标 | 标签 |
| --- | --- | --- |
| 1 | `home` | 推荐 |
| 2 | `handshake` | 合作 |
| 3 | `person` | 我的 |

### 4.3 页面转场

| 场景 | 转场效果 |
| --- | --- |
| 进入详情 | iOS: 从右滑入；Android: Material 标准 |
| Modal 弹窗 | 从下滑入 + 背景模糊 |
| Tab 切换 | Fade |
| Push/Pop 失败 | 还原上一态 |

---

## 5. 关键页面设计要点

### 5.1 启动 + 登录页

**启动页**：
- 全屏 Logo + Slogan
- 自动检测：版本检查 → 已登录进首页 / 未登录进登录页
- 兜底 Splash 最长 2s

**登录页**：
- 顶部 Logo
- "请输入手机号" 输入框（带国家码选择器，默认 +86）
- "获取验证码" 按钮（60s 倒计时）
- "验证码" 输入框（6 位独立格子，更直观）
- "登录" 主按钮
- 下方次要登录：
  - iOS：Apple 登录按钮（必须，黑白官方样式）
  - 微信登录按钮（绿色官方样式）
- 隐私政策勾选（未勾选时按钮置灰）

### 5.2 买方需求发布页

- **顶部固定**：步骤指示器（3 步）
- **第 1 步**：贝壳链接输入（带"跳过"直接手动）
- **第 2 步**：手动录入表单
  - 区域：单选（朝阳/海淀/...）
  - 价格区间：双滑块
  - 户型：多选标签
  - 购房资质：单选（首套/二套/不限）
  - 看房时间：多选
- **第 3 步**：AI 摘要卡预览 + "发布"按钮

### 5.3 卖方房源录入页

- 顶部：贝壳链接输入（可跳过）
- 表单：
  - 小区：自动补全输入
  - 户型：单选
  - 面积：数字输入（带单位 m²）
  - 总价：数字输入（带单位 万元，自动换算元）
  - 核心标签：可选 Tag 列表
  - 可看时间：单选
- **实勘图**：
  - 9 张图限制
  - 大图预览 + 长按删除
  - 拍照按钮（调起相机）
- 底部："真实性承诺"勾选 + "提交"按钮

### 5.4 匹配推荐页（核心页）

- 顶部固定：**需求摘要卡**（可点击展开看详情）
- 5 张 **SellerCard** 垂直列表
  - 头像 + 脱敏姓名
  - 信用分 Badge
  - 匹配度（百分比 + 进度条）
  - 匹配房源缩略图（1-3 张）
  - "查看详情" / "邀请合作" 按钮
- 邀请中状态：半透明 + 倒计时
- 已失效：灰显 + "已失效" 角标

### 5.5 邀请响应页（卖方）

- Tab 切换：**新邀请 / 历史邀请**
- 新邀请：每条带
  - 买方需求摘要
  - 倒计时（24h，最后 2h 变红色 + 震动）
  - "感兴趣" 主按钮 + "拒绝" 次按钮
- 历史：已接受 / 已拒绝 / 已失效 分类

### 5.6 合作看板页

- 状态分组（带数字徽章）：
  - 待响应（卖方视角）/ 待你接单
  - 方案待审
  - 已握手
  - 合作中
  - 待评价
- 列表项：合作 ID、合作方头像、房源/需求缩略、最后状态时间
- 点击进详情

### 5.7 合作详情页

- 顶部：状态时间线（步骤条）
- 房源/需求卡
- 双方信息（握手后显示真实姓名+电话）
- 操作区：
  - 待响应 → "接单" / "拒绝"
  - 方案待审 → "查看方案" + "确认" / "拒绝"
  - 已握手 → "标记成交" / "终止合作"
  - 待评价 → "去评价"

---

## 6. 状态设计（4 态原则）

每个数据展示区块都必须考虑 4 种状态：

### 6.1 Loading（加载中）
- 骨架屏（**优先于**菊花转圈）
- 关键内容用灰色矩形占位
- 列表用 5 条假数据占位

### 6.2 Empty（空数据）
- 插画（轻量 Lottie 或静态 PNG）
- 标题 + 副标题
- 引导按钮（如"去发布需求"）

### 6.3 Error（错误）
- 错误图标 + 错误文案（**人话**，不是"ERROR 500"）
- "重试" 按钮
- 显示错误码（开发模式）

### 6.4 Success（成功）
- 正常数据展示
- 操作成功的轻提示（Toast 1.5s 自动消失）

---

## 7. 交互动效

### 7.1 时长标准

| 动效类型 | 时长 | 缓动函数 |
| --- | --- | --- |
| **微交互**（按钮按下） | 100ms | `ease-out` |
| **页面转场** | 300ms | `ease-in-out` |
| **大区块展开** | 250ms | `ease-out` |
| **Toast 出现** | 200ms | `ease-out` |
| **Toast 消失** | 150ms | `ease-in` |

### 7.2 关键动效

- **下拉刷新**：自定义动画（不用系统默认）
- **上拉加载**：底部小转圈 + 文字"加载中"
- **空状态出现**：fade-in 200ms
- **倒计时**：数字翻转动画
- **匹配度**：进度条从 0 增长到目标值（800ms）
- **握手成功**：礼花/握手图标 + 触觉反馈（haptic）

### 7.3 触觉反馈

| 场景 | iOS | Android |
| --- | --- | --- |
| 按钮按下 | `HapticFeedback.selectionClick()` | `HapticFeedback.virtualKey()` |
| 成功操作 | `HapticFeedback.mediumImpact()` | `HapticFeedback.mediumImpact()` |
| 警告（即将超时） | `HapticFeedback.heavyImpact()` | `HapticFeedback.heavyImpact()` |
| 错误 | `HapticFeedback.notificationFailure()` | 震动一次 |

---

## 8. 无障碍（Accessibility）

### 8.1 基础要求

- 所有交互元素有 `Semantics` 标签
- 颜色对比度满足 WCAG AA（正文 4.5:1，大字 3:1）
- 触摸目标 ≥ 44pt（iOS）/ 48dp（Android）
- 支持系统字号放大（不要硬编码 `textScaler: 1.0`）
- 支持 VoiceOver / TalkBack

### 8.2 色盲友好

- 不要只靠颜色传达信息（如：红色文字 + ✅ 图标）
- 信用分用"颜色 + 文字标签"双通道

---

## 9. 国际化（i18n）

- MVP 阶段：**只做简体中文**
- 但所有文案**抽离**到 `arb` 文件，不硬编码
- 预留 `lib/l10n/` 目录结构（`intl` + `flutter_localizations`）

```yaml
# l10n.yaml
arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
```

---

## 10. 性能与体验细节

| 场景 | 优化 |
| --- | --- |
| **冷启动** | 启动时只初始化必要服务；延迟非关键模块（推送、分析） |
| **图片加载** | 占位 + 渐显；下采样到显示尺寸；列表滑动不加载 |
| **长列表** | `ListView.builder` + 懒加载；分页加载；下拉刷新 |
| **表单** | 自动 focus 下一个；键盘上方固定按钮 |
| **网络请求** | 失败重试 3 次（指数退避）；并行请求；预取下一页 |
| **下拉刷新冲突** | 内容区滚动到顶才触发下拉 |
| **键盘** | iOS: `keyboardDismissBehavior: onDrag`；Android: 自带 |
| **安全区** | iOS: `SafeArea(bottom: true)`；Android: 适配挖孔屏 |
| **横屏** | MVP 不支持，强制竖屏 |

---

## 11. 错误提示文案规范（人话）

| 场景 | ❌ 不要 | ✅ 要 |
| --- | --- | --- |
| 网络断开 | "Network Error" | "网络好像断开了，检查一下 WiFi？" |
| 验证码错误 | "Code Invalid" | "验证码不对，再看看？" |
| 邀请失效 | "Invitation Expired" | "邀请已超时，TA 没接上，要不邀请下一位？" |
| 信用过低 | "Credit too low" | "您的信用分暂不足以发起合作，先完善资料吧" |
| 上传失败 | "Upload failed" | "图片上传失败，重试一下？" |
| 服务异常 | "Internal Server Error" | "开小差了，稍后再试" |

---

## 12. 视觉资产清单

### 12.1 Logo
- 主 Logo（彩色 + 单色 + 反色）
- App Icon（iOS: 1024×1024；Android: 512×512）
- 启动图（iOS: 各机型；Android: 各密度）

### 12.2 插画
- 空状态插画（4-6 个）
- 错误状态插画（2-3 个）
- 引导页插画（3-4 张）

### 12.3 Icon
- Tab Bar 图标（3 个，2 态）
- 功能图标（推荐 50+，可用 Material Symbols 兜底）

### 12.4 字体
- 思源黑体（仅 Android 端作为中文回退）

> 资源全部存放在 `mobile-app/assets/` 下。

---

## 13. 设计交付物

| 阶段 | 产出 |
| --- | --- |
| **设计稿** | Figma（高保真 + 设计 Token） |
| **切图** | 2x / 3x PNG、WebP |
| **设计 Token** | JSON 文件（颜色、字体、间距、圆角、阴影） |
| **动效** | Lottie JSON / Rive 文件 |
| **图标** | SVG 图标库（Material Symbols 自定义子集） |

---

## 14. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-06-04 | 初稿，配合 v0.3 需求文档 |
