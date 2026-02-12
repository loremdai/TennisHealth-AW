"""
Tennis AI Analyzer

基于 LLM 的网球运动 AI 分析模块。

功能:
    - 单场双打战术分析: 体能评估 + 瓶颈分析 + 战术建议 (250 字)
    - 多场体能衰减复盘: 数据结算 + 衰减趋势 + 表现特征 (300 字)
"""

import json
import logging
import os

logger = logging.getLogger("tennis_monitor")


class TennisAIAnalyzer:
    """LLM 封装, 提供单场战术分析和多场体能复盘。

    单场分析:
        面向左手持拍、单反、NTRP 4.0 的双打选手, 生成 250 字以内的
        体能评估 + 瓶颈分析 + 战术建议。

    多场复盘:
        对同一天内多场比赛进行体能衰减模型分析, 输出 300 字以内的
        数据结算 + 衰减趋势 + 表现特征总结 (不含建议)。
    """

    def __init__(self):
        try:
            from openai import OpenAI

            self.client = OpenAI(
                base_url="https://api.deepseek.com",
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            )
            self.model_name = "deepseek-reasoner"
            self.available = True
        except ImportError:
            self.available = False

    def generate_match_analysis(self, workout_data):
        """生成单场双打战术分析报告。

        Args:
            workout_data: 单条 workout 的原始 JSON dict。

        Returns:
            AI 生成的分析文本, 失败时返回错误提示。
        """
        if not self.available:
            return "分析服务不可用 (缺少 openai 库)。"

        system_prompt = (
            "你是一位专业且务实的网球双打战术教练。"
            "你对左手持拍、单反球员的特质有深刻理解。"
            "请基于客观的生理数据, 为我制定高效的双打比赛策略。"
        )

        user_prompt = f"""# Player Profile
- **Handedness**: 左手持拍 (Left-handed)
- **Backhand**: 单手反拍 (One-handed backhand)
- **Level**: NTRP 4.0
- **Context**: 这是一场双打比赛 (Doubles Match)。

# Style Guidelines
- **语言风格**: 平实、直接、客观。
- **核心要求**: 重点分析双打特有的网前配合、左手发球优势及战术布局。拒绝废话, 直指本质。
- **篇幅限制**: 全文字数控制在 250 字以内。

# Task
第一步: 数据有效性检查
如果 `duration`(时长) < 10 分钟 或 `avgHeartRate`(平均心率) < 70 bpm, 请直接输出: "**数据无效: 时长过短或强度不足, 无法进行双打战术分析。**" 并结束回答。如果数据有效, 请不要输出任何确认信息, 直接跳至第二步。

第二步: 双打战术分析
请跳过数据罗列, 直接输出以下 3 点:
1. **体能与覆盖率评估**:
   * 结合数据评估在双打快节奏下的体能储备和场上覆盖积极性。
2. **关键生理瓶颈与双打隐患**:
   * 指出最影响双打表现(如网前反应、移动切换)的具体问题。
3. **双打战术调整建议**:
   * 基于左手优势和体能现状, 提供具体的双打打法(如 I-Formation、中路封锁、斜线切削压制)。

# Data (JSON)
{json.dumps(workout_data, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("DeepSeek 单场分析失败: %s", exc)
            return "AI 分析生成失败。"

    def generate_period_analysis(self, workouts, date_str):
        """生成多场体能衰减复盘报告。

        Args:
            workouts: 多条 workout 的 dict 列表。
            date_str: 日期字符串 (YYYY-MM-DD), 用于报告标题。

        Returns:
            AI 生成的复盘文本, 失败时返回错误提示。
        """
        if not self.available:
            return "分析服务不可用 (缺少 openai 库)。"

        prompt = f"""你是一位职业网球体能分析师。请对以下在 {date_str} 完成的 {len(workouts)} 场网球运动进行赛后生理复盘与数据总结。

# 要求:
1. **全天数据结算**: 统计累计时长、总消耗卡路里、全天平均心率、全天峰值心率。
2. **体能衰减模型分析**: 对比第一场与最后一场的关键指标变化。重点分析心率/步频比的变化趋势, 以此论证疲劳对移动能力的具体影响。
3. **表现特征总结**: 客观总结今天这几场比赛呈现出的生理特征(例如: 高心率耐受型、晚期爆发型等)。
4. **拒绝任何建议**: 不要给出"建议下次如何打"之类的话语, 只针对已经发生的数据进行深度归纳。
5. **字数限制**: 300 字以内, 平实、严谨。

# 原始数据 (JSON):
{json.dumps(workouts, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专注于数据复盘的职业网球体能分析师。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("DeepSeek 周期复盘失败: %s", exc)
            return "汇总分析生成失败。"
