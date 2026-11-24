-- ============================================================
-- 云枢智学 数据库建表脚本
-- 目标库：MySQL 8.0+（InnoDB / utf8mb4 / utf8mb4_0900_ai_ci）
-- 设计依据：docs/design/03.数据库设计.md（字段/索引/枚举以该文档为准）
--
-- 全局约定：
--   1. 表名/字段 snake_case，表名单数风格；主键统一 id BIGINT AUTO_INCREMENT。
--   2. 禁止物理外键；表间以 <实体>_id 逻辑关联，引用完整性由应用层维护。
--   3. 时间 UTC 存储（连接时区设为 UTC）；展示层转换 Asia/Shanghai。
--   4. 逻辑删除：deleted_at IS NULL = 有效；所有查询须带 deleted_at IS NULL。
--   5. 「活动行唯一生成列」：*_uk = IF(deleted_at IS NULL, 业务列, NULL) 上建唯一
--      索引——有效行参与唯一校验，已删除行（生成列为 NULL）互不冲突，
--      同一业务值可删除后重建（MySQL 唯一索引中 NULL 互不相等）。
--   6. 无 deleted_at 的表分三类（见 03 §3.2）：编辑替换（行物理替换）、
--      追加只增（统计/快照）、无删除入口（历史报告/系统设置）。
--   7. 枚举取值见 03 §4 状态字典；COMMENT 中同步登记。
-- ============================================================

CREATE DATABASE IF NOT EXISTS yszx
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE yszx;

-- ============================================================
-- 一、账号与权限
-- ============================================================

-- 学员（学员端账号，与后台账号体系独立）
CREATE TABLE student (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  phone         VARCHAR(11)  NOT NULL COMMENT '手机号（登录凭证，业务唯一）',
  password_hash VARCHAR(100) NOT NULL COMMENT '密码哈希（bcrypt）',
  nickname      VARCHAR(50)  NOT NULL COMMENT '用户名/昵称',
  avatar_url    VARCHAR(255) NULL COMMENT '头像 URL',
  email         VARCHAR(100) NULL COMMENT '邮箱',
  gender        TINYINT      NOT NULL DEFAULT 2 COMMENT '性别：0男 1女 2保密',
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '状态：1已启用 0已禁用',
  last_login_at DATETIME     NULL COMMENT '最后登录时间（UTC）',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间（UTC）',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at    DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  phone_uk      VARCHAR(11)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, phone, NULL)) VIRTUAL COMMENT '活动行唯一键',
  PRIMARY KEY (id),
  UNIQUE KEY uk_phone (phone_uk),
  KEY idx_status (status),
  KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学员（学员端账号）';

-- 后台用户（管理端账号）
CREATE TABLE admin_user (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  username      VARCHAR(50)  NOT NULL COMMENT '管理员账号（登录凭证，业务唯一）',
  password_hash VARCHAR(100) NOT NULL COMMENT '密码哈希（bcrypt；重置默认密码为应用层常量）',
  phone         VARCHAR(11)  NOT NULL COMMENT '手机号（业务唯一）',
  email         VARCHAR(100) NULL COMMENT '邮箱（选填）',
  avatar_url    VARCHAR(255) NULL COMMENT '头像 URL',
  role_id       BIGINT       NOT NULL COMMENT '角色 id（逻辑关联 role.id；超管角色禁授新用户由应用层校验）',
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '状态：1已启用 0已禁用',
  last_login_at DATETIME     NULL COMMENT '最后登录时间（UTC）',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at    DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  username_uk   VARCHAR(50)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, username, NULL)) VIRTUAL COMMENT '活动行唯一键',
  phone_uk      VARCHAR(11)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, phone, NULL)) VIRTUAL COMMENT '活动行唯一键',
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username_uk),
  UNIQUE KEY uk_phone (phone_uk),
  KEY idx_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='后台用户';

-- 角色（预置：super_admin/content_reviewer/operator，9 组 33 项授权）
CREATE TABLE role (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  code        VARCHAR(50)  NOT NULL COMMENT '角色编码（业务唯一）',
  name        VARCHAR(50)  NOT NULL COMMENT '角色名称',
  description VARCHAR(255) NULL COMMENT '角色描述',
  is_preset   TINYINT      NOT NULL DEFAULT 0 COMMENT '1预置角色（应用层保护不可删）0自建',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at  DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  code_uk     VARCHAR(50)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, code, NULL)) VIRTUAL COMMENT '活动行唯一键',
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code_uk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='角色';

