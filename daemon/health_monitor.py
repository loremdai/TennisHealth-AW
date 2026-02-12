#!/usr/bin/env python3
"""
Tennis Health Monitor Daemon
============================

Apple Watch 网球运动数据的自动化监听与推送守护进程。

本模块仅负责两件事:
    1. 监听 iCloud 目录中 Health Auto Export JSON 文件的变化
    2. 将 AI 分析结果通过 OpenClaw CLI 推送至指定联系人

数据筛选/去重 和 AI 分析 的业务逻辑分别由 tools/ 下的模块提供:
    - tools.workout_filter: JSON 读取、网球记录筛选、UUID 去重
    - tools.ai_analyzer:    DeepSeek 单场战术分析 + 多场体能复盘

用法:
    python daemon/health_monitor.py

环境变量:
    DEEPSEEK_API_KEY  DeepSeek API 密钥
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ---------------------------------------------------------------------------
# Path Setup
# ---------------------------------------------------------------------------

# 项目根目录 (daemon/ 的上一级)
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent

# 将项目根目录加入 sys.path, 以便 import tools.*
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.workout_filter import (  # noqa: E402
    WorkoutStateTracker,
    filter_tennis_workouts,
    read_json_file,
)
from tools.ai_analyzer import TennisAIAnalyzer  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Health Auto Export 的 iCloud 导出目录
ICLOUD_DIR = Path(
    "/Users/daibin/Library/Mobile Documents/"
    "iCloud~com~ifunography~HealthExport/Documents/iCloud 自动化"
)

# 最近一场比赛的缓存文件 (供 Skill 读取)
CONTEXT_DIR = PROJECT_ROOT / "context"

# OpenClaw CLI 配置
OPENCLAW_BIN = (
    "/Users/daibin/.local/share/fnm/node-versions/v22.22.0/installation/bin/openclaw"
)
NODE_BIN = "/opt/homebrew/bin/node"
OPENCLAW_TARGET_ID = "1128305182"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("tennis_monitor")


# ---------------------------------------------------------------------------
# OpenClaw Push
# ---------------------------------------------------------------------------


def push_via_openclaw(message):
    """通过 OpenClaw CLI 推送消息。

    Args:
        message: 要推送的文本内容。

    Returns:
        推送成功返回 True, 否则 False。
    """
    cmd = [
        NODE_BIN,
        OPENCLAW_BIN,
        "message",
        "send",
        "--target",
        OPENCLAW_TARGET_ID,
        "--message",
        message,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error("OpenClaw CLI 错误: %s", result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("OpenClaw CLI 超时")
        return False


# ---------------------------------------------------------------------------
# File System Event Handler
# ---------------------------------------------------------------------------


class HealthFileHandler(FileSystemEventHandler):
    """监听 iCloud 目录中 Health Auto Export JSON 文件的变化。

    当检测到当天的 JSON 文件被修改时, 调用 tools/ 中的模块
    筛选新记录、执行 AI 分析, 然后通过 OpenClaw 推送结果。
    """

    def __init__(self, state_tracker):
        super().__init__()
        self.state = state_tracker
        self.ai = TennisAIAnalyzer()

    def on_modified(self, event):
        """响应文件修改事件, 仅处理当天的 JSON 文件。"""
        if event.is_directory or not event.src_path.endswith(".json"):
            return

        file_path = Path(event.src_path)
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in file_path.name:
            return

        logger.info("检测到健康数据文件更新: %s", file_path.name)
        time.sleep(2)  # 等待 iCloud 写入完成
        self._process(event.src_path)

    def _process(self, file_path):
        """处理单个 JSON 文件: 筛选 -> 分析 -> 推送。"""
        try:
            data = read_json_file(file_path)
            if not data:
                return

            all_tennis = filter_tennis_workouts(data)
            new_workouts = [
                w for w in all_tennis if not self.state.is_processed(w.get("id"))
            ]

            if not new_workouts:
                logger.info(
                    "未发现新的有效网球记录: %s",
                    Path(file_path).name,
                )
                return

            for workout in new_workouts:
                self._analyze_and_push(workout)

        except Exception as exc:
            logger.error("文件处理失败: %s", exc)

    def _analyze_and_push(self, workout):
        """对单条 workout 执行 AI 分析并推送结果。"""
        workout_id = workout.get("id", "unknown")
        try:
            report = self.ai.generate_match_analysis(workout)
            self._save_context(workout_id, workout, report)

            if push_via_openclaw(report):
                logger.info("推送成功: %s", workout_id)
                self.state.mark_processed(workout_id)
            else:
                logger.error("推送失败: %s", workout_id)

        except Exception as exc:
            logger.error("分析推送流程异常 (%s): %s", workout_id, exc)

    @staticmethod
    def _save_context(workout_id, workout, report):
        """将分析结果缓存到 context/latest_match.json。"""
        try:
            CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
            context_path = CONTEXT_DIR / "latest_match.json"
            with open(context_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "workout_id": workout_id,
                        "raw_workout": workout,
                        "ai_report": report,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main():
    """启动 Watchdog 文件监听守护进程。"""
    state = WorkoutStateTracker()
    handler = HealthFileHandler(state)
    observer = Observer()
    observer.schedule(handler, str(ICLOUD_DIR), recursive=False)
    observer.start()
    logger.info("守护进程已启动, 监听目录: %s", ICLOUD_DIR)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
