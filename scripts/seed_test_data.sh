#!/bin/bash
# HomeMatch 标准化测试数据 seed 脚本
# 用法：./scripts/seed_test_data.sh [--wipe] [--seed 42]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "🛠  HomeMatch 标准化测试数据 seed"
cd "$BACKEND_DIR" || { echo "❌ backend 目录不存在: $BACKEND_DIR"; exit 1; }
source .venv/bin/activate || { echo "❌ venv 激活失败"; exit 1; }

python -m scripts.seed_test_data "$@"
