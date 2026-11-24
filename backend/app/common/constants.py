"""全局阈值与常量统一收口（02 D10：全部为代码常量，不做成可配置）。

来源：需求 §5 关键枚举与阈值汇总、04 §1.5/§1.7、02 T6 安全与频控。
"""

# ---- 分页（04 §1.3）----
PAGE_SIZE_DEFAULT = 10
PAGE_SIZE_MAX = 100
PAGE_NUM_MIN = 1

# ---- 安全与频控（T6 定稿阈值）----
LOGIN_FAIL_MAX = 5                 # 连续密码错误 5 次
LOGIN_LOCK_SECONDS = 5 * 60        # 锁定 5 分钟
SMS_SEND_INTERVAL_SECONDS = 60     # 同手机号 60s 仅 1 次
SMS_DAILY_LIMIT = 10               # 同手机号每日上限 10 次
SMS_VERIFY_FAIL_MAX = 5            # 同验证码连续校验失败 5 次失效
SMS_CODE_LENGTH = 6                # 6 位验证码
SMS_CODE_TTL_SECONDS = 5 * 60      # ⚠️ 有效期待与用户确认（需求未定稿，暂定 5 分钟）

# ---- 密码规则 ----
PASSWORD_MIN_LEN = 6
PASSWORD_MAX_LEN = 20

# ---- 后台账号（04 §4.5.1：重置为默认密码=应用层常量）----
ADMIN_DEFAULT_PASSWORD = "admin123"  # 重置默认密码；内置超管初始密码（上线前应强制修改）
ADMIN_SUPER_USERNAME = "admin"       # 内置超管账号（唯一，03 §2.1.1）

# ---- 学习训练 ----
WRONG_LEVEL_HIGH_FREQ = 3          # ≥3 次 = 高频易错
WRONG_LEVEL_MULTIPLE = 2           # =2 次 = 多次错误
WRONG_MASTERY_STREAK = 3           # 连续答对 3 次自动标记已掌握
SHORT_ANSWER_PASS_SCORE = 6        # 简答 AI 批改 ≥6 分判通过（满分 10）

# ---- AI 面试 ----
INTERVIEW_QUOTA_PER_DAY = 5             # 每日 5 次（次日 0 点重置，Asia/Shanghai 日界）
INTERVIEW_QUESTION_COUNTS = (3, 5, 8, 10, 15)  # 题量档位
INTERVIEW_QUESTION_COUNT_DEFAULT = 10   # 默认 10 题
INTERVIEW_QUESTION_TIMEOUT_SECONDS = 5 * 60  # 单问固定 5 分钟

# ---- 导入上限（02 D8）----
IMPORT_COURSE_MAX_ROWS = 2000
IMPORT_QUESTION_MAX_ROWS = 500
EXPORT_MAX_ROWS = 10000

# ---- 文件上传限制（04 §1.4）----
UPLOAD_EXCEL_MAX_BYTES = 5 * 1024 * 1024     # Excel ≤5MB
UPLOAD_IMAGE_MAX_BYTES = 2 * 1024 * 1024     # 图片 jpg/png ≤2MB

# ---- 内容（04 §4.3 学科主题色 = 预置色板，与 prototype/admin/subjects.html PALETTE 一致）----
THEME_COLOR_PALETTE = (
    "#2a78d6", "#6250d6", "#1baf7a", "#eb6834",
    "#e87ba4", "#008300", "#eda100", "#e34948",
)

# ---- 逻辑删除标记 ----
DELETED_AT_NULL = None  # deleted_at IS NULL = 有效（语义常量，供代码引用）
