# ============================================================
#  HomeMatch Backend Dockerfile (Sprint2-#9)
# ============================================================
#
# 多阶段 build：
#   - builder: 装编译依赖 + 装包（用 uv，比 pip 快 10x）
#   - runtime: slim 镜像 + 非 root 用户 + 仅运行时依赖
#
# 镜像大小目标：~200MB
# 启动时间目标：< 5s
#
# 配套：
#   - 镜像 ENTRYPOINT 启动 uvicorn（prod 模式）
#   - 配套脚本 /scripts/entrypoint.sh 负责等 PG/Redis + 跑 alembic upgrade
#   - 部署到生产时配合 docker-compose.prod.yml + nginx + 外部 PG/Redis
#
# 本地构建：
#   docker build -t homematch-backend:latest backend/
#
# 生产 build（用 GitHub Actions 注入版本号）：
#   docker build -t homematch-backend:1.0.0 \
#     --build-arg VERSION=1.0.0 --build-arg GIT_SHA=$(git rev-parse HEAD) \
#     backend/

# ============================================================
#  Stage 1: builder
# ============================================================
FROM python:3.11-slim AS builder

# 装编译工具（uv 推荐用 pip install，比 curl 下载二进制更可控）
RUN pip install --no-cache-dir uv==0.4.18

# uv 虚拟环境建到 /app/.venv（runtime 镜像复用）
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# 1. 先 copy 依赖文件（lockfile）—— 利用 Docker 缓存
COPY pyproject.toml uv.lock* ./

# 2. 装运行时依赖到 .venv（不要 dev 依赖，减小镜像）
RUN uv sync --no-dev --frozen 2>/dev/null || \
    uv sync --no-dev  # fallback if uv.lock missing

# 3. 再 copy 源码
COPY . /app

# ============================================================
#  Stage 2: runtime
# ============================================================
FROM python:3.11-slim AS runtime

# 镜像 metadata（生产排障用）
ARG VERSION=0.0.0
ARG GIT_SHA=unknown
ENV APP_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    # 生产默认值
    APP_ENV=production \
    APP_DEBUG=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# 装运行时系统依赖（pillow 需要 libjpeg；cryptography 需要 libssl）
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 健康检查
    curl \
    # 镜像处理
    libjpeg62-turbo \
    zlib1g \
    # 加密库
    libssl3 \
    # 字体（pillow 处理中文/emoji）— MVP 暂不装，按需加 fonts-noto-cjk
    && rm -rf /var/lib/apt/lists/*

# 非 root 用户（k8s/dokku 强制要求）
RUN groupadd --system --gid 1001 app && \
    useradd --system --uid 1001 --gid app --no-create-home --shell /bin/bash app

WORKDIR /app

# 从 builder 拷 .venv（包含全部 Python 依赖）
COPY --from=builder /app/.venv /app/.venv
# 拷源码
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/scripts /app/scripts

# 写入版本号到镜像（让 /healthz 能返）
RUN echo "${VERSION} (${GIT_SHA})" > /app/VERSION

# 暴露上传目录（持久化建议挂到 host / 云盘）
RUN mkdir -p /app/uploads && chown -R app:app /app
USER app

# 健康检查（用 curl；不依赖业务代码）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${APP_PORT:-8000}/healthz || exit 1

EXPOSE 8000

# 启动入口（entrypoint.sh 等 PG/Redis + 跑 alembic + 启 uvicorn）
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
