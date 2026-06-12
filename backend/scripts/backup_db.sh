#!/bin/sh
# ============================================================
#  HomeMatch DB 备份脚本（[Sprint2-#11]）
# ============================================================
#
# 流程：
#   1. pg_dump → 压缩 → 本地存 7 天
#   2. 上传到 OSS / S3（保留 30 天）
#   3. 退出时打印备份大小 + 耗时
#
# 用法（生产 cron 每天 03:00 跑一次）：
#   0 3 * * * /app/scripts/backup_db.sh >> /var/log/backup.log 2>&1
#
# 环境变量：
#   DATABASE_URL        postgresql://user:pass@host:port/db
#   BACKUP_LOCAL_DIR    本地备份目录（默认 /var/backups/homematch）
#   BACKUP_REMOTE_BUCKET  OSS bucket 名（不设就不上送）
#   BACKUP_RETENTION_DAYS  本地保留天数（默认 7）
#   BACKUP_REMOTE_PREFIX   OSS 上的 key 前缀（默认 backups/db/）

set -eu

# === 解析 DATABASE_URL ===
DB_URL="${DATABASE_URL:-}"
if [ -z "$DB_URL" ]; then
    echo "ERROR: DATABASE_URL not set"
    exit 1
fi

# postgresql://user:pass@host:port/db → 拆 5 段
DB_USER=$(echo "$DB_URL" | sed -n 's|postgresql://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DB_URL" | sed -n 's|postgresql://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

if [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ]; then
    echo "ERROR: cannot parse DATABASE_URL: $DB_URL"
    exit 1
fi

LOCAL_DIR="${BACKUP_LOCAL_DIR:-/var/backups/homematch}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="homematch_${DB_NAME}_${TIMESTAMP}.sql.gz"
LOCAL_PATH="${LOCAL_DIR}/${FILENAME}"

mkdir -p "$LOCAL_DIR"

START=$(date +%s)
echo "[$(date +%H:%M:%S)] Starting backup → $FILENAME"

# === 1. pg_dump（远程）===
PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    --format=plain \
    | gzip -9 > "$LOCAL_PATH"

DUMP_SIZE=$(du -h "$LOCAL_PATH" | cut -f1)
ELAPSED=$(( $(date +%s) - START ))
echo "[$(date +%H:%M:%S)] Dump done: $DUMP_SIZE in ${ELAPSED}s"

# === 2. 验证备份（解压一行看是否能 parse）===
if ! gunzip -c "$LOCAL_PATH" | head -1 | grep -q "PostgreSQL database dump"; then
    echo "ERROR: backup file corrupted (no PostgreSQL header)"
    exit 1
fi

# === 3. 上传到 OSS（如果有配）===
if [ -n "${BACKUP_REMOTE_BUCKET:-}" ] && [ -n "${ALIYUN_AK:-}" ]; then
    REMOTE_KEY="${BACKUP_REMOTE_PREFIX:-backups/db/}${FILENAME}"
    echo "[$(date +%H:%M:%S)] Uploading to oss://${BACKUP_REMOTE_BUCKET}/${REMOTE_KEY}"

    # 用 ossutil（推荐） / oss2 CLI；ops 按需装
    if command -v ossutil >/dev/null 2>&1; then
        ossutil cp "$LOCAL_PATH" "oss://${BACKUP_REMOTE_BUCKET}/${REMOTE_KEY}"
    else
        echo "WARN: ossutil not installed, skip remote upload"
    fi
fi

# === 4. 清理旧备份（本地）===
DELETED=$(find "$LOCAL_DIR" -name "homematch_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete -print | wc -l)
echo "[$(date +%H:%M:%S)] Cleaned $DELETED old backups (>$RETENTION_DAYS days)"

echo "[$(date +%H:%M:%S)] Backup OK: $LOCAL_PATH ($DUMP_SIZE)"
