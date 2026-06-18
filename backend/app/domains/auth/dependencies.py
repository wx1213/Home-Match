"""JWT current_user 依赖 - 从 Authorization header 解析 JWT 得到当前用户。"""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import InvalidTokenError
from app.core.logging import get_logger
from app.core.security import decode_token
from app.models.user import User

logger = get_logger(__name__)


def _extract_token(authorization: str | None) -> str:
    """从 Authorization header 提取 Bearer token。"""
    if not authorization:
        raise InvalidTokenError("缺少 Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenError("Authorization 格式错误，应为 'Bearer <token>'")
    return parts[1]


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI 依赖：从 JWT 解析当前用户。

    用法:
        @router.get("/me")
        def handler(user: User = Depends(get_current_user)):
            ...
    """
    token = _extract_token(authorization)
    payload = decode_token(token)
    if not payload:
        raise InvalidTokenError("Token 无效或已过期")
    if payload.get("type") != "access":
        raise InvalidTokenError("Token 类型错误，需要 access token")

    user_id = int(payload["sub"])
    user = db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if not user:
        raise InvalidTokenError("用户不存在")
    return user


def get_current_user_id(
    user: User = Depends(get_current_user),
) -> int:
    """便捷依赖：只要 user_id。"""
    return user.id


def get_optional_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """可选当前用户（公开接口 + 部分登录态场景用）。"""
    if not authorization:
        return None
    try:
        return get_current_user(authorization=authorization, db=db)
    except Exception:
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI 依赖：要求当前用户是 admin。

    用法:
        @router.get("/admin/xxx")
        def handler(user: User = Depends(require_admin)):
            ...

    注：token 是 stateless 的，不读 admin claim；admin 权限每次都从 DB
    校验（get_current_user 已查过 user 对象，直接读字段即可）。
    """
    if not user.is_admin:
        from app.core.errors import PermissionDeniedError
        raise PermissionDeniedError("需要 admin 权限")
    return user
