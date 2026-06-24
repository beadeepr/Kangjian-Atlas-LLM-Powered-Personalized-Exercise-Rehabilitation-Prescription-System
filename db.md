# 数据库设计文档

> 版本：v2.0 | 更新日期：2026-06-24
> 本文档基于真实代码 `backend/app/models.py`、`backend/app/database.py` 整理

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. 设计目标

为系统建立稳定的数据模型，满足用户体系、患者信息管理、康复处方存储、训练闭环追踪、影像报告存储、穿戴疲劳监测、医患协同审核与数据分析需求。

## 2. 数据库选型

### 2.1 开发/生产双模式

| 环境 | 数据库 | 连接方式 |
|---|---|---|
| 本地开发 | SQLite | `DATABASE_URL=sqlite:///backend/database.db`（默认） |
| 生产部署 | PostgreSQL 17 | `DATABASE_URL=postgresql+psycopg://kangjian:kangjian_password@postgres:5432/kangjian_atlas` |

切换方式：只需修改环境变量 `DATABASE_URL`，无需修改任何业务代码。

### 2.2 配套存储组件

| 组件 | 用途 | 选型 |
|---|---|---|
| ORM | 模型定义、数据操作 | SQLAlchemy ORM |
| 缓存 | 热点数据（动作库等） | Redis（通过 `REDIS_URL` 配置，未配置时自动禁用） |
| 对象文件 | 影像报告文件存储 | 开发：本地 `backend/uploads`；生产：MinIO |
| RAG 向量 | 康复知识检索索引 | Chroma / Qdrant / local JSON three-way fallback |

### 2.3 ORM 管理

- 所有模型集中在 `backend/app/models.py` 中定义
- 使用 `Base = declarative_base()` 统一声明
- 应用启动时 `database.py` 的 `init_db()` 通过 `Base.metadata.create_all()` 自动建表
- SQLite 模式下自动调用 `_ensure_sqlite_columns()` 为旧表补充新增字段（`raw_response`、`user_id`、`patient_profile_id`、`role`）
- 生产环境建议引入 Alembic 管理迁移

## 3. 主要数据表设计

后端当前定义 **11 张业务表 + 1 张反馈表**，全部位于 `backend/app/models.py`。

### 3.1 `users` — 用户表

存储系统用户信息，支持患者（`user`）、医生（`doctor`）、管理员（`admin`）三类角色。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 用户 ID |
| account | String(64) | 唯一，非空，索引 | 登录账号 |
| password_hash | String(256) | 非空 | PBKDF2-HMAC-SHA256 密码哈希 |
| nickname | String(64) | 非空 | 昵称 |
| role | String(32) | 非空，默认 `user` | 角色：`user` / `doctor` / `admin` |
| gender | String(16) | 可空 | 性别 |
| age | Integer | 可空 | 年龄 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

**关联关系**：1:N → patient_profiles, prescriptions, training_checkins, imaging_reports, wearable_metrics, user_feedback  
**特殊角色**：管理员和医生账号可由环境变量 `ADMIN_ACCOUNTS`、`DOCTOR_ACCOUNTS` 预配置

### 3.2 `patient_profiles` — 患者档案表

保存患者详细康复资料，同一账号可维护多个患者档案（如代管家人）。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 档案 ID |
| user_id | Integer | 外键 users.id，非空，索引 | 所属用户 |
| name | String(128) | 非空 | 患者姓名 |
| gender | String(16) | 可空 | 性别 |
| age | Integer | 可空 | 年龄 |
| phone | String(32) | 可空 | 联系方式 |
| height_cm | Integer | 可空 | 身高（cm） |
| weight_kg | Integer | 可空 | 体重（kg） |
| pain_regions | JSON | 可空 | 疼痛部位数组，如 `["腰部", "颈部"]` |
| history | Text | 可空 | 既往史 |
| allergy_history | Text | 可空 | 过敏史 |
| surgery_history | Text | 可空 | 手术史 |
| rehab_goal | Text | 可空 | 康复目标 |
| note | Text | 可空 | 备注 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

### 3.3 `prescriptions` — 康复处方表

核心业务表，保存每次处方生成结果。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 处方 ID |
| user_id | Integer | 外键 users.id，可空，索引 | 创建用户 |
| patient_profile_id | Integer | 外键 patient_profiles.id，可空，索引 | 关联患者档案 |
| patient_name | String(128) | 可空 | 患者姓名快照 |
| patient_age | Integer | 可空 | 患者年龄快照 |
| symptoms | Text | 非空 | 主诉/症状描述 |
| history | Text | 可空 | 病史 |
| summary | Text | 可空 | 处方摘要 |
| raw_response | JSON | 可空 | 模型原始响应、安全评估、RAG 上下文 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

