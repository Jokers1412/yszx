"""stats 请求/响应模型（04 §3.2 首页 /home/*）。

统计口径以 03 §5.2 为准（streak=W2 口径、报告评分换算=W3 口径）。
"""
from typing import Optional

from pydantic import BaseModel


class HomeStats(BaseModel):
    """Hero 平台数据（前三项实时统计，好评率静态，展示后缀「+」由前端处理）。"""

    featuredQuestions: int  # 题库已上架题目数
    registeredStudents: int  # 注册学员（有效行）
    aiInterviews: int  # AI 面试次数（interview_record 行数）
    goodRate: float  # 好评率 %（system_setting.good_rate 静态）


class WeekTrendPoint(BaseModel):
    date: str  # YYYY-MM-DD（Asia/Shanghai 日界）
    count: int  # 当日作答题次


class LearnStats(BaseModel):
    """个人学习统计（登录）；admin 身份（isAdmin 登录）返回 0 值。"""

    streak: int  # 连续学习天数（W2：截至今天/昨天向前连续，中断归零）
    accuracy: float  # 正确率 %（答对÷作答，1 位小数，无作答 0）
    totalPracticed: int  # 总练习数（作答题次）
    todayDone: int  # 今日已刷（题次）
    weekTrend: list[WeekTrendPoint]  # 近 7 日按日作答量（含 0 值日）


class HotStage(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    subjectId: int
    subjectName: str
    questionCount: int  # 仅已上架题目


class ProfileStats(BaseModel):
    """个人学习数据（04 §3.1 GET /profile/stats；admin 身份返回全 0）。"""

    practiceCount: int  # 作答题次
    wrongCount: int  # 错题本题目数（wrong_question 有效行）
    interviewCount: int  # 完成的 AI 面试场次
    doneQuestions: int  # 已做过的去重题目数
    accuracy: float  # 正确率 %（答对÷作答，1 位小数，无作答 0）
