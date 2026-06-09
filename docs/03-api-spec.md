# HomeMatch API 接口规范 v0.1

> 配套文档：[01-requirements.md](01-requirements.md) | [02-architecture.md](02-architecture.md)
> 文档版本：v0.1（初稿，待复核）
> 撰写日期：2026-06-04

---

## 0. 速览

- **Base URL**：`https://api.hmatch.cn`（生产）/ `https://api-dev.hmatch.cn`（测试）
- **版本前缀**：`/v1/`
- **数据格式**：`application/json; charset=utf-8`
- **认证**：`Authorization: Bearer <jwt_token>`
- **时间格式**：ISO 8601（`2026-06-04T16:00:00+08:00`）

---

## 1. 通用规范

### 1.1 响应格式

**成功**：
```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

**列表（带分页）**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ ... ],
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "has_more": true
  }
}
```

**失败**：
```json
{
  "code": 40001,
  "message": "手机号格式错误",
  "detail": { "field": "phone" }
}
```

### 1.2 错误码

| 范围 | 含义 | HTTP 状态 |
| --- | --- | --- |
| 0 | 成功 | 200 |
| 1xxxx | 通用错误 | 400 |
| 10001 | 参数错误 | 400 |
| 10002 | 资源不存在 | 404 |
| 10003 | 权限不足 | 403 |
| 10004 | 未认证 | 401 |
| 10005 | 限流 | 429 |
| 10006 | 服务器异常 | 500 |
| 2xxxx | 认证 | 401 |
| 20001 | 验证码错误 | 401 |
| 20002 | 验证码过期 | 401 |
| 20003 | Token 无效 | 401 |
| 20004 | Token 过期 | 401 |
| 3xxxx | 业务错误 | 400 |
| 30001 | 房源已存在 | 409 |
| 30002 | 邀请已失效 | 410 |
| 30003 | 信用分不足 | 403 |
| 30004 | 房源已冻结 | 403 |
| 4xxxx | 第三方 | 502 |
| 40001 | 短信发送失败 | 502 |
| 40002 | LLM 调用失败 | 502 |
| 40003 | 推送发送失败 | 502 |

### 1.3 鉴权

#### 登录获取 Token

```
POST /v1/auth/login
```

**请求**：
```json
{
  "phone": "13800138000",
  "sms_code": "123456"
}
```

**响应**：
```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 7200,
    "user": {
      "id": 12345,
      "name": "张三",
      "phone_mask": "138****8000",
      "credit_score": 78.5,
      "is_new": false
    }
  }
}
```

#### 刷新 Token

```
POST /v1/auth/refresh
```

**请求**：
```json
{ "refresh_token": "eyJ..." }
```

#### 退出

```
POST /v1/auth/logout
```

### 1.4 分页

**Cursor 游标分页**（推荐用于移动端）：

```
GET /v1/cooperations?cursor=eyJpZCI6MTAwfQ==&limit=20
```

**参数**：
- `cursor`：上一页返回的 `next_cursor`，首次请求不传
- `limit`：单页条数，默认 20，最大 50

**响应**：
```json
{
  "code": 0,
  "data": {
    "items": [ ... ],
    "next_cursor": "eyJpZCI6MTIwfQ==",
    "has_more": true
  }
}
```

### 1.5 限流

- 默认：**60 次/分钟/用户**
- 认证接口：**5 次/分钟/IP**
- 短信发送：**1 次/60 秒/手机号 + 5 次/小时/手机号**
- 超出返回 `429`，body 含 `Retry-After` 头

### 1.6 数据脱敏

向对方展示时**默认脱敏**：
- 手机号：`138****8000`
- 真实姓名：未握手前显示 `张先生` / `李女士`（基于性别或姓氏推断）
- OpenID：内部使用，不外露

---

## 2. 接口清单

