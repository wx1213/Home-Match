# HomeMatch 生产运维脚本（[Sprint2-#11]）

## 目录

| 脚本 | 用途 | 调用频率 |
|---|---|---|
| `entrypoint.sh` | 容器启动入口：等 PG/Redis + alembic upgrade + 启 uvicorn | 容器启动时 1 次 |
| `backup_db.sh` | PostgreSQL 备份：dump + 压缩 + 上传 OSS + 本地保留 7 天 | 每天 03:00 (cron) |
| `credit_score_scheduler.py` | 信用分每日 0 点调度器（已有） | 每天 00:00 |
| `seed_dev_users.sh` | 6 个稳定 dev user（已有） | 按需 |
| `seed_test_data.sh` | 100 房源 + 60 需求 seed（已有） | 按需 |

## 生产 cron 建议

```bash
# /etc/cron.d/homematch
# 信用分每天 0 点
0 0 * * * app /app/scripts/run_credit_score.sh >> /var/log/credit.log 2>&1

# DB 备份每天 3 点
0 3 * * * app /app/scripts/backup_db.sh >> /var/log/backup.log 2>&1

# Redis 备份（4 点；AOF 已在 docker-compose.yml 开启）
0 4 * * * app redis-cli BGSAVE && cp /var/lib/redis/dump.rdb /var/backups/redis/
```

## DB 备份恢复

```bash
# 1. 下载备份
ossutil cp oss://hmatch-prod/backups/db/homematch_homa_20260612_030000.sql.gz .

# 2. 解压
gunzip homematch_homa_20260612_030000.sql.gz

# 3. 恢复（要先 drop 现有库！否则会冲突）
psql -U homa -d postgres -c "DROP DATABASE homa;"
psql -U homa -d postgres -c "CREATE DATABASE homa;"
psql -U homa -d homa < homematch_homa_20260612_030000.sql

# 4. 验证
psql -U homa -d homa -c "SELECT count(*) FROM users;"
```

## Redis 持久化

- 开启 AOF（`--appendonly yes`，docker-compose.yml 已配）
- maxmemory 256MB + LRU 淘汰（`--maxmemory-policy allkeys-lru`）
- 每天 4 点 BGSAVE 备份到 /var/backups/redis/

## 容器健康探针

| 端点 | 用途 | k8s 配置 |
|---|---|---|
| `/healthz` | Liveness：永远 200 | `livenessProbe.httpGet.path=/healthz` |
| `/readyz` | Readiness：检查 PG + Redis | `readinessProbe.httpGet.path=/readyz` |
| `/v1/health` | 详细健康 + 依赖状态 | 监控用 |

## Sentry

- 后端：错误 + 性能追踪 + 自动检测 N+1 SQL
- DSN：环境变量 `SENTRY_DSN`
- dev 模式自动不上送（避免污染 dashboard）
