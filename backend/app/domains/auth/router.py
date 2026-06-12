from __future__ import annotations

"""Auth 域 - 路由层。"""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import (
    AppleAuthInvalidTokenError,
    InvalidTokenError,
    WeChatAuthUnavailableError,
)
from app.core.logging import get_logger
from app.core.ratelimit import get_limiter
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.domains.auth.mock_names import generate_mock_name
from app.domains.auth.schemas import (
    AppleLoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    SmsCodeRequest,
    SmsCodeResponse,
    SmsLoginRequest,
    TokenPair,
    WechatLoginRequest,
)
from app.domains.auth.service import SmsService, UserService
from app.models.user import User, UserStatus
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])
limiter: Limiter = get_limiter()


# ============== 依赖注入 ==============

def get_sms_service(request: Request) -> SmsService:
    """FastAPI 依赖：获取 SmsService。"""
    redis_client = request.app.state.redis
    return SmsService(redis_client)


def get_user_service(
    request: Request,
    db: Session = Depends(get_db),
) -> UserService:
    """FastAPI 依赖：获取 UserService。"""
    redis_client = request.app.state.redis
    sms = SmsService(redis_client)
    return UserService(db, sms)


# ============== 1. 发送短信验证码 ==============

@router.post(
    "/sms-code",
    response_model=APIResponse[SmsCodeResponse],
    summary="发送短信验证码",
)
async def send_sms_code(
    body: SmsCodeRequest,
    sms: SmsService = Depends(get_sms_service),
) -> APIResponse[SmsCodeResponse]:
    """发送登录短信验证码。

    - 测试模式（`SMS_PROVIDER=mock`）：所有验证码固定为 `1234`（见 .env）
    - 生产模式：调阿里云短信发送
    - 限流：60s 一次，每小时最多 5 次（在 SmsService 内部实现）
    """
    result = await sms.send_code(body.phone, body.purpose)
    return APIResponse(data=result)


# ============== 2. 短信登录（兜底方式） ==============

@router.post(
    "/login",
    response_model=APIResponse[LoginResponse],
    summary="短信验证码登录（兜底方式）",
)
async def sms_login(
    body: SmsLoginRequest,
    user_service: UserService = Depends(get_user_service),
) -> APIResponse[LoginResponse]:
    """用手机号 + 短信验证码登录。

    v0.4 调整：这是**兜底方式**，主推微信登录（[D-013]）。
    """
    # 1. 校验验证码
    user_service.sms.verify_code(body.phone, body.sms_code, "login")

    # 2. 查找或创建用户
    user, is_new = user_service.find_or_create_by_phone(body.phone)

    # 3. 构造响应
    response = user_service.build_login_response(user, is_new)
    logger.info(
        "User logged in via SMS",
        extra={"user_id": user.id, "is_new": is_new},
    )
    return APIResponse(data=response)


# ============== 3. 微信登录（v0.4 主登录） ==============

