# Dev 用户管理（P1-0）

> 本文档说明 HomeMatch dev 环境下的"伪微信用户"机制，以及 6 个稳定 dev code 的用法。
> 配套代码：[`backend/scripts/seed_dev_users.py`](../backend/scripts/seed_dev_users.py)

---

## 为什么需要 dev user？

MVP 阶段没有真实微信 AppID 配置（`WECHAT_APP_ID` / `WECHAT_APP_SECRET` 为空）时，
`POST /v1/auth/wechat-login` 会走 mock 分支：用 wechat `code` 当作 unionid，**自动创建用户**。

这让 dev 阶段不需要每次都申请微信授权就能跑通登录、发布需求、发邀请等核心流程。

---

## dev code → user id 关系（**关键**）

| 概念 | 含义 |
|---|---|
| **dev code** | 稳定的 wechat code label，如 `dev_alice`（永远不变） |
| **mock_unionid** | 后端合成的 unionid：`mock_unionid_{code[:16]}`（作为 users 表唯一 key） |
| **user id** | PostgreSQL SERIAL 序列按创建顺序分配的 PK（**与 dev code 里的数字无关**） |

**重要警告**：`dev_seller_7` 拿到的 user id **不一定是 7**。可能是 17、23、任何值。
**取决于 dev code 第一次登录时，DB 已经创建过多少个 mock user**。

解决方案：
1. dev 切换器 UI（个人中心 → 🐛 按钮）已显示 `#userId` 徽章
2. 后端提供 `GET /v1/users/dev-identities` 接口动态发现所有 mock user
3. 6 个稳定 dev code 由 seed 脚本预创建，避免每次重新 setup 拿到不同 id

---

## 6 个稳定 dev code

| dev code | 角色 | 初始信用 | 用途 |
|---|---|---|---|
| `dev_alice` | buyer | 85.0 | 高信用买方代表（推荐 Top 5 中高分种子） |
| `dev_bob` | seller | 88.0 | 高信用卖方（接单/合作） |
| `dev_carol` | both | 82.0 | 双重身份（复杂场景） |
| `dev_dave` | buyer | 55.0 | 低信用买方（信用分差异） |
| `dev_eve` | seller | 92.0 | 高信用卖方（接单优先） |
| `dev_zach` | buyer | 70.0 | E2E 测试跑用户 |

> 名字按 `mock_names.generate_mock_name(code)` 稳定生成（基于 code 哈希），同一 code 永远拿同一名字。

---

## 如何查看实际 user_id？

### 方式 1：dev 切换器 UI（推荐）

APP 启动 → 个人中心 → 点击右上角 🐛 图标 → 弹出 bottom sheet，每个 tile 都显示 `#userId`。

### 方式 2：curl 后端接口

```bash
curl -s http://localhost:8000/v1/users/dev-identities | jq '.data[] | {code, user_id, display_name}'
```

输出示例：

```json
{ "code": "dev_alice", "user_id": 18, "display_name": "邓嘉怡" }
{ "code": "dev_bob",   "user_id": 19, "display_name": "许建华" }
{ "code": "dev_carol", "user_id": 20, "display_name": "李超" }
{ "code": "dev_dave",  "user_id": 21, "display_name": "曹欣怡" }
{ "code": "dev_eve",   "user_id": 22, "display_name": "周子轩" }
{ "code": "dev_zach",  "user_id": 23, "display_name": "吴浩然" }
```

### 方式 3：psql 直查

```bash
PGPASSWORD=devpass psql -h 127.0.0.1 -U homa -d homa \
  -c "SELECT id, name, wechat_unionid FROM users WHERE wechat_unionid LIKE 'mock_%' ORDER BY id;"
```

---

## 切换 dev 用户

### APP 端

1. 个人中心 → 点击右上角 🐛 图标
2. 在 bottom sheet 选择要切换的 dev 身份
3. 自动用对应 code 重新登录，跳转到需求页

### 后端 API

```bash
curl -X POST http://localhost:8000/v1/auth/wechat-login \
  -H "Content-Type: application/json" \
  -d '{"code": "dev_alice"}'
```

返回的 `data.user.id` 就是该 dev code 对应的 user id。

---

## Seed 脚本用法

### 首次 setup（幂等创建 6 个稳定 dev user）

```bash
./scripts/seed_dev_users.sh
```

输出示例：

```
code               user_id  name     display  role     credit 状态
--------------------------------------------------------------------------------
dev_alice          #18      邓嘉怡      邓嘉怡      buyer    85.0   ✨ created
dev_bob            #19      许涛       许建华      seller   88.0   ✨ created
...
```

第二次运行会显示 `exists`，可安全重复跑。

### Clean start（⚠️ 会级联删数据）

```bash
./scripts/seed_dev_users.sh --wipe
```

这会先删所有 `wechat_unionid LIKE 'mock_%' OR wechat_openid LIKE 'mock_%'` 的 user，
**连带 properties / demands / invitations / proposals / cooperations / reviews 一起 cascade 删**。
仅在 dev 环境用！

---

## 新 dev 环境 checklist

```bash
cd /Users/wangxiao/WorkSpace/RD

# 1. 启动后端
./scripts/start_backend.sh

# 2. Seed 6 个稳定 dev user
./scripts/seed_dev_users.sh

# 3. 启动信用分调度器
./scripts/start_credit_cron.sh

# 4. 启动 APP
./scripts/start_flutter.sh
```

---

## 历史背景

- **2026-06-10 (P1-0)**：发现 dev code 跟 user id 错位（如 `dev_seller_7` → user 17），
  引入 6 个稳定 dev code + seed 脚本 + UI 突出显示 user_id。
- 之前：17 个 mock user 是按历史登录顺序创建的，id 1-17 完全没有文档化。
