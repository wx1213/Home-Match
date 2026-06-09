#!/bin/bash
# HomeMatch Flutter APP 启动脚本
# 用法：./scripts/start_flutter.sh
# 效果：杀掉旧的 flutter run → 启动 flutter run → 写 PID 文件 → 后台跑

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/Users/wangxiao/WorkSpace/RD"
MOBILE_DIR="$PROJECT_DIR/mobile-app"
DEVICE_ID="179C75B4-1813-4A95-ABAB-E67ADF2435A8"   # iPhone 17 Pro (booted)
LOG_FILE="/tmp/flutter_run.log"
PID_FILE="/tmp/flutter_run.pid"

echo -e "${YELLOW}🚀 HomeMatch Flutter APP 启动${NC}"

# 1. 杀旧 flutter run
if pgrep -f "flutter run.*$DEVICE_ID" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  旧的 flutter run 在跑，先 kill${NC}"
    pkill -f "flutter run.*$DEVICE_ID" 2>/dev/null
    sleep 2
fi

# 2. 确认 simulator booted
if ! xcrun simctl list devices booted | grep -q "$DEVICE_ID"; then
    echo -e "${RED}❌ Simulator $DEVICE_ID 未 boot${NC}"
    exit 1
fi

# 3. 启动 flutter run
cd "$MOBILE_DIR" || { echo -e "${RED}❌ mobile-app 目录不存在${NC}"; exit 1; }
export PATH="/opt/homebrew/flutter/bin:$PATH"

echo -e "${YELLOW}▶ 启动 flutter run (device=$DEVICE_ID)${NC}"
nohup flutter run -d "$DEVICE_ID" --no-pub > "$LOG_FILE" 2>&1 &
FLUTTER_PID=$!
echo $FLUTTER_PID > "$PID_FILE"
disown

# 4. 等待编译 + 截图
sleep 30
if pgrep -f "flutter run.*$DEVICE_ID" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Flutter run 启动成功${NC}"
    echo -e "   PID: $FLUTTER_PID"
    echo -e "   日志: $LOG_FILE"
    echo -e "   截图: xcrun simctl io booted screenshot /tmp/hm.png"
else
    echo -e "${RED}❌ Flutter run 启动失败，查看日志: $LOG_FILE${NC}"
    tail -30 "$LOG_FILE"
    exit 1
fi