@router.post(
    "/wechat-login",
    response_model=APIResponse[LoginResponse],
    summary="微信登录（主登录方式）",
)
async def wechat_login(
    body: WechatLoginRequest,
    db: Session = Depends(get_db),
) -> APIResponse[LoginResponse]:
    """用微信授权 code 登录（[D-013]）。

    流程：
    1. 用 `code` 调微信接口换 `openid` + `unionid`
    2. 查 users 表，有则登录，无则自动注册
    3. 返回 JWT

    [Sprint1-P0] 生产安全：
    - 生产环境（``app_env=production``）**禁止** mock 兜底
    - 缺 app_id/secret → 返 503（WeChatAuthUnavailableError），不再静默放行
    - 开发/staging 保留 mock（dev 切换器需要）
    """
    # 1. code 换 openid + unionid
    app_id = body.app_id or settings.wechat_test_app_id or settings.wechat_app_id
    app_secret = settings.wechat_test_app_secret or settings.wechat_app_secret

    if not app_id or not app_secret:
        # [Sprint1-P0] 生产环境：禁止 mock 兜底
        if settings.is_production:
            logger.error(
                "WeChat login unavailable in production: app_id/secret not configured",
                extra={"code_prefix": body.code[:16] if body.code else None},
            )
            raise WeChatAuthUnavailableError(
                "微信登录暂不可用（缺少 WECHAT_APP_ID / WECHAT_APP_SECRET）",
                detail={"missing": ["wechat_app_id" if not app_id else None,
                                   "wechat_app_secret" if not app_secret else None]},
            )

        # dev / staging 兜底：直接用 code 当 openid
        # P1-0 修复（2026-06-10）说明：
        # - dev code 是稳定的 wechat code label（如 `dev_alice`）
        # - 这里生成 `mock_unionid_{code[:16]}` 作为 users 表的查找 key
        # - user.id 由 PostgreSQL SERIAL 序列按创建顺序分配，**与 dev code 数字无关**
        # - 所以 `dev_seller_7` 拿到的可能是 user 17 或任何 id（取决于 DB 历史）
        # - 6 个稳定 dev user 由 `backend/scripts/seed_dev_users.py` 预创建，
        #   详见 `docs/05-dev-users.md`
        logger.warning(
            "WeChat app_id/secret not configured, using mock openid (dev mode only)",
            extra={"code_prefix": body.code[:16] if body.code else None,
                   "app_env": settings.app_env},
        )
        unionid = f"mock_unionid_{body.code[:16]}"
        openid = f"mock_openid_{body.code[:16]}"
        # Mock 模式用百家姓生成稳定的随机名（同一 code 始终同一名字）
        name, display_name = generate_mock_name(body.code)
        nickname = name
        avatar_url = None
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.weixin.qq.com/sns/oauth2/access_token",
                    params={
                        "appid": app_id,
                        "secret": app_secret,
                        "code": body.code,
                        "grant_type": "authorization_code",
                    },
                )
                data = resp.json()
                if data.get("errcode", 0) != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"微信登录失败: {data.get('errmsg', '未知错误')}",
                    )
                openid = data["openid"]
                unionid = data.get("unionid", openid)
                # 真实微信：优先用微信返回的昵称；如果为空则降级为 mock 名字
                raw_nick = (data.get("nickname") or "").strip()
                if raw_nick:
                    nickname = raw_nick[:64]
                else:
                    nickname, _ = generate_mock_name(openid)
                avatar_url = data.get("headimgurl")
        except httpx.HTTPError as e:
            logger.error("WeChat API call failed", extra={"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="微信服务暂时不可用",
            ) from e

    # 2. 查找或创建用户
    sms = SmsService(None)  # wechat 登录不调 sms
    user_service = UserService(db, sms)
    user, is_new = user_service.find_or_create_by_wechat(
        unionid, openid, nickname, avatar_url
    )

    # 3. 构造响应
    response = user_service.build_login_response(user, is_new)
    logger.info(
        "User logged in via WeChat",
        extra={"user_id": user.id, "is_new": is_new},
    )
    return APIResponse(data=response)


# ============== 4. Apple 登录（iOS 必选） ==============

@router.post(
    "/apple-login",
    response_model=APIResponse[LoginResponse],
    summary="Apple 登录（iOS 上架合规必选）",
)
async def apple_login(
    body: AppleLoginRequest,
    db: Session = Depends(get_db),
) -> APIResponse[LoginResponse]:
    """iOS 通过 Apple 登录（[D-013] iOS 上架合规要求）。

    [Sprint1-P0] 安全加固：
    - 生产环境**必须**用 Apple JWKS 公钥验签 identity_token（签名/aud/iss/exp）
    - 用 payload.sub（Apple 唯一用户 id）当 apple_user_id
    - dev/staging 保留 mock 路径（方便本地 iOS 模拟器无 Apple 账号时调试）
    """
    from app.domains.auth.apple_verify import (
        is_dev_mode,
        mock_extract_user_id_for_dev,
        verify_apple_identity_token,
    )

    if is_dev_mode() and settings.apple_client_id == "":
        # dev 模式 + 没配 client_id → 走 mock（之前 MVP 方案）
        # 生产环境绝不走这里（is_dev_mode()=False）
        try:
            apple_user_id = mock_extract_user_id_for_dev(body.identity_token)
        except AppleAuthInvalidTokenError:
            raise
    else:
        # 真实生产路径：验签 Apple JWT
        try:
            payload = verify_apple_identity_token(body.identity_token)
            apple_user_id = payload["sub"]
        except AppleAuthInvalidTokenError:
            # 已经带结构化 detail，直接 re-raise
            raise

    user = db.scalar(select(User).where(User.apple_user_id == apple_user_id))

    if user:
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        is_new = False
    else:
        user = User(
            apple_user_id=apple_user_id,
            name="Apple 用户",
            display_name="Apple 用户",  # Apple 登录目前没真实名，统一用 Apple
            status=UserStatus.ACTIVE,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True
        logger.info("New Apple user created", extra={"user_id": user.id})

    sms = SmsService(None)
    user_service = UserService(db, sms)
    response = user_service.build_login_response(user, is_new)
    return APIResponse(data=response)


# ============== 5. 刷新 Token ==============

@router.post(
    "/refresh",
    response_model=APIResponse[TokenPair],
    summary="刷新 Access Token",
)
async def refresh_token(
    body: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> APIResponse[TokenPair]:
    """用 Refresh Token 换新的 Access Token。"""
    payload = decode_token(body.refresh_token)
    if not payload:
        raise InvalidTokenError()
    if payload.get("type") != "refresh":
        raise InvalidTokenError("Token 类型错误")

    user_id = int(payload["sub"])
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise InvalidTokenError("用户不存在")

    access = create_access_token(user.id, extra_claims={"name": user.name})
    refresh = create_refresh_token(user.id)
    return APIResponse(
        data=TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
    )


# ============== 6. 当前用户信息 ==============

@router.get(
    "/me",
    response_model=APIResponse[dict],
    summary="获取当前用户信息",
)
async def get_me() -> APIResponse[dict]:
    """获取当前登录用户信息。

    TODO: 加 current_user 依赖，从 Authorization header 解析 JWT。
    """
    return APIResponse(data={"message": "TODO: 实现 current_user 依赖"})
