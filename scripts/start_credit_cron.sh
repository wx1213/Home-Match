#!/bin/bash
# HomeMatch 信用分每日调度器启动脚本
# 用法：./scripts/start_credit_cron.sh
# 效果：杀掉旧的 scheduler → 启动 credit_score_scheduler → 写 PID 文件 → 后台跑
# 调度时间：每日 0:00 (local) 调 recompute_all_credit_scores_task

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/Users/wangxiao/WorkSpace/RD"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_FILE="/tmp/credit_score_cron.log"
PID_FILE="/tmp/credit_score_cron.pid"

echo -e "${YELLOW}⏰ HomeMatch 信用分调度器启动${NC}"

# 1. 杀旧 scheduler
if pgrep -f "credit_score_scheduler" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  旧 scheduler 在跑，先 kill${NC}"
    pkill -f "credit_score_scheduler" 2>/dev/null
    sleep 1
fi

# 2. 启动
cd "$BACKEND_DIR" || { echo -e "${RED}❌ backend 目录不存在${NC}"; exit 1; }
source .venv/bin/activate || { echo -e "${RED}❌ venv 激活失败${NC}"; exit 1; }

nohup python -m scripts.credit_score_scheduler > "$LOG_FILE" 2>&1 &
CRON_PID=$!
echo $CRON_PID > "$PID_FILE"
disown

# 3. 验证
sleep 2
if pgrep -f "credit_score_scheduler" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 调度器启动成功${NC}"
    echo -e "   PID: $CRON_PID"
    echo -e "   日志: $LOG_FILE"
    echo -e "   停止: ./scripts/stop_credit_cron.sh"
    echo -e "   立即跑: cd backend && source .venv/bin/activate && python -m scripts.recompute_credit_scores"
else
    echo -e "${RED}❌ 启动失败${NC}"
    tail -20 "$LOG_FILE"
    exit 1
fi
