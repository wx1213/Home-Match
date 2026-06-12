#!/bin/sh
# ============================================================
#  HomeMatch Backend Container Entrypoint (Sprint2-#9 + #10)
# ============================================================
#
# 启动流程：
#   1. 等待 PostgreSQL 可用（按 DATABASE_URL 解析 host:port）
#   2. 等待 Redis 可用
#   3. 跑 alembic upgrade head（同步 schema）
#   4. exec CMD（默认启 uvicorn）
#
# 设计：
#   - 全部检查都有超时（避免容器卡住）
#   - 失败时 exit 1 → k8s/dokku 自动重启 + 报警
#   - 日志输出到 stdout → 容器日志收集

set -eu

log() {
    echo "[entrypoint $(date +%H:%M:%S)] $*" >&2
}

# === 1. 解析 DATABASE_URL ===
# DATABASE_URL=postgresql://user:pass@host:port/db
DB_HOST=$(echo "${DATABASE_URL:-}" | sed -n 's|.*@\(.*\):\(.*\)/.*|\1|p')
DB_PORT=$(echo "${DATABASE_URL:-}" | sed -n 's|.*@\(.*\):\(.*\)/.*|\2|p')

if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ]; then
    log "WARN: cannot parse DATABASE_URL, skip PG wait: ${DATABASE_URL:-<empty>}"
else
    log "Waiting for PostgreSQL at $DB_HOST:$DB_PORT (max 60s)..."
    i=0
    while [ $i -lt 60 ]; do
        if nc -z -w 2 "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            log "PG ready"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ $i -ge 60 ]; then
        log "ERROR: PG not ready after 60s, exit"
        exit 1
    fi
fi

# === 2. 解析 REDIS_URL ===
REDIS_HOST=$(echo "${REDIS_URL:-}" | sed -n 's|redis://\(.*\):\(.*\)/.*|\1|p')
REDIS_PORT=$(echo "${REDIS_URL:-}" | sed -n 's|redis://\(.*\):\(.*\)/.*|\2|p')

if [ -z "$REDIS_HOST" ] || [ -z "$REDIS_PORT" ]; then
    log "WARN: cannot parse REDIS_URL, skip Redis wait: ${REDIS_URL:-<empty>}"
else
    log "Waiting for Redis at $REDIS_HOST:$REDIS_PORT (max 30s)..."
    i=0
    while [ $i -lt 30 ]; do
        if nc -z -w 2 "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
            log "Redis ready"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ $i -ge 30 ]; then
        log "ERROR: Redis not ready after 30s, exit"
        exit 1
    fi
fi

# === 3. alembic upgrade head ===
if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    log "Running alembic upgrade head..."
    if ! alembic upgrade head; then
        log "ERROR: alembic upgrade failed"
        exit 1
    fi
    log "alembic upgrade done"
else
    log "SKIP_MIGRATIONS=true, skip alembic"
fi

# === 4. exec CMD ===
log "Starting: $*"
exec "$@"
