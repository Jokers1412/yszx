"""枚举：数据库 TINYINT 数值 ↔ API 小写驼峰字符串（04 附录 C 定稿映射）。

API JSON 中一律使用字符串枚举（如 difficulty: "easy"）；入库转数值。
"""
from enum import IntEnum


class ApiEnum(IntEnum):
    """带 API 字符串映射的基类。"""

    @property
    def api(self) -> str:
        return _API_STRINGS[self.__class__][self]

    @classmethod
    def from_api(cls, value: str) -> "ApiEnum":
        for member, s in _API_STRINGS[cls].items():
            if s == value:
                return member
        raise ValueError(f"invalid {cls.__name__} api value: {value!r}")


class Difficulty(ApiEnum):
    EASY = 1
    MEDIUM = 2
    HARD = 3


class QuestionType(ApiEnum):
    SINGLE = 1
    MULTIPLE = 2
    JUDGE = 3
    SHORT = 4


class QuestionStatus(ApiEnum):
    ON_SHELF = 1
    OFF_SHELF = 2
    PENDING = 3
    DRAFT = 4  # DB 预留不启用（03 §2.2）
    REJECTED = 5


class EnableStatus(ApiEnum):
    ENABLED = 1
    DISABLED = 0


class Gender(ApiEnum):
    MALE = 0
    FEMALE = 1
    SECRET = 2


class CourseSource(ApiEnum):
    BILI = 1
    OTHER = 2


class InterviewQuestionSource(ApiEnum):
    MANUAL = 1
    EXCEL = 2


class AnswerScene(ApiEnum):
    PRACTICE = 1
    WRONG_REVIEW = 2


class MasteryStatus(ApiEnum):
    REVIEWING = 0
    MASTERED = 1


class OperationActionType(ApiEnum):
    LOGIN = 1
    CREATE = 2
    UPDATE = 3
    DELETE = 4
    DISABLE = 5
    OTHER = 6


class JudgeAnswer(ApiEnum):
    TRUE = 1
    FALSE = 0


# 错题等级为派生值（无 DB 数值），单独定义
WRONG_LEVEL_HIGH_FREQ = "highFreq"
WRONG_LEVEL_MULTIPLE = "multiple"
WRONG_LEVEL_OCCASIONAL = "occasional"

_API_STRINGS: dict[type[ApiEnum], dict[ApiEnum, str]] = {
    Difficulty: {Difficulty.EASY: "easy", Difficulty.MEDIUM: "medium", Difficulty.HARD: "hard"},
    QuestionType: {
        QuestionType.SINGLE: "single",
        QuestionType.MULTIPLE: "multiple",
        QuestionType.JUDGE: "judge",
        QuestionType.SHORT: "short",
    },
    QuestionStatus: {
        QuestionStatus.ON_SHELF: "onShelf",
        QuestionStatus.OFF_SHELF: "offShelf",
        QuestionStatus.PENDING: "pending",
        QuestionStatus.DRAFT: "draft",
        QuestionStatus.REJECTED: "rejected",
    },
    EnableStatus: {EnableStatus.ENABLED: "enabled", EnableStatus.DISABLED: "disabled"},
    Gender: {Gender.MALE: "male", Gender.FEMALE: "female", Gender.SECRET: "secret"},
    CourseSource: {CourseSource.BILI: "bili", CourseSource.OTHER: "other"},
    InterviewQuestionSource: {
        InterviewQuestionSource.MANUAL: "manual",
        InterviewQuestionSource.EXCEL: "excel",
    },
    AnswerScene: {AnswerScene.PRACTICE: "practice", AnswerScene.WRONG_REVIEW: "wrongReview"},
    MasteryStatus: {
        MasteryStatus.REVIEWING: "reviewing",
        MasteryStatus.MASTERED: "mastered",
    },
    OperationActionType: {
        OperationActionType.LOGIN: "login",
        OperationActionType.CREATE: "create",
        OperationActionType.UPDATE: "update",
        OperationActionType.DELETE: "delete",
        OperationActionType.DISABLE: "disable",
        OperationActionType.OTHER: "other",
    },
    JudgeAnswer: {JudgeAnswer.TRUE: "true", JudgeAnswer.FALSE: "false"},
}