### 2.1 认证 (auth)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| POST | `/v1/auth/sms-code` | ❌ | 发送短信验证码 |
| POST | `/v1/auth/login` | ❌ | 短信验证码登录 |
| POST | `/v1/auth/apple-login` | ❌ | Apple 登录 |
| POST | `/v1/auth/wechat-login` | ❌ | 微信登录 |
| POST | `/v1/auth/refresh` | ❌ | 刷新 token |
| POST | `/v1/auth/logout` | ✅ | 退出登录 |
| GET | `/v1/auth/me` | ✅ | 当前用户信息 |

**POST /v1/auth/sms-code**
```json
// 请求
{ "phone": "13800138000", "purpose": "login" }
// purpose: login | bind_phone
// 响应
{ "code": 0, "data": { "expire_in": 300 } }
```

---

### 2.2 用户 (users)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| GET | `/v1/users/me` | ✅ | 我的信息 |
| PATCH | `/v1/users/me` | ✅ | 修改昵称/头像 |
| GET | `/v1/users/{id}/public-profile` | ✅ | 公开主页（脱敏） |
| GET | `/v1/users/{id}/reviews` | ✅ | 评价列表（脱敏） |

**GET /v1/users/{id}/public-profile**
```json
{
  "code": 0,
  "data": {
    "id": 12345,
    "display_name": "张先生",
    "credit_score": 78.5,
    "rating_avg": 4.2,
    "completed_count": 23,
    "active_days_30": 18,
    "is_verified": true
  }
}
```

---

### 2.3 房源 (properties)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| GET | `/v1/properties` | ✅ | 我的房源列表 |
| POST | `/v1/properties` | ✅ | 创建房源 |
| GET | `/v1/properties/{id}` | ✅ | 房源详情 |
| PATCH | `/v1/properties/{id}` | ✅ | 修改房源 |
| DELETE | `/v1/properties/{id}` | ✅ | 下架房源 |
| POST | `/v1/properties/parse-link` | ✅ | 贝壳链接解析（占位） |

**POST /v1/properties**
```json
// 请求
{
  "community": "天通苑北一区",
  "layout": "3室1厅",
  "area": 89.5,
  "total_price": 3800000,
  "tags": ["满五唯一", "近地铁", "南北通透"],
  "viewing_time": "周末全天",
  "images": [
    "https://hmatch-oss.oss-cn-beijing.aliyuncs.com/property/123/abc.jpg"
  ],
  "source_url": "https://bj.ke.com/ershoufang/xxx.html",  // 可选
  "verified": true
}
// 响应
{ "code": 0, "data": { "id": 10086 } }
```

**POST /v1/properties/parse-link**（MVP 占位）
```json
// 请求
{ "url": "https://bj.ke.com/ershoufang/xxx.html" }
// 响应
{ "code": 0, "data": { "parsed": false, "reason": "MVP 暂未实现解析" } }
```

---

### 2.4 需求 (demands)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| GET | `/v1/demands` | ✅ | 我的需求列表 |
| POST | `/v1/demands` | ✅ | 发布需求 |
| GET | `/v1/demands/{id}` | ✅ | 需求详情 |
| PATCH | `/v1/demands/{id}` | ✅ | 修改需求 |
| DELETE | `/v1/demands/{id}` | ✅ | 关闭需求 |
| GET | `/v1/demands/{id}/recommendations` | ✅ | 获取 Top 5 推荐 |

**POST /v1/demands**
```json
// 请求
{
  "district": "朝阳区",
  "price_range": { "min": 3500000, "max": 4500000 },
  "layout": ["2室1厅", "3室1厅"],
  "qualification": "首套",
  "viewing_time": "工作日晚上+周末",
  "source_url": null
}
// 响应
{ "code": 0, "data": { "id": 20001 } }
```

**GET /v1/demands/{id}/recommendations**
```json
{
  "code": 0,
  "data": {
    "sellers": [
      {
        "rank": 1,
        "match_score": 0.92,
        "user": {
          "id": 10001,
          "display_name": "李女士",
          "credit_score": 85.0,
          "rating_avg": 4.5,
          "completed_count": 41,
          "active_days_30": 25
        },
        "matched_properties": [
          {
            "id": 5001,
            "community": "望京西园",
            "layout": "3室1厅",
            "area": 95,
            "total_price": 4200000,
            "cover_image": "https://..."
          }
        ]
      },
      // ... 共 5 个
    ]
  }
}
```

