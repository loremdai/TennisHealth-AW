# TennisHealth-AW

Professional Physiological & Tactical Tennis Analysis System.

## Features
- **Health Data Integration**: Automatically processes Apple Watch workout exports.
- **AI Coaching**: Uses DeepSeek Reasoner for professional tactical reports.
- **Incremental Detection**: UUID-based tracking to avoid duplicate reports.
- **Interactive Mode**: Query match history and physiological stats via LLM.

## Setup
1. Export health data to iCloud via HealthExport.
2. Configure `tennis_health_monitor.py` with your paths.
3. Set `DEEPSEEK_API_KEY` in your environment.
4. Run the monitor as a background service (LaunchAgent included).

---
*Developed for NTRP 4.0 -> 4.5 progression.*
