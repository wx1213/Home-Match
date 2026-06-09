from __future__ import annotations

"""结构化日志 - JSON 格式 + request_id/user_id 注入。"""

import logging
import sys
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

# Context vars for request-scoped logging
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[int | None] = ContextVar("user_id", default=None)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志输出。"""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 注入 request_id 和 user_id
        rid = request_id_ctx.get()
        if rid:
            log_data["request_id"] = rid
        uid = user_id_ctx.get()
        if uid:
            log_data["user_id"] = uid

        # 异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 额外字段（通过 extra= 传入）
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """配置全局日志。"""
    root = logging.getLogger()
    root.setLevel(settings.log_level)

    # 清除已有 handler
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root.addHandler(handler)

    # 第三方库日志降噪
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取 logger。"""
    return logging.getLogger(name)
