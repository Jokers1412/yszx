# 云枢智学 · 后端（FastAPI 模块化单体）

> 设计依据：`docs/design/02.整体架构设计.md`（§4.2 目录规划）、`03.数据库设计.md`、`04.API接口设计.md`。
> 当前状态：**基础工程骨架**（2026-11-23）——横切能力（配置/DB/Redis/统一响应/异常/JWT/RBAC/频控/审计）与 21 张表 ORM 模型已就位，业务接口待功能开发阶段按 04 契约实现。

## 快速开始

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                                 # 默认值对齐 deploy/.env 本机开发环境

# 基础设施（MySQL:3307 / Redis:6380 / MinIO:9000）需已启动：
#   cd ../deploy && docker compose up -d

uvicorn app.main:app --reload --port 8000
# 接口文档 http://localhost:8000/docs ；探活 http://localhost:8000/healthz
```

## 目录结构（02 §4.2）

```
backend/
├── app/
│   ├── main.py            # 入口：路由注册/中间件/异常/生命周期
│   ├── core/              # 横切：config/database/redis/security(JWT+bcrypt)/
│   │                      #   rbac(9组33项)/ratelimit/response/exceptions/deps/audit
│   ├── common/            # constants(阈值收口 D10)/enums(附录C)/pagination/utils(时区 D9)
│   ├── modules/           # 8 业务模块（模块自治，跨模块只调 service，02 §3.3）
│   │   ├── accounts/      # 学员账号：student 表
│   │   ├── system/        # 后台账号/RBAC/日志/设置：admin_user/role/role_permission/
│   │   │                  #   system_setting/operation_log
│   │   ├── content/       # 内容体系：subject/stage/question/question_option/
│   │   │                  #   course/course_subject/route/route_item
│   │   ├── learning/      # 学习训练：answer_record/wrong_question/student_course
│   │   ├── interview/     # AI 面试：interview_question/interview_record/
│   │   │                  #   interview_record_question/interview_report
│   │   ├── students/      # 学员管理（聚合，无自有表）
│   │   ├── stats/         # 统计聚合（无自有表）
│   │   └── ai/            # AI 网关：Provider 抽象 + Mock（02 D5）
│   └── api/               # 双端路由挂载：/api/portal/v1、/api/admin/v1
├── alembic/               # 迁移（结构基线=schema.sql，首次 alembic stamp head）
├── tests/                 # 冒烟测试
└── scripts/seed.py        # 种子数据（待实现）
```

## 关键约定

| 项 | 约定 | 出处 |
|---|---|---|
| 统一响应 | `{code, message, data}`，成功 code=0；失败为稳定字符串业务码 | 04 §1.2、附录 B |
| 分页 | `pageNum`（从 1）/`pageSize`（默认 10 上限 100）→ `{list,total,pageNum,pageSize}` | 04 §1.3 |
| 字段命名 | JSON lowerCamelCase；DB snake_case；时间 `YYYY-MM-DD HH:mm:ss`（Asia/Shanghai） | 04 §1.1 |
| 认证 | 双端双 JWT（aud=portal/admin，互不通用）；access 2h + refresh 7d/30d | 04 §1.5 |
| 阈值 | 全部代码常量收口 `app/common/constants.py` | 02 D10 |
| 时区 | DB naive UTC；日界口径 Asia/Shanghai | 02 D9 |
| 数据库 | 21 表以 `scripts/sql/schema.sql` 为基线（已建库）；ORM 模型在各模块 models.py | 03 |
| 逻辑删除 | `deleted_at IS NULL=有效`；唯一冲突用「活动行唯一生成列」 | 03 §2 |

## 已知待办（基础工程遗留）

1. **SMS 验证码有效期**（`SMS_CODE_TTL_SECONDS` 暂定 5 分钟）——需求未定稿，开发验证码链路时与用户确认。
2. **接口限流阈值**（config 中 rate_limit_* 占位值）——04 §1.7 未定稿具体数值，联调时确认后固化到 constants。
3. Alembic 首次使用：`alembic stamp head` 建立基线；autogenerate 须人工复核（活动行唯一生成列勿误删）。
4. `scripts/seed.py`（学科/预置角色/内置超管/系统设置）待功能开发阶段实现。
