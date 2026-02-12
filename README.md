# TennisHealth-AW

Apple Watch 网球运动生理数据的自动化采集、分析与交互查询系统。

## 系统概述

本项目将 Apple Watch 的运动健康数据与 AI 分析能力相结合, 为网球爱好者提供两种使用模式:

1. **自动推送模式**: 后台守护进程监听 iCloud 新数据, 自动生成战术分析并推送至 OpenClaw (ClawdBot)。
2. **交互查询模式**: 通过 Skill 文件教会 LLM 客户端直接读取和分析 iCloud 中的原始数据, 支持灵活的对话式复盘。

### 球员画像

- 左手持拍, 单手反拍
- NTRP 4.0, 目标 4.5
- 以双打为主

## 数据链路

```
Apple Watch  -->  iPhone HealthKit  -->  Health Auto Export  -->  iCloud JSON
                  (蓝牙同步)              (自动导出)              (云盘存储)
                                                                     |
                                             +-----------------------+
                                             |                       |
                                        daemon/                 skills/
                                        (自动推送)              (交互查询)
                                             |                       |
                                        DeepSeek AI                客户端
                                             |                 (OpenClaw等)
                                        OpenClaw 推送
```

## 项目结构

```
TennisHealth-AW/
├── skills/                          # Skill 定义
│   └── tennis_health/
│       ├── skill.md                 # 数据查询与分析的完整 SOP
│       └── config.yaml              # 技能元数据 (名称、权限、标签)
├── tools/                           # 业务逻辑 (可被 daemon 和其他脚本复用)
│   ├── workout_filter.py            # JSON 读取、网球记录筛选、UUID 去重
│   └── ai_analyzer.py               # DeepSeek 单场战术分析 + 多场体能复盘
├── daemon/                          # 守护进程 (给 OpenClaw 使用)
│   └── health_monitor.py            # Watchdog 监听 + OpenClaw 推送
├── examples/                        # 示例数据
│   └── sample_workout.json          # 脱敏的 workout JSON 样例
├── context/                         
├── README.md
├── requirements.txt               
└── .gitignore                       # 运行时缓存 (gitignore)
```

## 环境要求

- Python 3.10+
- macOS (依赖 iCloud 同步和 TCC 兼容的 `cat` 回退机制)
- [Health Auto Export](https://apps.apple.com/app/health-auto-export/id1115567461) (iPhone App)

## 安装

```bash
cd /path/to/TennisHealth-AW
pip install -r requirements.txt
```

## 配置

### 环境变量

```bash
export DEEPSEEK_API_KEY="your_api_key_here"
```

### 路径配置

以下常量定义在 `daemon/health_monitor.py` 顶部, 需根据实际环境修改:

| 常量 | 说明 |
|---|---|
| `ICLOUD_DIR` | Health Auto Export 的 iCloud 导出目录 |
| `STATE_FILE` | 已处理记录的持久化状态路径 |
| `OPENCLAW_BIN` | OpenClaw CLI 二进制路径 |
| `NODE_BIN` | Node.js 二进制路径 |
| `OPENCLAW_TARGET_ID` | 推送目标 ID |

## 使用方式

### 1. 自动推送模式 (守护进程)

运行后台监控, 当 Apple Watch 记录新比赛并同步到 iCloud 后, 自动分析并推送:

```bash
python daemon/health_monitor.py
```

建议通过 macOS LaunchAgent 配置为开机自启动。

### 2. 交互查询模式 (LLM Skill)

`skills/tennis_health/skill.md` 包含了数据位置、JSON 结构、读取方式和分析场景的完整描述。LLM 客户端读取该文件后即可自主查询数据。

典型对话示例:
- "看看我 2026-02-08 打了几场球"
- "对比一下今天第一场和最后一场的心率曲线"
- "这周的训练量统计一下"
- "分析最近三场的心率恢复速度变化趋势"

## 在 OpenClaw (ClawdBot) 中使用

本项目与 [OpenClaw](https://github.com/nicepkg/openclaw) 深度集成, 实现"打完球自动收到分析报告"的闭环体验。

### 自动推送集成

守护进程在检测到新比赛后, 通过 OpenClaw CLI 推送 AI 分析报告:

```
Watchdog 检测新比赛 -> DeepSeek 生成战术分析 -> OpenClaw CLI 推送消息
```

推送内容包含:
- 体能与覆盖率评估
- 关键生理瓶颈与双打隐患
- 基于左手优势的双打战术调整建议

### 配置步骤

1. 安装 OpenClaw CLI:

```bash
npm install -g openclaw
```

2. 登录并获取目标 ID:

```bash
openclaw login
```

3. 修改 `daemon/health_monitor.py` 顶部的常量配置:

```python
OPENCLAW_BIN = "/path/to/openclaw"
NODE_BIN = "/path/to/node"
OPENCLAW_TARGET_ID = "your_target_id"
```

4. 启动守护进程:

```bash
python daemon/health_monitor.py
```

## 数据格式

Health Auto Export 导出的 JSON 文件的完整结构和字段说明见:
- `skills/tennis_health/skill.md` (字段说明表)
- `examples/sample_workout.json` (完整 JSON 样例)