-- 角色权限点（编辑权限=全量覆盖：事务内物理替换，编辑语义，无 deleted_at）
CREATE TABLE role_permission (
  id              BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  role_id         BIGINT      NOT NULL COMMENT '角色 id（逻辑关联 role.id）',
  permission_code VARCHAR(50) NOT NULL COMMENT '权限码（9 组 33 项目录为代码常量）',
  created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_role_perm (role_id, permission_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='角色权限点';

-- 系统设置（单行表 id=1）
CREATE TABLE system_setting (
  id                  BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键（固定单行 id=1，遵循统一自增主键策略）',
  platform_name       VARCHAR(50)  NOT NULL DEFAULT '云枢智学' COMMENT '平台名称',
  platform_description VARCHAR(500) NULL COMMENT '平台描述',
  logo_url            VARCHAR(255) NULL COMMENT 'Logo URL',
  default_avatar_url  VARCHAR(255) NULL COMMENT '默认头像 URL',
  good_rate           DECIMAL(5,2) NOT NULL DEFAULT 98.00 COMMENT '首页好评率静态展示值（%）',
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统设置（基本信息+首页好评率）';

-- 操作日志（管理端写操作+登录/登出+导出；清空日志=批量逻辑删除）
CREATE TABLE operation_log (
  id             BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  admin_user_id  BIGINT       NULL COMMENT '操作人 admin_user.id（无主场景为空）',
  admin_username VARCHAR(50)  NULL COMMENT '操作人账号快照',
  action_type    TINYINT      NOT NULL COMMENT '操作类型：1登录类(登录/登出) 2新增·创建·上传 3修改·编辑(含审核/上下架/排序/授权/重置密码) 4删除(含清空日志) 5禁用·启用 6其他(含导出)',
  action_desc    VARCHAR(200) NOT NULL COMMENT '操作描述，如「新增课程」',
  target         VARCHAR(200) NULL COMMENT '操作对象，如「课程《xxx》」',
  detail         VARCHAR(500) NULL COMMENT '详情（看板最近活动）',
  ip             VARCHAR(45)  NOT NULL COMMENT 'IP 地址（兼容 IPv6）',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间（UTC）',
  deleted_at     DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效；清空日志批量写入）',
  PRIMARY KEY (id),
  KEY idx_created (created_at),
  KEY idx_user (admin_user_id),
  KEY idx_type_time (action_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='操作日志';

-- ============================================================
-- 二、内容体系
-- ============================================================

-- 学科（含「其他学科」兜底学科）
CREATE TABLE subject (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  name        VARCHAR(50)  NOT NULL COMMENT '学科名称（业务唯一）',
  icon        VARCHAR(10)  NOT NULL COMMENT '学科图标（Emoji）',
  description VARCHAR(255) NOT NULL COMMENT '学科描述',
  sort_order  INT          NOT NULL DEFAULT 0 COMMENT '排序号（越小越靠前）',
  theme_color VARCHAR(20)  NOT NULL COMMENT '主题颜色（预置色板取值）',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at  DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  name_uk     VARCHAR(50)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, name, NULL)) VIRTUAL COMMENT '活动行唯一键',
  PRIMARY KEY (id),
  UNIQUE KEY uk_name (name_uk),
  KEY idx_sort (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学科';

-- 阶段（题目挂载层级）
CREATE TABLE stage (
  id         BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  subject_id BIGINT      NOT NULL COMMENT '所属学科 id（逻辑关联 subject.id）',
  name       VARCHAR(50) NOT NULL COMMENT '阶段名称',
  icon       VARCHAR(10) NULL COMMENT '阶段图标（留空默认）',
  sort_order INT         NOT NULL DEFAULT 0 COMMENT '排序号',
  status     TINYINT     NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at DATETIME    NULL COMMENT '逻辑删除时间（NULL=有效）',
  PRIMARY KEY (id),
  KEY idx_subject_sort (subject_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='阶段';

-- 题目（挂阶段下；状态流转：新增→待审核→已上架/已驳回…）
CREATE TABLE question (
  id               BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  stage_id         BIGINT      NOT NULL COMMENT '所属阶段 id（逻辑关联 stage.id）',
  type             TINYINT     NOT NULL COMMENT '题型：1单选 2多选 3判断 4简答',
  difficulty       TINYINT     NOT NULL COMMENT '难度：1简单 2中等 3困难',
  status           TINYINT     NOT NULL DEFAULT 3 COMMENT '状态：1已上架 2已下架 3待审核(默认) 4草稿(DB预留不启用) 5已驳回',
  content          TEXT        NOT NULL COMMENT '题干',
  judge_answer     TINYINT     NULL COMMENT '判断题正确答案：1正确 0错误（仅 type=3）',
  reference_answer TEXT        NULL COMMENT '简答参考答案（仅 type=4，可留空）',
  analysis         TEXT        NULL COMMENT '解析',
  tags             JSON        NULL COMMENT '标签数组，如 ["RAG","检索"]（结构化存储）',
  created_by       BIGINT      NULL COMMENT '创建人 admin_user.id（审计用）',
  created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at       DATETIME    NULL COMMENT '逻辑删除时间（NULL=有效）',
  PRIMARY KEY (id),
  KEY idx_stage_status (stage_id, status),
  KEY idx_type_difficulty (type, difficulty)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='题目';

-- 题目选项（单选/多选；编辑整体替换语义，无 deleted_at；判断/简答不建选项行）
CREATE TABLE question_option (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  question_id BIGINT       NOT NULL COMMENT '所属题目 id（逻辑关联 question.id）',
  option_key  CHAR(1)      NOT NULL COMMENT '选项键 A-F',
  content     VARCHAR(500) NOT NULL COMMENT '选项内容',
  is_correct  TINYINT      NOT NULL DEFAULT 0 COMMENT '1正确答案 0非正确（多选可多个 1）',
  sort_order  INT          NOT NULL DEFAULT 0 COMMENT '展示顺序',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_question_key (question_id, option_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='题目选项';

-- 课程（B站课程库；无上架/下架状态；bvid 选填全库唯一）
CREATE TABLE course (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  name            VARCHAR(200) NOT NULL COMMENT '课程名称',
  bvid            VARCHAR(20)  NULL COMMENT 'BV 号（选填，业务唯一；导入覆盖匹配键）',
  cover_url       VARCHAR(255) NULL COMMENT '封面图片 URL',
  duration_minutes INT         NOT NULL COMMENT '时长（分钟；表单 小时:分钟、导入 分钟均归一）',
  source          TINYINT      NOT NULL DEFAULT 1 COMMENT '来源：1B站 2其他',
  play_url        VARCHAR(255) NULL COMMENT '播放链接',
  sort_seq        BIGINT       NOT NULL DEFAULT 0 COMMENT '列表顺序权重（导入按 Excel 行序、非导入最新在前，见 03 §7.2 S5）',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at      DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  bvid_uk         VARCHAR(20)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, bvid, NULL)) VIRTUAL COMMENT '活动行唯一键（bvid 为 NULL 不校验）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_bvid (bvid_uk),
  KEY idx_sort_seq (sort_seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='B站课程';

-- 课程-学科关联（多对多；编辑/导入整体替换语义，无 deleted_at）
CREATE TABLE course_subject (
  id         BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  course_id  BIGINT   NOT NULL COMMENT '课程 id（逻辑关联 course.id）',
  subject_id BIGINT   NOT NULL COMMENT '学科 id（逻辑关联 subject.id）',
  is_primary TINYINT  NOT NULL DEFAULT 0 COMMENT '1主学科（选择顺序第一个）0关联学科',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_course_subject (course_id, subject_id),
  KEY idx_subject (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='课程-学科关联';

-- 学习路线（单学科归属；一学科可多条路线）
CREATE TABLE route (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  subject_id      BIGINT       NOT NULL COMMENT '归属学科 id（逻辑关联 subject.id）',
  name            VARCHAR(100) NOT NULL COMMENT '路线名称',
  icon            VARCHAR(10)  NULL COMMENT '路线图标',
  target_education VARCHAR(50) NULL COMMENT '适合学历',
  description     VARCHAR(500) NULL COMMENT '路线描述',
  status          TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0禁用（发布/下线）',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at      DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  PRIMARY KEY (id),
  KEY idx_subject_status (subject_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学习路线';

-- 路线课程（有序；添加/移除/排序为编辑替换语义，无 deleted_at）
CREATE TABLE route_item (
  id         BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  route_id   BIGINT   NOT NULL COMMENT '路线 id（逻辑关联 route.id）',
  course_id  BIGINT   NOT NULL COMMENT '课程 id（可跨学科补充）',
  sort_order INT      NOT NULL DEFAULT 0 COMMENT '课程顺序（=学习顺序）',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_route_course (route_id, course_id),
  KEY idx_route_sort (route_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='路线课程';

-- ============================================================
-- 三、学习训练
-- ============================================================

-- 答题记录（追加型；学习统计唯一数据源；练习会话进度在前端 localStorage 不落库）
CREATE TABLE answer_record (
  id         BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT   NOT NULL COMMENT '学员 id（逻辑关联 student.id）',
  question_id BIGINT  NOT NULL COMMENT '题目 id（逻辑关联 question.id）',
  scene      TINYINT  NOT NULL COMMENT '场景：1刷题练习 2错题重做（仅 2 计入错题纠正进度）',
  answer     JSON     NULL COMMENT '作答快照：单选/多选=选项键数组；判断=bool；简答=文本（03 附录 A）',
  is_correct TINYINT  NOT NULL COMMENT '1正确 0错误（简答按 AI 评分≥6 判通过）',
  ai_grade   JSON     NULL COMMENT '简答 AI 批改 {score, comment, key_points}；客观题为 NULL',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '答题时间（UTC）',
  PRIMARY KEY (id),
  KEY idx_student_time (student_id, created_at),
  KEY idx_question (question_id),
  KEY idx_student_question (student_id, question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='答题记录';

-- 错题本（移除错题=逻辑删除；等级由 wrong_count 派生不落库）
CREATE TABLE wrong_question (
  id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id        BIGINT       NOT NULL COMMENT '学员 id（逻辑关联 student.id）',
  question_id       BIGINT       NOT NULL COMMENT '题目 id（逻辑关联 question.id）',
  wrong_count       INT          NOT NULL DEFAULT 1 COMMENT '错误次数（≥3高频易错 =2多次 =1偶尔，等级派生）',
  correct_streak    INT          NOT NULL DEFAULT 0 COMMENT '连续纠正次数 0~3（仅错题重做场景累加/清零）',
  mastery_status    TINYINT      NOT NULL DEFAULT 0 COMMENT '0待复习 1已掌握（连续答对3次自动或手动标记）',
  last_wrong_answer JSON         NULL COMMENT '「你的答案」快照（最近一次答错，格式同 answer_record.answer）',
  last_wrong_at     DATETIME     NOT NULL COMMENT '最近答错时间（UTC）',
  mastered_at       DATETIME     NULL COMMENT '标记已掌握时间（UTC）',
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at        DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效；移除错题写入）',
  pair_uk           VARCHAR(64)  GENERATED ALWAYS AS (IF(deleted_at IS NULL, CONCAT(student_id, '-', question_id), NULL)) VIRTUAL COMMENT '活动行唯一键',
  PRIMARY KEY (id),
  UNIQUE KEY uk_pair (pair_uk),
  KEY idx_student_mastery (student_id, mastery_status),
  KEY idx_student_lastwrong (student_id, last_wrong_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='错题本';

-- 已学课程（追加型；仅标记不可取消；按课程全局标记，各路线进度同步生效）
CREATE TABLE student_course (
  id         BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id BIGINT   NOT NULL COMMENT '学员 id（逻辑关联 student.id）',
  course_id  BIGINT   NOT NULL COMMENT '课程 id（逻辑关联 course.id）',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '标记时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_student_course (student_id, course_id),
  KEY idx_course (course_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='已学课程（标记已学完）';

-- ============================================================
-- 四、AI 面试
-- ============================================================

-- 面试题库（按学科归属；来源=手工录入/Excel 文件名+行号；无上架下架入口）
CREATE TABLE interview_question (
  id             BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  subject_id     BIGINT       NOT NULL COMMENT '归属学科 id（方向=学科）',
  content        TEXT         NOT NULL COMMENT '题干',
  difficulty     TINYINT      NOT NULL COMMENT '难度：1简单 2中等 3困难',
  topic          VARCHAR(100) NULL COMMENT '主题（自由文本；NULL=未分类；筛选模糊匹配）',
  tags           JSON         NULL COMMENT '标签数组（结构化存储）',
  reference_answer TEXT       NULL COMMENT '参考答案（可留空）',
  source_type    TINYINT      NOT NULL COMMENT '来源：1手工录入 2Excel导入',
  source_file    VARCHAR(255) NULL COMMENT '来源 Excel 文件名（纯文本）',
  source_row     INT          NULL COMMENT '来源数据行序号',
  status         TINYINT      NOT NULL DEFAULT 1 COMMENT '1已上架（默认，当前无上架/下架入口）',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  deleted_at     DATETIME     NULL COMMENT '逻辑删除时间（NULL=有效）',
  PRIMARY KEY (id),
  KEY idx_subject_difficulty (subject_id, difficulty),
  KEY idx_topic (topic)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='面试题库';

-- 面试记录（场次；无删除入口；每日 5 次配额计数在 Redis）
CREATE TABLE interview_record (
  id             BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  student_id     BIGINT       NOT NULL COMMENT '学员 id（逻辑关联 student.id）',
  subject_id     BIGINT       NOT NULL COMMENT '面试方向（=学科 id）',
  difficulty     TINYINT      NOT NULL COMMENT '面试难度：1简单 2中等 3困难',
  question_count INT          NOT NULL COMMENT '配置题量（3/5/8/10/15）',
  answered_count INT          NOT NULL DEFAULT 0 COMMENT '实际作答题数（中途结束可小于配置题量）',
  overall_score  DECIMAL(5,1) NULL COMMENT '综合评分 0~100（报告生成时写入）',
  duration_seconds INT        NOT NULL DEFAULT 0 COMMENT '面试时长（秒）',
  started_at     DATETIME     NULL COMMENT '开始时间（UTC）',
  finished_at    DATETIME     NULL COMMENT '结束/生成报告时间（UTC）',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (id),
  KEY idx_student_subject_time (student_id, subject_id, finished_at),
  KEY idx_student_time (student_id, finished_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='面试记录（场次）';

-- 面试逐题明细（追加型快照；题目引用可空=AI 补充生成题）
CREATE TABLE interview_record_question (
  id                   BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  interview_record_id  BIGINT        NOT NULL COMMENT '场次 id（逻辑关联 interview_record.id）',
  seq                  INT           NOT NULL COMMENT '题号（1..N）',
  interview_question_id BIGINT       NULL COMMENT '来源题库 id（NULL=AI 补充生成题）',
  question_text        TEXT          NOT NULL COMMENT '题干快照（题库变更不影响报告）',
  reference_answer     TEXT          NULL COMMENT '参考答案快照',
  user_answer          TEXT          NULL COMMENT '学员作答（超时未答为 NULL）',
  timed_out            TINYINT       NOT NULL DEFAULT 0 COMMENT '1超时（单问固定5分钟）0正常',
  score                DECIMAL(4,1)  NULL COMMENT '逐题评分 0~10',
  ai_comment           VARCHAR(1000) NULL COMMENT 'AI 评语',
  created_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (id),
  KEY idx_record_seq (interview_record_id, seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='面试逐题明细（快照）';

-- 面试报告（1:1 场次；叙述性内容 JSON 结构化存储，见 03 附录 A）
CREATE TABLE interview_report (
  id                  BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  interview_record_id BIGINT       NOT NULL COMMENT '场次 id（业务唯一）',
  overall_comment     TEXT         NULL COMMENT '整体评价',
  accuracy_rate       DECIMAL(5,2) NULL COMMENT '回答准确度（%）',
  ability_scores      JSON         NOT NULL COMMENT '六维能力分数，键固定：专业基础/表达沟通/逻辑思维/项目经验/应变能力/岗位匹配',
  strengths           JSON         NULL COMMENT '优点列表（字符串数组）',
  improvements        JSON         NULL COMMENT '待提升列表 [{issue, advice}]',
  suggestions         JSON         NULL COMMENT '改进建议（字符串数组，展示编号）',
  coaching            JSON         NULL COMMENT '能力提升三卡 {questions, courses, reinterview}',
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_record (interview_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='面试报告';
