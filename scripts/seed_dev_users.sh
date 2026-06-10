#!/bin/bash
# HomeMatch dev users seed 脚本
# 用法：./scripts/seed_dev_users.sh [--wipe]
# 效果：保证 6 个稳定 dev code 永远存在（见 docs/05-dev-users.md）
#       --wipe 会先清掉所有 mock user（⚠️ cascade 删 properties/demands/...）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "🛠  HomeMatch dev users seed"
cd "$BACKEND_DIR" || { echo "❌ backend 目录不存在: $BACKEND_DIR"; exit 1; }
source .venv/bin/activate || { echo "❌ venv 激活失败"; exit 1; }

python -m scripts.seed_dev_users "$@"
