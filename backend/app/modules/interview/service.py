"""interview 业务服务（04 §4.6 面试题库管理已实现；AI 面试流程后续补充）。

职责：每日配额（Redis，Asia/Shanghai 日界 0 点重置）、抽题（面试题库优先 + AI 补充，
逐题快照）、逐题评分与报告生成编排（经 ai 模块，失败 503 可重试）、记录/回放；
向 stats 暴露统计查询接口（02 §3.3）。

面试题库口径（04 §4.6 / 需求 4.3.4）：
  - 主题为自由文本（D4-20：无词表，筛选模糊匹配；留空=未分类）；
  - 编辑仅可改主题与难度（题干/参考答案录入后只读，extra=forbid 拒收其他字段）；
  - 导入 6 列按表头识别、仅读第一张工作表、学科不存在即整份拒绝；
    来源记 Excel 文件名 + 数据行序号（1 起，A2 口径）；
  - 删除逻辑删除，风险提示文案按来源区分（前端实现）。
"""
import io
import json
import re
import secrets

import openpyxl
import xlrd
import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import COURSE_IMPORT_TOKEN_TTL_SECONDS, UPLOAD_EXCEL_MAX_BYTES
from app.common.enums import Difficulty, InterviewQuestionSource, OperationActionType
from app.common.error_codes import ErrorCode
from app.common.utils import to_shanghai, utc_now
from app.core.audit import record_operation
from app.core.context import AdminContext
from app.core.exceptions import BizError
from app.modules.content.models import Subject
from app.modules.interview.models import InterviewQuestion

_STEM_LIMIT = 80  # 列表题干截断
_IMPORT_TOKEN_PREFIX = "interview:import:"
_IMPORT_PREVIEW_ROWS = 20
_IMPORT_MAX_ROWS = 500  # 02 D8 导入上限
_DIFF_CN = {1: "简单", 2: "中等", 3: "困难"}
_DIFF_FROM_CN = {**{v: k for k, v in _DIFF_CN.items()}, "easy": 1, "medium": 2, "hard": 3}


def _stem(text: str, limit: int = _STEM_LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _item_dict(item: InterviewQuestion, subject_name: str) -> dict:
    return {
        "id": item.id,
        "content": _stem(item.content),
        "subjectName": subject_name,
        "difficulty": Difficulty(item.difficulty).api,
        "topic": item.topic,
        "tags": item.tags or [],
        "sourceType": InterviewQuestionSource(item.source_type).api,
        "sourceFile": item.source_file,
        "sourceRow": item.source_row,
    }


def _filters(q) -> list:
    filters = [InterviewQuestion.deleted_at.is_(None)]
    if q.keyword:
        filters.append(InterviewQuestion.content.like(f"%{q.keyword.strip()}%"))
    if q.subjectId:
        filters.append(InterviewQuestion.subject_id == q.subjectId)
    if q.topic:
        filters.append(InterviewQuestion.topic.like(f"%{q.topic.strip()}%"))
    if q.difficulty and q.difficulty != "all":
        filters.append(InterviewQuestion.difficulty == int(Difficulty.from_api(q.difficulty)))
    if q.unclassifiedOnly:
        filters.append(InterviewQuestion.topic.is_(None))
    return filters


async def list_interview_questions(db: AsyncSession, q) -> dict:
    """题目列表（筛选 + 分页）；unclassifiedOnly 与 topic 互斥（04 §4.6）。"""
    if q.unclassifiedOnly and q.topic:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "「只看未分类」与主题筛选不可同时使用", http_status=400)

    stmt = (
        select(InterviewQuestion, Subject.name)
        .join(Subject, Subject.id == InterviewQuestion.subject_id)
        .where(*_filters(q), Subject.deleted_at.is_(None))
    )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (
        await db.execute(stmt.order_by(InterviewQuestion.id.desc()).offset(q.offset).limit(q.limit))
    ).all()
    return {
        "list": [_item_dict(item, subject_name) for item, subject_name in rows],
        "total": total,
        "pageNum": q.pageNum,
        "pageSize": q.pageSize,
    }


