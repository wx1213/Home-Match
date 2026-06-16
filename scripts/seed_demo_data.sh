#!/bin/bash
# HomeMatch demo 数据 seed（5 经纪人 + 50 房源 + 50 需求 + 50 合作）
# 用法：./scripts/seed_demo_data.sh [--wipe] [--seed 42]
# 效果：幂等创建 demo_agent_01~05 + 各 10 条 property/demand + 50 条 cooperation

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "🛠  HomeMatch demo 数据 seed"
cd "$BACKEND_DIR" || { echo "❌ backend 目录不存在: $BACKEND_DIR"; exit 1; }
source .venv/bin/activate || { echo "❌ venv 激活失败"; exit 1; }

python -m scripts.seed_demo_data "$@"