---

### 2.5 邀请/方案/合作 (invitations / proposals / cooperations)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| POST | `/v1/invitations` | ✅ | 发起邀请（买方） |
| GET | `/v1/invitations` | ✅ | 我的邀请列表 |
| GET | `/v1/invitations/{id}` | ✅ | 邀请详情 |
| POST | `/v1/invitations/{id}/accept` | ✅ | 接单（卖方） |
| POST | `/v1/invitations/{id}/reject` | ✅ | 拒绝（卖方） |
| POST | `/v1/invitations/{id}/proposal` | ✅ | 提交方案（卖方） |
| POST | `/v1/invitations/{id}/proposal/confirm` | ✅ | 确认方案（买方） |
| POST | `/v1/invitations/{id}/proposal/decline` | ✅ | 拒绝方案（买方） |
| GET | `/v1/cooperations` | ✅ | 我的合作列表 |
| GET | `/v1/cooperations/{id}` | ✅ | 合作详情 |
| POST | `/v1/cooperations/{id}/close` | ✅ | 关闭合作 |
| POST | `/v1/cooperations/{id}/review` | ✅ | 提交评价 |

**POST /v1/invitations**
```json
// 请求
{
  "demand_id": 20001,
  "seller_id": 10001
}
// 响应
{ "code": 0, "data": { "invitation_id": 30001, "expired_at": "2026-06-05T16:00:00+08:00" } }
```

**POST /v1/invitations/{id}/accept**
```json
// 响应
{ "code": 0, "data": { "invitation_id": 30001, "status": "accepted", "proposal_deadline": "..." } }
```

**POST /v1/invitations/{id}/proposal**
```json
// 请求
{
  "content": "契合点：1) 客户总价预算 400-450 万，望京西园 95 平米三居挂牌 420 万正好匹配；2) 业主诚心出售，可议价；3) 工作日晚上 8 点后可看房...",
  "viewing_suggestion": "建议 6 月 6 日（周五）20:00 带看",
  "owner_situation": "业主自住，已购新房 3 个月，急售"
}
// 响应
{ "code": 0, "data": { "proposal_id": 40001 } }
```

**POST /v1/invitations/{id}/proposal/confirm**
```json
// 响应
{ "code": 0, "data": { "cooperation_id": 50001, "signed_at": "2026-06-04T16:00:00+08:00" } }
```

**POST /v1/cooperations/{id}/review**
```json
// 请求
{
  "rating": 5,
  "comment": "响应快，方案专业，业主配合度高"
}
// 响应
{ "code": 0, "data": { "review_id": 60001 } }
```

---

### 2.6 设备/推送 (devices)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| POST | `/v1/devices/register` | ✅ | 注册推送 token |
| DELETE | `/v1/devices/{token}` | ✅ | 注销 token（退出登录） |
| GET | `/v1/notifications` | ✅ | 通知中心列表 |
| POST | `/v1/notifications/{id}/read` | ✅ | 标记已读 |

**POST /v1/devices/register**
```json
// 请求
{
  "fcm_token": "fK3j...",
  "platform": "ios",  // ios | android
  "app_version": "1.0.0",
  "device_model": "iPhone15,2",
  "os_version": "17.5"
}
```

---

### 2.7 APP 元信息 (app)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| GET | `/v1/app/check-version` | ❌ | 版本检查 |

**GET /v1/app/check-version?platform=ios&current=1.0.0**
```json
{
  "code": 0,
  "data": {
    "latest_version": "1.2.0",
    "min_supported_version": "1.0.0",
    "force_update": false,
    "release_notes": "1. 优化匹配速度\n2. 修复邀请推送延迟 bug",
    "download_url": "https://apps.apple.com/app/idxxx"
  }
}
```

---

### 2.8 文件上传 (upload)

| Method | Path | 鉴权 | 描述 |
| --- | --- | --- | --- |
| POST | `/v1/upload/sign` | ✅ | 申请 OSS 直传签名 |