**关联关系**：级联删除 actions；1:N → training_checkins, prescription_reviews, prescription_adjustments

### 3.4 `actions` — 处方动作明细表

保存处方中的动作执行快照。动作基础信息（禁忌、进阶、降阶等）存储在 JSON 知识库 `knowledge/actions.json`。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 动作记录 ID |
| prescription_id | Integer | 外键 prescriptions.id，非空 | 所属处方 |
| name | String(128) | 非空 | 动作名称 |
| sets | Integer | 可空 | 组数 |
| reps | Integer | 可空 | 次数 |
| note | Text | 可空 | 动作说明 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

### 3.5 `pose_feedback` — 姿态反馈表

保存动作纠正接口的请求数据和反馈结果。支持规则算法和 RTMPose ONNX 模型推理两种方式。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 反馈 ID |
| request_data | JSON | 可空 | 动作 ID、关键点、可见度、时间戳 |
| feedback | JSON | 非空 | 反馈文本、评分、状态 |
| created_at | DateTime | 默认当前时间 | 创建时间 |

### 3.6 `imaging_reports` — 影像报告表

保存用户上传的影像文件、OCR 文本及红旗症状识别结果。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 报告 ID |
| user_id | Integer | 外键 users.id，非空，索引 | 所属用户 |
| patient_profile_id | Integer | 外键 patient_profiles.id，可空，索引 | 关联患者档案 |
| report_type | String(64) | 可空 | 类型：MRI / CT / X-Ray / 影像报告 |
| file_name | String(256) | 可空 | 原始文件名 |
| file_path | String(512) | 可空 | 本地或 MinIO 文件路径 |
| ocr_text | Text | 可空 | OCR 或 TXT 提取文本 |
| ocr_status | String(32) | 非空，默认 `pending` | 状态：`pending` / `provided` / `text_file_extracted` / `pending_external_ocr` / `done` / `failed` |
| risk_level | String(32) | 非空，默认 `unknown` | 风险等级：`low` / `medium` / `high` / `unknown` |
| red_flags | JSON | 可空 | 红旗症状列表 |
| note | Text | 可空 | 备注 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

**业务逻辑**：处方生成前读取风险等级，`high` 时阻止生成居家康复处方，强制提示就医。

### 3.7 `training_checkins` — 训练打卡表

保存患者每次训练打卡记录，为趋势统计和进度报告提供数据来源。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 打卡 ID |
| user_id | Integer | 外键 users.id，非空，索引 | 所属用户 |
| patient_profile_id | Integer | 外键 patient_profiles.id，可空，索引 | 患者档案 |
| prescription_id | Integer | 外键 prescriptions.id，可空，索引 | 关联处方 |
| action_id | String(128) | 可空 | 动作库 ID |
| action_name | String(128) | 非空 | 动作名称 |
| trained_on | Date | 非空，索引 | 训练日期 |
| completed_sets | Integer | 可空 | 完成组数 |
| completed_reps | Integer | 可空 | 完成次数 |
| pain_before | Integer | 可空 | 训练前 VAS 疼痛评分（0~10） |
| pain_after | Integer | 可空 | 训练后 VAS 疼痛评分（0~10） |
| difficulty | Integer | 可空 | 主观难度（1~10） |
| score | Integer | 可空 | 综合评分（0~100） |
| note | Text | 可空 | 备注 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

**业务逻辑**：系统自动处方调整会读取近 14 天训练记录，判断是否需要降低训练负荷。

### 3.8 `wearable_metrics` — 穿戴指标表

保存穿戴设备或手动录入的运动生理指标，系统计算疲劳风险。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 指标 ID |
| user_id | Integer | 外键 users.id，非空，索引 | 所属用户 |
| patient_profile_id | Integer | 外键 patient_profiles.id，可空，索引 | 患者档案 |
| training_checkin_id | Integer | 外键 training_checkins.id，可空，索引 | 关联训练打卡 |
| device_type | String(64) | 可空 | 设备类型 |
| heart_rate | Integer | 可空 | 运动心率（bpm） |
| resting_heart_rate | Integer | 可空 | 静息心率（bpm） |
| hrv_ms | Integer | 可空 | HRV（ms） |
| spo2 | Integer | 可空 | 血氧（%） |
| steps | Integer | 可空 | 步数 |
| calories | Integer | 可空 | 热量（kcal） |
| skin_temperature_c | Float | 可空 | 皮温（℃） |
| perceived_exertion | Integer | 可空 | 主观用力程度（Borg 量表 0~20） |
| duration_minutes | Integer | 可空 | 训练时长（分钟） |
| fatigue_score | Integer | 非空，默认 0 | 系统综合疲劳评分 |
| risk_level | String(32) | 非空，默认 `low`，索引 | 疲劳风险：`low` / `medium` / `high` |
| signals | JSON | 可空 | 触发风险的指标信号 |
| recommendation | Text | 可空 | 训练调整建议 |
| recorded_at | DateTime | 默认当前时间，索引 | 记录时间 |
| created_at | DateTime | 默认当前时间 | 创建时间 |

