"""
Workout Filter & State Tracker

从 Health Auto Export 的 JSON 文件中筛选有效网球记录, 并通过 UUID 去重。

功能:
    - 读取 iCloud 目录下的 JSON 文件 (带 TCC cat 回退)
    - 按条件筛选有效网球记录 (名称含 "网球", 时长 > 3 分钟)
    - 持久化已处理的 workout ID, 防止重复分析
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("tennis_monitor")

# 有效网球记录的最低时长 (秒), 3 分钟
MIN_DURATION_SECONDS = 180

# 已处理记录 ID 列表的最大长度, 超出后截断最旧的
MAX_PROCESSED_IDS = 200

# 状态持久化路径
STATE_FILE = Path("/Users/daibin/.openclaw/tennis_health_analyzer_state.json")


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def read_json_file(file_path):
    """读取 JSON 文件, 带有 cat 命令回退机制。

    macOS 的 TCC 权限策略可能导致 Python 直接读取 iCloud 目录失败,
    此时回退到 subprocess.run(["cat", ...]) 方式绕过限制。

    Args:
        file_path: JSON 文件路径 (str 或 Path)。

    Returns:
        解析后的 dict, 失败时返回 None。
    """
    file_path = str(file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (PermissionError, IOError, json.JSONDecodeError) as exc:
        logger.warning("标准读取失败 (%s), 尝试 cat 回退: %s", file_path, exc)
        try:
            result = subprocess.run(
                ["cat", file_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as inner:
            logger.error("cat 回退也失败: %s", inner)
        return None


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def filter_tennis_workouts(data):
    """从 Health Auto Export 数据中筛选有效的网球运动记录。

    筛选条件:
        1. workout 名称包含 "网球"
        2. 时长 > MIN_DURATION_SECONDS (180s)

    Args:
        data: Health Auto Export 导出的完整 JSON dict。

    Returns:
        按开始时间正序排列的网球 workout 列表。
    """
    workouts = data.get("data", {}).get("workouts", [])
    tennis = [
        w
        for w in workouts
        if "网球" in w.get("name", "") and w.get("duration", 0) > MIN_DURATION_SECONDS
    ]
    tennis.sort(key=lambda x: x.get("start", ""))
    return tennis


# ---------------------------------------------------------------------------
# State Tracker (UUID Dedup)
# ---------------------------------------------------------------------------


class WorkoutStateTracker:
    """基于 UUID 的 workout 去重状态管理。

    通过持久化已处理的 workout ID 列表到本地 JSON 文件,
    防止同一场比赛被重复分析和推送。列表超过 MAX_PROCESSED_IDS
    条时自动截断最旧的记录。
    """

    def __init__(self):
        self.processed_ids = []
        self._load()

    def _load(self):
        """从磁盘加载已处理 ID 列表。"""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    self.processed_ids = state.get(
                        "processed_workout_ids",
                        [],
                    )
        except Exception:
            pass

    def _save(self):
        """将已处理 ID 列表持久化到磁盘。"""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(
                    {"processed_workout_ids": self.processed_ids},
                    f,
                )
        except Exception:
            pass

    def is_processed(self, workout_id):
        """检查 workout ID 是否已处理过。"""
        return workout_id in self.processed_ids

    def mark_processed(self, workout_id):
        """标记 workout ID 为已处理并持久化。"""
        if workout_id not in self.processed_ids:
            self.processed_ids.append(workout_id)
            if len(self.processed_ids) > MAX_PROCESSED_IDS:
                self.processed_ids = self.processed_ids[-MAX_PROCESSED_IDS:]
            self._save()
