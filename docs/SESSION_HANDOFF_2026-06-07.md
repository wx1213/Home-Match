# HomeMatch 开发会话交接文档

> 日期：2026-06-07
> 状态：UI 优化 + 完整业务闭环已跑通
> 下次继续：从本文末"下一步"开始

---

## 1. 当前环境

| 项目 | 状态 |
| --- | --- |
| 后端服务 | ✅ Python 3.11 + FastAPI + SQLAlchemy 2.0 + PostgreSQL 15 + Redis 7 |
| 移动端 | ✅ Flutter 3.44.1 + Riverpod 2 + go_router 14（StatefulShellRoute）|
| 数据库 | ✅ PostgreSQL 9 张业务表 + alembic 迁移 v3 |
| 模拟器 | iPhone 17 Pro (iOS 26.5) 已启动 |
| 工作目录 | `/Users/wangxiao/WorkSpace/RD` |

### 服务启动命令

```bash
# 后端
cd /Users/wangxiao/WorkSpace/RD/backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# 重算信用分（每日定时任务）
python -m scripts.recompute_credit_scores

# 移动端（开发模式自动登录 user 3）
cd /Users/wangxiao/WorkSpace/RD/mobile-app
nohup flutter run -d "179C75B4-1813-4A95-ABAB-E67ADF2435A8" --no-hot > /tmp/flutter_run.log 2>&1 &
```

---

## 2. 当前数据库状态（2026-06-07 21:55 快照）

```
users         : 9
properties    : 9
demands       : 11
invitations   : 10
cooperations  : 1  (COOP-1: handshaked → completed, buyer=3 seller=4)
reviews       : 2  (1 each direction for COOP-1)
proposals     : 4
```

### 用户状态

| id | name | credit_score | rating_avg | rating_count | activity_30d | completed | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 微信用户 | 6 | 0 | 0 | 0 | 0 | dev_visual_test (旧) |
| **3** | 微信用户 | **24** | 4 | 1 | 0 | 1 | 买方代表 dev_visual_test |
| **4** | 微信用户 | **46.4** | 4 | 1 | 4 | 1 | 卖方-望京 seed_seller_1 |
| **5** | 微信用户 | 6 | 0 | 0 | 2 | 0 | 卖方-国贸 seed_seller_2 |
| 6 | 微信用户 | 6 | 0 | 0 | 1 | 0 | 卖方-中关村 seed_seller_4 |
| 7-9 | 微信用户 | 6 | 0 | 0 | 0 | 0 | 其他 |

---

## 3. 已完成的功能（按时间顺序）

### 3.1 设计基础设施
- `lib/core/theme/app_tokens.dart` — HMSpace / HMRadius / HMColors / HMShadow
- `lib/core/theme/app_theme.dart` — Material 3 主题（含 chipTheme 修复）
- `lib/core/widgets/empty_state.dart` — 渐变圆形图标空状态
- `lib/core/widgets/credit_badge.dart` — 5 档颜色（优质/良好/一般/偏低/风险）
- `lib/core/widgets/status_chip.dart` — StatusChip + HMTag + HMUserAvatar + 状态映射
- `lib/core/widgets/countdown_text.dart` — 1h 内自动变红的倒计时

### 3.2 页面实现
- 登录页（渐变 + 装饰圆 + 微信登录按钮）
- 需求列表（卡片化、区域徽章、大字价格、AI 推荐按钮）
- 需求表单
- 房源列表（封面占位、实勘/上架徽章、tag 列表）
- 房源表单
- 房源详情页（关键指标卡、维护经纪人）
- 邀请列表
- 邀请详情页（**按身份切换按钮**：buyer/seller 看到的操作不同）
- 方案详情页（双方可看，含拒绝原因）
- 合作看板（**统一仪表板**：4 数字概览 + 进行中合作 + 进行中邀请 + 历史折叠）
- 合作详情页（5 步时间线 + 备忘录）
- 评价表单（5 星 + 评分提示 + 标签分组 + 评价后回跳合作详情）
- 个人中心（**真实统计 + 信用分公式可视化**）

### 3.3 业务闭环
- 完整跑通：发布需求 → AI 推荐 → 邀请 → 卖方接单 → 提交方案 → 买方确认 → 握手 → 互评 → 信用分更新