**疲劳算法**：综合心率、静息心率、HRV、血氧、主观用力、训练时长等多维指标，基于近 20 条历史记录计算波动趋势。

### 3.9 `doctor_patient_links` — 医患关系表

保存医生与患者之间的授权绑定关系，控制处方访问权限。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 关系 ID |
| user_id | Integer | 外键 users.id，非空，索引 | 患者用户 |
| doctor_id | Integer | 外键 users.id，非空，索引 | 医生用户 |
| patient_profile_id | Integer | 外键 patient_profiles.id，可空，索引 | 授权的患者档案 |
| status | String(32) | 非空，默认 `active`，索引 | 状态：`active` / `inactive` |
| patient_note | Text | 可空 | 患者备注 |
| doctor_note | Text | 可空 | 医生备注 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

**业务约束**：医生必须与患者建立 `active` 关系后，才能审核该患者的处方。

### 3.10 `prescription_reviews` — 处方审核表

保存患者主动分享给医生的处方审核记录。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 审核 ID |
| prescription_id | Integer | 外键 prescriptions.id，非空，索引 | 被审核处方 |
| user_id | Integer | 外键 users.id，非空，索引 | 患者用户 |
| doctor_id | Integer | 外键 users.id，非空，索引 | 医生用户 |
| patient_profile_id | Integer | 外键 patient_profiles.id，可空，索引 | 患者档案 |
| status | String(32) | 非空，默认 `pending`，索引 | `pending` / `reviewed` / `approved` / `changes_requested` |
| patient_note | Text | 可空 | 患者说明 |
| doctor_note | Text | 可空 | 医生审核意见 |
| risk_level | String(32) | 非空，默认 `unknown`，索引 | 风险等级 |
| reviewed_at | DateTime | 可空 | 审核完成时间 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

### 3.11 `prescription_adjustments` — 处方调整表

保存医生或系统对处方提出的调整建议及患者决策结果。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 调整 ID |
| review_id | Integer | 外键 prescription_reviews.id，可空，索引 | 来源审核 |
| prescription_id | Integer | 外键 prescriptions.id，非空，索引 | 原处方 |
| user_id | Integer | 外键 users.id，非空，索引 | 患者用户 |
| doctor_id | Integer | 外键 users.id，可空，索引 | 医生用户（系统调整时为空） |
| source | String(32) | 非空，默认 `doctor`，索引 | 来源：`doctor` / `system` |
| status | String(32) | 非空，默认 `proposed`，索引 | `proposed` / `applied` / `rejected` |
| reason | Text | 可空 | 调整原因 |
| summary | Text | 可空 | 调整后处方摘要 |
| action_changes | JSON | 可空 | 动作变更规则 |
| adjusted_actions | JSON | 可空 | 调整后动作列表快照 |
| created_prescription_id | Integer | 外键 prescriptions.id，可空，索引 | 采纳后生成的新处方 |
| decided_at | DateTime | 可空 | 患者决策时间 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

**业务逻辑**：患者点击"采纳"后，系统根据 `adjusted_actions` 生成新的 `prescriptions` 和 `actions` 记录。

### 3.12 `user_feedback` — 用户反馈表

保存用户向后台提交的意见反馈。

| 字段 | 数据类型 | 约束/索引 | 说明 |
|------|----------|-----------|------|
| id | Integer | 主键，索引 | 反馈 ID |
| user_id | Integer | 外键 users.id，可空，索引 | 反馈用户（未登录时为空） |
| category | String(64) | 非空，默认 `general` | `general` / `bug` / `suggestion` |
| rating | Integer | 可空 | 评分（1~5） |
| content | Text | 非空 | 反馈内容 |
| contact | String(128) | 可空 | 联系方式 |
| source | String(64) | 可空 | 来源页面 |
| status | String(32) | 非空，默认 `open`，索引 | `open` / `processing` / `resolved` / `closed` |
| admin_note | Text | 可空 | 管理员备注 |
| created_at | DateTime | 默认当前时间 | 创建时间 |
| updated_at | DateTime | 自动更新 | 更新时间 |

