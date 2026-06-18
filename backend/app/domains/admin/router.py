"""Admin 占位端点 - 验证 admin 链路已通，二期在 router 内追加实际管理接口。

MVP 阶段 admin 链路验证：
- require_admin Depends（chain: get_current_user → is_admin 校验）
- /v1/admin/me 端点：返回当前 admin 用户的核心标识
- 二期在本 router 内追加实际管理接口（用户冻结、房源审核、评价异常处理、LLM 用量看板等）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.domains.auth.dependencies import require_admin
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", summary="当前 admin 信息（占位）")
def admin_me(user: User = Depends(require_admin)) -> dict:
    """返回当前 admin 用户的核心标识。链路验证用，二期替换为完整 admin profile。"""
    return {
        "id": user.id,
        "name": user.name,
        "is_admin": user.is_admin,
    }
