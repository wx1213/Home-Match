"""Devices 域 - 设备注册（推送用）。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.domains.auth.dependencies import get_current_user
from app.models.device import Device
from app.models.user import User
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/devices", tags=["设备"])


class DeviceRegisterRequest(BaseModel):
    """设备注册请求。"""

    fcm_token: str
    platform: str  # ios | android
    app_version: str = "0.1.0"
    device_model: str | None = None
    os_version: str | None = None


@router.post("/register", summary="注册推送设备")
async def register_device(
    body: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """APP 启动/登录后调用，注册推送 token。"""
    # 查现有
    existing = db.scalar(
        select(Device).where(Device.fcm_token == body.fcm_token)
    )
    if existing:
        existing.user_id = user.id
        existing.platform = body.platform
        existing.app_version = body.app_version
        existing.device_model = body.device_model
        existing.os_version = body.os_version
        existing.last_active_at = datetime.now(timezone.utc)
        device = existing
    else:
        device = Device(
            user_id=user.id,
            fcm_token=body.fcm_token,
            platform=body.platform,
            app_version=body.app_version,
            device_model=body.device_model,
            os_version=body.os_version,
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(device)

    db.commit()
    db.refresh(device)
    logger.info("Device registered", extra={"user_id": user.id, "device_id": device.id})
    return APIResponse(data={"device_id": device.id, "platform": device.platform})


@router.delete("/{token}", summary="注销推送 token")
async def unregister_device(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    device = db.scalar(select(Device).where(Device.fcm_token == token))
    if not device:
        raise NotFoundError("设备不存在")
    if device.user_id != user.id:
        raise NotFoundError("设备不属于当前用户")
    db.delete(device)
    db.commit()
    return APIResponse(data={"token": token, "deleted": True})