## 4. 数据表关联关系总览

### 4.1 核心层级关系

```text
users
  ├─ patient_profiles (1:N)
  │   ├─ prescriptions (1:N)
  │   │   ├─ actions (1:N, cascade delete)
  │   │   ├─ training_checkins (1:N)
  │   │   ├─ prescription_reviews (1:N, cascade delete)
  │   │   └─ prescription_adjustments (1:N)
  │   ├─ imaging_reports (1:N, cascade delete)
  │   ├─ wearable_metrics (1:N, cascade delete)
  │   └─ doctor_patient_links (1:N)
  ├─ training_checkins (1:N, cascade delete)
  ├─ imaging_reports (1:N, cascade delete)
  ├─ wearable_metrics (1:N, cascade delete)
  └─ user_feedback (1:N, cascade delete)
```

### 4.2 医患协同关系

```text
users(role=user) ──── doctor_patient_links ──── users(role=doctor)
       │                                                │
       └────── prescription_reviews ──────────────────┘
                          │
                          └── prescription_adjustments
                                    │
                                    └── 新 prescriptions（采纳时生成）
```

### 4.3 训练与疲劳监测关系

```text
prescriptions ── actions（动作明细）
      │
      ├── training_checkins（训练打卡）
      │         │
      │         └── wearable_metrics（关联打卡的穿戴指标）
      │
      └── prescription_adjustments ── 新 prescriptions
```

## 5. ORM 与初始化

### 5.1 模型定义（`backend/app/models.py`）

```python
from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# 所有模型通过 Base 统一声明
# 启动时调用 Base.metadata.create_all() 自动建表
```

### 5.2 数据库初始化（`backend/app/database.py`）

```python
# 根据环境变量决定使用 SQLite 或 PostgreSQL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'database.db'}")

# 核心方法
init_db()              # 建表 + SQLite 补列
check_database()       # 健康检查：SELECT 1
database_backend()     # 返回当前数据库后端信息
```

## 6. 数据库设计原则

- **外键约束**：所有跨表引用均使用 SQLAlchemy ForeignKey，确保数据关系一致性。
- **索引策略**：为 `account`、各 `user_id`、`trained_on`、`recorded_at`、`status`、`risk_level` 等查询频繁字段单独建立索引。
- **JSON 字段**：`pain_regions`、`raw_response`、`red_flags`、`signals`、`action_changes`、`adjusted_actions`、`request_data`、`feedback` 使用 JSON 类型存储结构化可变数据。
- **时间戳**：所有业务表包含 `created_at` 和 `updated_at`，支持历史追踪和排序。
- **角色分级**：`users.role` 字段区分 `user` / `doctor` / `admin`，配合 `ADMIN_ACCOUNTS`、`DOCTOR_ACCOUNTS` 环境变量实现权限控制。

## 7. 备份与迁移

- 建议生产环境引入 **Alembic** 管理数据库变更迁移。
- 生产环境需定期备份 PostgreSQL 数据、MinIO bucket 和 RAG 向量索引目录。
- 制定 RTO/RPO 目标，确保宕机后数据可恢复。
- 审核敏感数据访问合规性。

## 8. 后续扩展（待规划表）

| 表名 | 用途 |
|------|------|
| knowledge_articles | 知识库条目表，脱离 JSON 文件实现后台管理维护 |
| audit_logs | 审计日志，记录管理员操作、医生审核和敏感数据访问 |
| appointment | 康复预约与随访管理 |
| notification | 系统消息与提醒 |
| evaluation | 康复评估结果 |

## 9. 各模块对应数据表速查

| 功能模块 | 使用到的表 |
|----------|-----------|
| 注册登录 | users |
| 患者档案 | patient_profiles |
| 影像报告 | imaging_reports |
| 处方生成 | prescriptions, actions |
| 处方导出 | prescriptions, actions |
| 训练打卡 | training_checkins |
| 进度报告 | training_checkins |
| 姿态纠正 | pose_feedback |
| 疲劳监测 | wearable_metrics |
| 医患绑定 | doctor_patient_links, users |
| 处方审核 | prescription_reviews, prescriptions |
| 处方调整 | prescription_adjustments, prescriptions |
| 用户反馈 | user_feedback |
| 后台管理 | users, user_feedback + 全部表（dashboard 统计） |
