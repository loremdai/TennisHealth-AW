"""
Tennis AI Analyzer

基于 LLM 的网球运动 AI 分析模块。

功能:
    - 单场分析: 强度评估 + 移动效率 + 能量分布 + 恢复 + 战术建议
    - 多场复盘: 数据结算 + 衰减趋势 + 恢复对比 + 表现特征
"""

import json
import logging
import os

logger = logging.getLogger("tennis_monitor")


class TennisAIAnalyzer:
    """LLM 封装, 提供单场战术分析和多场体能复盘。

    单场分析:
        面向左手持拍、单反、NTRP 4.0 的选手, 从 7 个维度进行分析:
        运动强度、心率分区、移动效率、能量分布、心肺恢复、
        运动经济性、战术建议。不预设单打或双打。

    多场复盘:
        对同一天内多场比赛进行体能衰减模型分析, 涵盖:
        数据结算、跨场衰减、能量分配、恢复对比、TRIMP 负荷、
        表现特征总结 (不含建议)。
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
        """生成单场战术分析报告。

        Args:
            workout_data: 单条 workout 的原始 JSON dict。

        Returns:
            AI 生成的分析文本, 失败时返回错误提示。
        """
        if not self.available:
            return "分析服务不可用 (缺少 openai 库)。"

        system_prompt = (
            "你是一位专业且务实的网球战术教练。"
            "你对左手持拍、单反球员的特质有深刻理解。"
            "你必须充分利用所有可用的生理数据维度进行分析, "
            "每个观点必须引用具体数值作为论据。"
        )

        user_prompt = f"""# Player Profile
- **Handedness**: 左手持拍 (Left-handed)
- **Backhand**: 单手反拍 (One-handed backhand)
- **Level**: NTRP 4.0

# Available Data Fields
以下是 JSON 中所有可用的数据维度, 你必须在分析中尽可能多地利用:

**汇总指标**:
- `duration`: 总时长 (秒)
- `avgHeartRate` / `maxHeartRate`: 平均/峰值心率 (bpm)
- `heartRate.min`: 最低心率 (bpm), 可与 max 一起计算心率动态范围
- `activeEnergyBurned`: 总活跃能量消耗 (kJ, 1 kcal = 4.184 kJ)
- `distance`: 总移动距离 (km)
- `speed`: 平均移动速度 (km/hr)
- `stepCadence`: 平均步频 SPM (count/min)

**时序数据** (逐分钟采样, 是最有分析价值的部分):
- `heartRateData[]`: 逐分钟心率 (Avg/Min/Max), 用于心率区间分布、漂移趋势、高强度占比
- `stepCount[]`: 逐分钟步数, 即每分钟步频 SPM; 可与 heartRateData[] 对齐计算心率/步频比
- `activeEnergy[]`: 逐分钟能量消耗 (kJ), 可与 stepCount[] 对齐计算每步能量消耗
- `heartRateRecovery[]`: 运动结束后心率恢复序列 (约 5-10 秒采样)

**可衍生的 ATP 级指标** (需你从原始数据中计算):
- TRIMP (训练冲量): duration(min) x avgHR/maxHR, 量化单场运动负荷
- HR Zone 分布: 按 heartRateData[] 统计 Zone1(<70%maxHR) / Zone2(70-85%) / Zone3(>85%) 各占比
- SPM 时序: stepCount[] 每条记录即为该分钟的步频, 分析前后半场步频衰减
- 心率/步频比 (Cardiac Efficiency): heartRateData[i].Avg / stepCount[i].qty, 比值升高=疲劳
- 每步能量消耗: activeEnergy[i].qty / stepCount[i].qty, 数值升高=运动经济性下降
- 心率动态范围: heartRate.max - heartRate.min, 范围越大说明强度变化越剧烈
- HRR1: heartRateRecovery 序列中结束时心率 - 1分钟后心率, >30 bpm 优秀, 20-30 正常, <20 需关注