### 3.4 开发便利
- `lib/main.dart` — 自动登录（dev_visual_test 默认 = user 3）
- `kDevWechatCodes` 列表 — 6 个 dev 身份
- `switchDevUser(container, code)` — 暴露给 UI 调用
- 个人中心 🐛 虫虫图标 → 弹出身份切换器（6 个卡片）
- 路由重构成 `StatefulShellRoute.indexedStack` — 底导常驻 4 个 Tab

### 3.5 后端能力
- `GET /v1/users/me` + `GET /v1/users/me/stats`
- `POST /v1/cooperations/{id}/review` 自动 flush + 触发信用分重算
- `recompute_all_credit_scores()` 批量重算
- `scripts/recompute_credit_scores.py` — CLI 每日定时任务

---

## 4. 关键 bug 修复记录

### 4.1 邀请详情页 403 错误
- **症状**：user 3 (买方) 在 proposal_review 状态看到"拒绝"按钮
- **根因**：UI 写死了"接单/拒绝"按钮，没区分身份
- **修复**：invitation_detail_screen.dart 加 `_ViewerRole` 判断，按 (状态 × 身份) 矩阵切换按钮

### 4.2 信用分 update_user_credit_score autoflush 失败
- **症状**：user 3 评价后 user 3 的 rating_avg 一直是 0
- **根因**：`_compute_rating_avg` 之前查到的是 SQLAlchemy session 缓存
- **修复**：`db.flush()` 强制 flush 后再查

### 4.3 BottomNavigationBar 消失
- **症状**：进入 /cooperations 等子路由后底导消失
- **根因**：原 home_screen 自管 IndexedStack，子路由是顶级 GoRoute
- **修复**：改用 `StatefulShellRoute.indexedStack`，底导归 HomeShell 管

### 4.4 withOpacity 废弃
- 全局替换为 `withValues(alpha: ...)`

### 4.5 合作看板空状态 CTA 错
- **症状**：卖方身份看"去发布需求"提示
- **修复**：加 `_UserRole` 探测（buyer/seller/both/neither），不同身份不同 CTA

---

## 5. dev_visual_test 用户数据 (user 3)

```
需求：7 条（朝阳区/丰台区/海淀区/西城区各种价格区间）
房源：2 套（双井富力城 580万 / 望京西园 425万）
合作：COOP-1 (与 user 4 完成) + 2 个 handshaked (与 user 5)
评价：收到 1 条 4 星（来自 user 4）
信用分：24.0（4 星 × 20 × 0.3 活跃系数）
```

---

## 6. 关键文件路径（按重要性）

### 后端
- `backend/app/domains/invitations/state_machine.py` — 状态机
- `backend/app/domains/reviews/credit_score.py` — 信用分公式
- `backend/app/domains/reviews/router.py` — 评价路由（含 flush fix）
- `backend/app/domains/users/router.py` — 新增的 /users/me endpoints
- `backend/app/workers/credit_score.py` — RQ 任务
- `backend/scripts/recompute_credit_scores.py` — CLI 定时任务
- `backend/app/domains/proposals/router.py` — 方案查询

### 移动端
- `mobile-app/lib/main.dart` — 入口 + dev auto-login
- `mobile-app/lib/core/router/app_router.dart` — StatefulShellRoute
- `mobile-app/lib/core/theme/app_tokens.dart` + `app_theme.dart` — 设计系统
- `mobile-app/lib/core/widgets/status_chip.dart` — 状态映射
- `mobile-app/lib/features/home/home_shell.dart` — 底导
- `mobile-app/lib/features/cooperation/cooperation_board_screen.dart` — 统一仪表板
- `mobile-app/lib/features/cooperation/cooperation_detail_screen.dart` — 合作详情
- `mobile-app/lib/features/invitation/invitation_detail_screen.dart` — 邀请详情（角色感知）
- `mobile-app/lib/features/invitation/proposal_view_screen.dart` — 方案详情
- `mobile-app/lib/features/review/review_form_screen.dart` — 评价表单
- `mobile-app/lib/features/profile/profile_screen.dart` — 个人中心（统计 + 信用分）
- `mobile-app/lib/features/auth/user_service.dart` — UserStats 数据层

---

## 7. 重要 UI 截图清单

位置：`/tmp/hm_screens/`

