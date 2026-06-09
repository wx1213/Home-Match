#!/bin/bash
# HomeMatch 后端启动脚本
# 用法：./scripts/start_backend.sh
# 效果：杀掉旧的 8000 端口进程 → 启动 uvicorn → 写 PID 文件 → 后台跑

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/Users/wangxiao/WorkSpace/RD"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_FILE="/tmp/uvicorn.log"
PID_FILE="/tmp/uvicorn.pid"
PORT=8000

echo -e "${YELLOW}🔧 HomeMatch 后端启动${NC}"

# 1. 检查端口
if lsof -i :$PORT -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  端口 $PORT 已被占用，kill 旧进程${NC}"
    lsof -i :$PORT -t | xargs kill 2>/dev/null
    sleep 2
fi

# 2. 启动 uvicorn
cd "$BACKEND_DIR" || { echo -e "${RED}❌ backend 目录不存在${NC}"; exit 1; }
source .venv/bin/activate || { echo -e "${RED}❌ venv 激活失败${NC}"; exit 1; }

echo -e "${YELLOW}▶ 启动 uvicorn (port=$PORT)${NC}"
nohup uvicorn app.main:app --host 0.0.0.0 --port $PORT > "$LOG_FILE" 2>&1 &
UVICORN_PID=$!
echo $UVICORN_PID > "$PID_FILE"
disown

# 3. 等待启动
sleep 3
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/v1/health | grep -q "200"; then
    echo -e "${GREEN}✅ 后端启动成功${NC}"
    echo -e "   PID: $UVICORN_PID"
    echo -e "   日志: $LOG_FILE"
    echo -e "   健康: curl http://localhost:$PORT/v1/health"
else
    echo -e "${RED}❌ 后端启动失败，查看日志: $LOG_FILE${NC}"
    tail -20 "$LOG_FILE"
    exit 1
fi