# Style Guidelines
- **语言风格**: 平实、直接、客观。
- **核心要求**: 每个分析点必须引用具体数值 (如 "平均心率 131 bpm", "后半段 SPM 从 35 降至 22") 作为论据。拒绝空泛描述。
- **篇幅限制**: 全文 500 字以内。

# Task
第一步: 数据有效性检查
如果 `duration` < 600 秒 或 `avgHeartRate` < 70 bpm, 输出 "**数据无效**" 并结束。否则直接进入分析。

第二步: 分维度分析 (每点引用具体数值)
1. **运动强度与心率特征**:
   - 引用 avgHeartRate, maxHeartRate, heartRate.min, duration
   - 计算心率动态范围 (max - min)
   - 分析 heartRateData[] 时序: 心率上升速率、是否出现漂移 (cardiac drift)

2. **心率分区与 TRIMP**:
   - 按 heartRateData[] 统计 Zone1/Zone2/Zone3 各自的时间占比
   - 计算 TRIMP = duration(min) x avgHR/maxHR, 评估本场运动负荷
   - Zone3 占比过高 (>40%) 提示过度消耗

3. **移动效率与 SPM 时序**:
   - 引用 distance, speed, stepCadence
   - 分析 stepCount[] 逐分钟 SPM: 前后半场步频对比, 量化移动衰减幅度
   - 计算心率/步频比随时间的变化, 比值升高提示疲劳导致心血管效率下降

4. **能量消耗与运动经济性**:
   - 引用 activeEnergyBurned 总量, 换算 kcal
   - 分析 activeEnergy[] 时序的前后半场对比
   - 计算每步能量消耗 (activeEnergy[i] / stepCount[i]), 数值升高=运动经济性下降

5. **心肺恢复能力 (HRR)**:
   - 分析 heartRateRecovery[] 序列, 计算 HRR1
   - 评估标准: >30 bpm 优秀, 20-30 正常, <20 需关注

6. **综合战术建议**:
   - 基于上述 5 个维度的数据发现, 结合左手持拍优势, 给出针对性调整

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

        prompt = f"""你是一位职业网球体能分析师。请对以下在 {date_str} 完成的 {len(workouts)} 场网球运动进行赛后生理复盘。

# Available Data (每场均包含以下维度)
- 汇总: duration, avgHeartRate, maxHeartRate, heartRate.min, activeEnergyBurned, distance, speed, stepCadence
- 时序: heartRateData[] (逐分钟心率), stepCount[] (逐分钟步数/SPM), activeEnergy[] (逐分钟能量消耗)
- 恢复: heartRateRecovery[] (运动后心率恢复序列)
- 可衍生: TRIMP (duration_min x avgHR/maxHR), HR Zone 分布, 心率/步频比, 每步能量消耗, HRR1

# 要求 (每点必须引用具体数值):
1. **全天数据结算**: 累计时长、总卡路里 (kJ->kcal)、全天加权平均心率、全天峰值心率、总移动距离、总步数。
2. **TRIMP 负荷对比**: 计算各场 TRIMP 值, 评估负荷分布是否均匀。
3. **跨场体能衰减**: 逐场对比 avgHeartRate、stepCadence (SPM)、speed。计算心率/步频比在各场间的变化, 量化疲劳对移动能力的影响。
4. **能量分配与经济性**: 对比各场 activeEnergy[] 时序的前后半场分布; 计算各场的每步能量消耗, 判断运动经济性是否随场次下降。
5. **恢复能力对比**: 对比各场 heartRateRecovery[] 的 HRR1 值, 判断心肺恢复能力是否随场次下降。
6. **表现特征总结**: 基于以上数据归纳生理特征 (如高心率耐受型、晚期衰减型等)。
7. **拒绝建议**: 只归纳已发生的数据, 不给出任何训练或战术建议。
8. **字数**: 500 字以内, 平实、严谨。

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