| 编号 | 内容 |
| --- | --- |
| 24_v2_login.png | 登录页（最终版） |
| 50_v4_default_demands.png | 需求 Tab（默认首页） |
| 51_v4_coop_tab.png | 合作 Tab（4 数字概览） |
| 52_v4_prop_tab.png | 房源 Tab |
| 53_v4_profile_tab.png | 个人中心 Tab |
| 60_buyer_view.png | pending + 买方（等卖方） |
| 61_seller_view.png | pending + 卖方（接单/拒绝） |
| 62_buyer_proposal_review.png | proposal_review + 买方（确认握手） |
| 63_seller_proposal_review.png | proposal_review + 卖方（等待） |
| 70_profile_with_bug.png | 个人中心 + 🐛 切换器入口 |
| 83_relanched.png | 卖方空状态："查看我的邀请" |
| 84_buyer_view.png | 买方视图 |
| 91_dashboard_seller_clean.png | 统一仪表板（卖方） |
| 92_dashboard_buyer.png | 统一仪表板（买方，4 卡片 + 2 合作 + 4 邀请） |
| 93_seller_inv_detail.png | 卖方邀请详情（紫色 + 查看方案入口） |
| 100_profile_real.png | 个人中心真实统计（user 3, 24.0） |
| 101_profile_user4.png | 个人中心真实统计（user 4, 46.4） |

---

## 8. 下次可继续的方向

### 8.1 立即可做（无新功能）
- [ ] 给所有页面（特别是 Profile / Cooperation Board / Invitation）加 ⭐ 评分可视化
- [ ] 信用分变化历史折线图（30 天）
- [ ] 评价的"标签"字段入库（review.tags，目前前端能发但后端不存）
- [ ] 邀请的"撤销"流程（状态机需要新增 transition）

### 8.2 中等投入
- [ ] 房源图片上传 → OSS（用 STS token 直传）
- [ ] 通知推送（firebase_admin，APNs + FCM）
- [ ] 接单超时 / 评价超时定时器（用 RQ 延迟任务）
- [ ] 评价标签云：用户画像

### 8.3 较大投入
- [ ] Web 管理后台（Vue 3 + Element Plus）
- [ ] 数据导出
- [ ] 信用分保护期机制
- [ ] 多语言支持（l10n 框架已预留）

---

## 9. 复盘：本次会话完整时间线

1. 项目审计 + 后端服务检查
2. Flutter analyze（58 issues，0 error）
3. 跑通空数据 → 创建 seed
4. **设计 tokens + 主题升级**（HMSpace/HMRadius/HMColors/HMShadow）
5. 升级共享组件（EmptyState/CreditBadge/StatusChip/HMTag/HMUserAvatar）
6. 升级 4 个 Tab 页面（需求/房源/合作/我的）
7. 设计登录页（渐变 + 装饰圆）
8. 后端新增 /v1/cooperations 列表接口
9. 实现合作看板（真实数据 + 卡片 + 时间线）
10. 实现合作详情页（5 步时间线 + 备忘录）
11. 升级邀请详情页（按身份切换按钮）
12. 实现房源详情页
13. 升级评价表单（评分提示 + 标签 + 回跳）
14. **重构成 StatefulShellRoute.indexedStack**（底导常驻）
15. **添加开发模式身份切换器**（🐛 虫虫图标 + 6 个 dev 卡片）
16. **修复 403 错误**（身份感知邀请详情）
17. **重构合作看板为统一仪表板**（4 数字 + 进行中 + 折叠历史）
18. **个人中心真实统计**（/v1/users/me/stats + 公式可视化）
19. **修复信用分 autoflush bug**（db.flush()）
20. **新增每日 RQ 任务**（scripts/recompute_credit_scores.py）

---

## 10. 重启检查清单

明天回来时按这个顺序验证：
```bash
# 1. 启动后端
cd /Users/wangxiao/WorkSpace/RD/backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 4
curl http://localhost:8000/v1/health  # 应返回 ok

# 2. 启动 APP
cd /Users/wangxiao/WorkSpace/RD/mobile-app
nohup flutter run -d "179C75B4-1813-4A95-ABAB-E67ADF2435A8" --no-hot > /tmp/flutter_run.log 2>&1 &

# 3. 验证数据仍在
PGPASSWORD=devpass psql -h localhost -U homa -d homa -c "SELECT id, credit_score FROM users WHERE id IN (3, 4);"
# 应看到 user 3 = 24, user 4 = 46.4
```

如果数据库没了：
```bash
# 跑种子脚本（还没写，可以从会话里的 SQL 重新生成）
# 暂时用 manual 方式
```

如果代码有问题：
- 所有改动都在 `lib/` 和 `app/` 下的源文件里
- 没改过依赖（`pubspec.yaml` / `pyproject.toml` 保持原样）
- DB schema 没变（不需要 alembic upgrade）
