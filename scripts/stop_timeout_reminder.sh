#!/bin/bash
# 停止 HomeMatch 推送超时提醒调度器
set -e

PID_FILE="/tmp/timeout_reminder.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" >/dev/null 2>&1; then
        kill "$PID"
        echo "✅ 已停止 timeout_reminder_scheduler (PID=$PID)"
    else
        echo "⚠️  PID $PID 已不存在（可能已停止）"
    fi
    rm -f "$PID_FILE"
else
    echo "⚠️  PID 文件不存在，尝试 pkill"
    pkill -f "timeout_reminder_scheduler" 2>/dev/null || true
fi