async def get_interview_question(db: AsyncSession, question_id: int) -> dict:
    row = (
        await db.execute(
            select(InterviewQuestion, Subject)
            .join(Subject, Subject.id == InterviewQuestion.subject_id)
            .where(
                InterviewQuestion.id == question_id,
                InterviewQuestion.deleted_at.is_(None),
                Subject.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在", http_status=404)
    item, subject = row
    return {
        **_item_dict(item, subject.name),
        "subjectId": item.subject_id,
        "referenceAnswer": item.reference_answer,
        "createdAt": to_shanghai(item.created_at),
    }


async def create_interview_question(
    db: AsyncSession, ctx: AdminContext, payload, ip: str
) -> dict:
    subject = (
        await db.execute(
            select(Subject).where(Subject.id == payload.subjectId, Subject.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if subject is None:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "所属知识库不存在", http_status=400)

    question = InterviewQuestion(
        subject_id=subject.id,
        content=payload.content,
        difficulty=int(Difficulty.from_api(payload.difficulty)),
        topic=payload.topic.strip() if payload.topic and payload.topic.strip() else None,
        tags=[t.strip() for t in payload.tags if t.strip()] or None,
        reference_answer=payload.referenceAnswer,
        source_type=int(InterviewQuestionSource.MANUAL),  # 手工录入
    )
    db.add(question)
    await db.flush()
    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="录入面试题",
        target=f"面试题 #{question.id}",
        detail=_stem(payload.content, 50),
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": question.id}


async def _require_interview_question(db: AsyncSession, question_id: int) -> InterviewQuestion:
    question = (
        await db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.id == question_id, InterviewQuestion.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if question is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在", http_status=404)
    return question


async def update_interview_question(
    db: AsyncSession, ctx: AdminContext, question_id: int, payload, ip: str
) -> dict:
    """编辑（需求 4.3.4）：仅主题（可清空=未分类）与难度。"""
    question = await _require_interview_question(db, question_id)
    question.topic = payload.topic.strip() if payload.topic and payload.topic.strip() else None
    question.difficulty = int(Difficulty.from_api(payload.difficulty))

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑面试题",
        target=f"面试题 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_interview_question(
    db: AsyncSession, ctx: AdminContext, question_id: int, ip: str
) -> dict:
    question = await _require_interview_question(db, question_id)
    question.deleted_at = utc_now()  # 逻辑删除（风险提示按来源区分，前端文案）

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除面试题",
        target=f"面试题 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


# ---------- 批量导入（两段式：仅读第一张工作表，6 列按表头识别） ----------

_REQUIRED_COLS = ("所属学科", "题干")
_OPTIONAL_COLS = ("难度", "主题", "标签", "参考答案")
_TEMPLATE_HEADERS = ["所属学科", "题干", "难度", "主题", "标签", "参考答案"]


def _read_first_sheet(data: bytes, filename: str) -> list[list[str]]:
    """仅读第一张工作表（需求 4.3.4：多表文件不拒绝，取首表）。"""

    def cell_str(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    if filename.lower().endswith(".xls"):
        book = xlrd.open_workbook(file_contents=data)
        if book.nsheets < 1:
            raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件无工作表", http_status=400)
        sheet = book.sheet_by_index(0)
        return [[cell_str(v) for v in sheet.row_values(i)] for i in range(sheet.nrows)]
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    if not wb.worksheets:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件无工作表", http_status=400)
    return [[cell_str(v) for v in row] for row in wb.worksheets[0].iter_rows(values_only=True)]


async def preview_interview_import(
    db: AsyncSession, r: aioredis.Redis, data: bytes, filename: str
) -> dict:
    """导入预览（需求 4.3.4）：文件名/大小/逐行校验/涉及学科汇总/告警；任一无效行整份拒绝。"""
    if len(data) > UPLOAD_EXCEL_MAX_BYTES:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件超过 5MB 限制", http_status=400)

    sheet = _read_first_sheet(data, filename or "")
    if not sheet:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件内容为空", http_status=400)

    header = sheet[0]
    col_index = {name: header.index(name) for name in _REQUIRED_COLS + _OPTIONAL_COLS if name in header}
    missing = [name for name in _REQUIRED_COLS if name not in col_index]
    if missing:
        return _rejected(0, f"缺少必需列：{'、'.join(missing)}")

    data_rows = sheet[1:]
    if not data_rows:
        return _rejected(0, "文件无数据行")
    if len(data_rows) > _IMPORT_MAX_ROWS:
        return _rejected(0, f"超过单次 {_IMPORT_MAX_ROWS} 行上限")

    subject_ids: dict[str, int] = dict(
        (await db.execute(select(Subject.name, Subject.id).where(Subject.deleted_at.is_(None)))).all()
    )

    def cell(row: list[str], col: str) -> str:
        idx = col_index.get(col)
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    errors: list[dict] = []
    parsed: list[dict] = []
    subject_counts: dict[str, int] = {}

    for offset, row in enumerate(data_rows):
        row_no = offset + 1  # 数据行序号（1 起，与来源「第 N 行」口径一致）
        subject_name = cell(row, "所属学科")
        if not subject_name:
            errors.append({"rowNo": row_no, "reason": "所属学科缺失"})
            continue
        if subject_name not in subject_ids:
            errors.append({"rowNo": row_no, "reason": f"所属学科「{subject_name}」在系统中不存在"})
            continue

        content = cell(row, "题干")
        if not content:
            errors.append({"rowNo": row_no, "reason": "题干为空"})
            continue
        if len(content) > 5000:
            errors.append({"rowNo": row_no, "reason": "题干超过 5000 字"})
            continue

        diff_raw = cell(row, "难度")
        if not diff_raw:
            difficulty = 2  # 默认中等（需求 4.3.4）
        elif diff_raw in _DIFF_FROM_CN:
            difficulty = _DIFF_FROM_CN[diff_raw]
        else:
            errors.append({"rowNo": row_no, "reason": f"难度无效「{diff_raw}」（简单/中等/困难）"})
            continue

        topic = cell(row, "主题") or None
        if topic and len(topic) > 100:
            errors.append({"rowNo": row_no, "reason": "主题超过 100 字"})
            continue
        reference = cell(row, "参考答案") or None
        if reference and len(reference) > 10000:
            errors.append({"rowNo": row_no, "reason": "参考答案超过 10000 字"})
            continue
        tags = [t.strip() for t in re.split(r"[，,、]", cell(row, "标签")) if t.strip()]

        parsed.append(
            {
                "subjectId": subject_ids[subject_name],
                "subjectName": subject_name,
                "content": content,
                "difficulty": difficulty,
                "topic": topic,
                "tags": tags,
                "referenceAnswer": reference,
                "sourceFile": (filename or "")[:255],
                "sourceRow": row_no,
            }
        )
        subject_counts[subject_name] = subject_counts.get(subject_name, 0) + 1

    if errors:
        return {
            "importToken": "",
            "summary": {
                "totalRows": len(data_rows),
                "newCount": 0,
                "updateCount": 0,
                "warningCount": 0,
                "errorCount": len(errors),
            },
            "errors": errors,
            "warnings": [],
            "subjects": [],
            "rows": [],
        }

    token = secrets.token_urlsafe(24)
    await r.set(
        _IMPORT_TOKEN_PREFIX + token,
        json.dumps({"rows": parsed}, ensure_ascii=False),
        ex=COURSE_IMPORT_TOKEN_TTL_SECONDS,
    )
    return {
        "importToken": token,
        "summary": {
            "totalRows": len(data_rows),
            "newCount": len(parsed),
            "updateCount": 0,
            "warningCount": 0,
            "errorCount": 0,
        },
        "errors": [],
        "warnings": [],
        "subjects": [
            {"subjectName": name, "count": count} for name, count in subject_counts.items()
        ],
        "rows": [
            {
                "rowNo": it["sourceRow"],
                "content": _stem(it["content"]),
                "subjectName": it["subjectName"],
                "difficulty": Difficulty(it["difficulty"]).api,
                "topic": it["topic"],
            }
            for it in parsed[:_IMPORT_PREVIEW_ROWS]
        ],
    }


def _rejected(row_no: int, reason: str) -> dict:
    return {
        "importToken": "",
        "summary": {
            "totalRows": 0,
            "newCount": 0,
            "updateCount": 0,
            "warningCount": 0,
            "errorCount": 1,
        },
        "errors": [{"rowNo": row_no, "reason": reason}],
        "warnings": [],
        "subjects": [],
        "rows": [],
    }


async def confirm_interview_import(
    db: AsyncSession, r: aioredis.Redis, payload, ctx: AdminContext, ip: str
) -> dict:
    """确认导入：逐行入库（主题/难度/标签按文件值，来源记文件名+行号）。"""
    raw = await r.get(_IMPORT_TOKEN_PREFIX + payload.importToken)
    if not raw:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED, "importToken 无效或已过期，请重新上传", http_status=400
        )
    await r.delete(_IMPORT_TOKEN_PREFIX + payload.importToken)
    rows: list[dict] = json.loads(raw)["rows"]

    created = 0
    for item in rows:
        db.add(
            InterviewQuestion(
                subject_id=item["subjectId"],
                content=item["content"],
                difficulty=item["difficulty"],
                topic=item["topic"],
                tags=item["tags"] or None,
                reference_answer=item["referenceAnswer"],
                source_type=int(InterviewQuestionSource.EXCEL),
                source_file=item["sourceFile"] or None,
                source_row=item["sourceRow"],
            )
        )
        created += 1

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="批量导入面试题",
        target="面试题库",
        detail=f"导入 {created} 道",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"created": created, "updated": 0}


def build_interview_import_template() -> bytes:
    """导入模板（6 列，需求 4.3.4）。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_TEMPLATE_HEADERS)
    ws.append([
        "AI应用与智能体开发", "请说明 Agent 记忆的短期与长期记忆如何设计？", "中等",
        "Agent", "记忆,Agent", "短期记忆用会话上下文，长期记忆用向量库沉淀并检索。",
    ])
    ws.append([
        "AI大模型开发", "什么是 MoE（专家混合）结构？它带来什么收益？", "困难",
        "深度学习", "MoE", "将 FFN 拆成多个专家按路由激活，参数量大而计算量可控。",
    ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
