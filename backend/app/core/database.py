"""SQLAlchemy 2.0 数据库连接 - 同步引擎（MVP 阶段）。"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """所有 ORM model 的基类。"""


def _create_engine() -> Engine:
    """根据 URL 构造 engine（SQLite 跳过 pool 参数）。"""
    url = settings.database_url
    if url.startswith("sqlite"):
        # SQLite：单文件/内存模式，连接池参数不适用
        return create_engine(
            url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False},
        )
    # PG / MySQL 等：使用连接池
    return create_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.database_echo,
    )


engine: Engine = _create_engine()

# Session 工厂
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：获取数据库 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """非请求场景使用的 session context manager。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """健康检查：数据库是否连通。"""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection check failed", extra={"error": str(e)})
        return False
