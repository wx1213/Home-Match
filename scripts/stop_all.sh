#!/bin/bash
# HomeMatch 全部进程停止脚本
# 用法：./scripts/stop_all.sh
# 效果：停后端 uvicorn + Flutter run + credit_score_scheduler

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛑 HomeMatch 全部进程停止${NC}"

# 1. uvicorn (8000 端口)
if lsof -i :8000 -t >/dev/null 2>&1; then
    echo -e "${YELLOW}▶ 停 uvicorn (8000)${NC}"
    lsof -i :8000 -t | xargs kill 2>/dev/null
    [ -f /tmp/uvicorn.pid ] && rm -f /tmp/uvicorn.pid
fi

# 2. flutter run
if pgrep -f "flutter run" >/dev/null 2>&1; then
    echo -e "${YELLOW}▶ 停 flutter run${NC}"
    pkill -f "flutter run" 2>/dev/null
    [ -f /tmp/flutter_run.pid ] && rm -f /tmp/flutter_run.pid
fi

# 3. credit_score_scheduler
if pgrep -f "credit_score_scheduler" >/dev/null 2>&1; then
    echo -e "${YELLOW}▶ 停 credit_score_scheduler${NC}"
    pkill -f "credit_score_scheduler" 2>/dev/null
    [ -f /tmp/credit_score_cron.pid ] && rm -f /tmp/credit_score_cron.pid
fi

# 4. dart backend server
if pgrep -f "dart development-service" >/dev/null 2>&1; then
    echo -e "${YELLOW}▶ 停 dart development-service${NC}"
    pkill -f "dart development-service" 2>/dev/null
fi

sleep 1
echo -e "${GREEN}✅ 全部进程已停止${NC}"
