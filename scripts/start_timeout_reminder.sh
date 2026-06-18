#!/bin/bash
# HomeMatch 推送超时提醒调度器启动脚本（C3）
# 用法：./scripts/start_timeout_reminder.sh
# 效果：杀掉旧的 scheduler → 启动 timeout_reminder_scheduler → 写 PID 文件 → 后台跑
# 扫描间隔：60s，邀请 <2h 提醒 / 方案 <30min 提醒

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/Users/wangxiao/WorkSpace/RD"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_FILE="/tmp/timeout_reminder.log"
PID_FILE="/tmp/timeout_reminder.pid"

echo -e "${YELLOW}⏰ HomeMatch 推送超时提醒调度器启动${NC}"

# 1. 杀旧 scheduler
if pgrep -f "timeout_reminder_scheduler" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  旧 scheduler 在跑，先 kill${NC}"
    pkill -f "timeout_reminder_scheduler" 2>/dev/null
    sleep 1
fi

# 2. 启动
cd "$BACKEND_DIR" || { echo -e "${RED}❌ backend 目录不存在${NC}"; exit 1; }
source .venv/bin/activate || { echo -e "${RED}❌ venv 激活失败${NC}"; exit 1; }

nohup python -m scripts.timeout_reminder_scheduler > "$LOG_FILE" 2>&1 &
SCH_PID=$!
echo $SCH_PID > "$PID_FILE"
disown

# 3. 验证
sleep 2
if pgrep -f "timeout_reminder_scheduler" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 调度器启动成功${NC}"
    echo -e "   PID: $SCH_PID"
    echo -e "   日志: $LOG_FILE"
    echo -e "   停止: ./scripts/stop_timeout_reminder.sh"
    echo -e "   立即跑一轮: cd backend && source .venv/bin/activate && python -m scripts.timeout_reminder_scheduler --once"
else
    echo -e "${RED}❌ 启动失败${NC}"
    tail -20 "$LOG_FILE"
    exit 1
fi
