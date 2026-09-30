# -*- coding: utf-8 -*-
"""考频加权艾宾浩斯记忆排程。
说明：
- 用于按“词汇掌握质量”动态安排下一次复习时间；
- 词汇的“熟悉程度、词频、难度、上次表现”都会影响复习间隔；
- 只要用户回忆质量达到 3 分及以上，就认为记住了，下一轮间隔会变长；
- 若质量低于 3，则说明未掌握，系统会缩短阶段并增加遗忘计数。
"""
from django.utils import timezone
from datetime import timedelta

# 经典艾宾浩斯间隔（分钟），表示从刚学会到长期记忆的常见复习节奏。
# 例如：0 分钟（立刻复习）、10 分钟、1 小时、1 天、3 天……
EB_INTERVALS = [0, 10, 60, 1440, 4320, 10080, 21600, 43200, 86400, 172800]


def clamp(v, lo, hi):
    """将数值限制在 [lo, hi] 范围内，避免出现异常间隔或难度系数。"""
    return max(lo, min(hi, v))


def freq_factor(word):
    """根据词频计算复习系数。

    思路：
    - 高频词（freq_total 较大）更容易掌握，复习间隔可以稍短一些；
    - 低频词需要更长时间巩固，因此间隔会被拉长。
    这里返回值小于 1 表示更容易记住，间隔会缩短；大于 1 表示更难，间隔会放宽。
    """
    ft = word.freq_total()  # 词频总值，越大说明词越常见
    return clamp(1.45 - 0.06 * ft, 0.5, 1.45)


def difficulty_factor(word):
    """难度因子：词越难，复习越要更勤一些。"""
    # 例如单词难度 2 表示中等难度，乘数接近 1；难度更高时系数会增大，间隔略缩短。
    return clamp(1.0 + (word.difficulty - 2) * 0.15, 0.7, 1.45)


def next_interval(word, state, quality):
    """根据当前质量评分，计算下一次复习的阶段和间隔时间。

    quality 取值范围通常是 0-5：
    - 0: 完全不会
    - 3: 大致记住
    - 5: 完全正确
    若 quality >= 3，说明该词已被识别，进入下一阶段；否则为遗忘，退回前一阶段。
    返回值为 (stage, interval_minutes)。
    """
    if quality >= 3:
        # 识记成功后，学习阶段后移一档，进入更久的复习周期
        stage = state.stage + 1

        # 从经典艾宾浩斯表中选择对应的基础间隔；过大阶段时使用最后一个值做上限。
        base = EB_INTERVALS[min(stage, len(EB_INTERVALS) - 1)]

        # 第一个复习阶段从 10 分钟开始，而不是 0 分钟或 1 分钟，避免立刻连续过度重看。
        if stage == 1:
            base = 10

        # 实际复习分钟数会受记忆熟练度、词频和难度共同影响。
        # state.ease 越大，说明词掌握得越稳，间隔可以更长。
        minutes = max(1, int(base * (state.ease / 2.5) * freq_factor(word) * difficulty_factor(word)))
    else:
        # 记不住时，说明当前学习阶段不稳，减回一档并重置为短间隔复习
        state.lapses += 1
        stage = max(0, state.stage - 1)
        minutes = 10

    return stage, minutes


def apply_quality(word, state, quality):
    """按当前回答质量更新记忆状态，并返回一份复习计划字典。"""
    # 统计正确/错误次数，便于后续分析学习表现
    if quality >= 3:
        state.correct_count += 1
    else:
        state.wrong_count += 1
    state.last_quality = quality

    # ease 类似 Anki 的“熟练度因子”：回答越好，ease 越高，间隔会更长；回答越差，ease 会下降。
    # 这里用简化公式模拟该机制，保证数值落在 [1.3, 3.0] 之间。
    if quality >= 3:
        state.ease = clamp(state.ease + (0.1 - (5 - quality) * 0.08), 1.3, 3.0)
    else:
        state.ease = clamp(state.ease - 0.2, 1.3, 3.0)

    # 计算更新后的阶段和下一次复习时间
    stage, minutes = next_interval(word, state, quality)
    state.stage = stage
    state.interval_minutes = minutes
    state.next_review_at = timezone.now() + timedelta(minutes=minutes)
    state.save()

    # 返回给前端或调用方，用于展示本次复习结果和下一次计划
    return {
        "word_id": word.id,
        "stage": state.stage,
        "ease": round(state.ease, 2),
        "interval_minutes": state.interval_minutes,
        "next_review_at": state.next_review_at.isoformat(),
        "lapses": state.lapses,
        "is_new": False,
        "wrong_count": state.wrong_count,
        "correct_count": state.correct_count,
    }