**POST /v1/upload/sign**
```json
// 请求
{
  "purpose": "property_image",  // property_image | review_image | avatar
  "mime_type": "image/jpeg",
  "file_size": 1024000
}
// 响应
{
  "code": 0,
  "data": {
    "oss_endpoint": "https://hmatch-oss.oss-cn-beijing.aliyuncs.com",
    "bucket": "hmatch-oss",
    "key_prefix": "property/123/",
    "access_key_id": "STS.xxx",
    "access_key_secret": "xxx",
    "security_token": "xxx",
    "expire_at": "2026-06-04T16:05:00+08:00"
  }
}
```

---

## 3. 接口详细示例

### 3.1 完整的"发布需求 → 看推荐 → 发起邀请"流程

```
1) POST /v1/auth/sms-code            { phone, purpose: "login" }
2) POST /v1/auth/login               { phone, sms_code } → 拿到 access_token
3) POST /v1/devices/register         { fcm_token, platform, app_version }
4) POST /v1/demands                  { district, price_range, ... } → demand_id
5) GET  /v1/demands/{id}/recommendations → 拿到 5 个 seller
6) POST /v1/invitations              { demand_id, seller_id } → invitation_id
7) (卖方) GET /v1/invitations        → 看到新邀请
8) (卖方) POST /v1/invitations/{id}/accept → status: accepted
9) (卖方) POST /v1/invitations/{id}/proposal → proposal_id
10) (买方) POST /v1/invitations/{id}/proposal/confirm → cooperation_id
11) ...合作中...
12) POST /v1/cooperations/{id}/close
13) POST /v1/cooperations/{id}/review
14) (双方) POST /v1/cooperations/{id}/review
```

---

## 4. 数据模型 Schema 简表

> 完整 Pydantic / OpenAPI 规范由 FastAPI 自动生成在 `/docs` 和 `/redoc`。

| 资源 | 关键字段 | 备注 |
| --- | --- | --- |
| **User** | id, phone_mask, display_name, credit_score, rating_avg, completed_count, active_days_30, is_verified, created_at | 公开视图不返回 phone_encrypted |
| **Property** | id, seller_id, community, layout, area, total_price, tags, viewing_time, images, source_url, status, created_at | |
| **Demand** | id, buyer_id, district, price_range, layout, qualification, viewing_time, source_url, status, created_at | |
| **Invitation** | id, demand_id, buyer_id, seller_id, status, expired_at, responded_at, created_at | |
| **Proposal** | id, invitation_id, content, viewing_suggestion, owner_situation, submitted_at | |
| **Cooperation** | id, invitation_id, buyer_id, seller_id, status, memo_content, signed_at, closed_at | |
| **Review** | id, cooperation_id, reviewer_id, reviewee_id, rating, comment, is_anonymous, created_at | |
| **Device** | id, user_id, fcm_token, platform, app_version, device_model, os_version, last_active_at | |
| **AppVersion** | id, platform, latest_version, min_supported_version, force_update, release_notes, download_url | |
| **EventLog** | id, user_id, event_name, event_data, app_version, platform, created_at | |

---

## 5. 错误响应完整示例

### 401 - 未登录
```json
{ "code": 10004, "message": "未登录" }
```

### 40001 - 验证码错误
```json
{ "code": 20001, "message": "验证码错误", "detail": { "remaining_attempts": 3 } }
```

### 30002 - 邀请已失效
```json
{ "code": 30002, "message": "邀请已超时失效" }
```

### 10005 - 限流
```json
{ "code": 10005, "message": "请求过于频繁", "detail": { "retry_after": 60 } }
```

---

## 6. 性能与 SLA

| 指标 | 目标 |
| --- | --- |
| **P95 响应** | < 500ms |
| **P99 响应** | < 2s |
| **可用性** | ≥ 99.5% |
| **错误率** | < 0.1% |
| **推送延迟** | < 5s |

---

## 7. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-06-04 | 初稿，配合 v0.3 需求文档 |
