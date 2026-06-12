# 数据库设计文档

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. 设计目标

为后续系统扩展建立稳定的数据模型，满足患者信息管理、康复处方存储、医生审核与数据分析需求。

## 2. 建议数据库类型

- MVP 阶段：`SQLite` 可快速验证功能。
- 中长期：推荐 `PostgreSQL` 或 `MySQL`。
- ORM 推荐：`SQLAlchemy` + `Alembic` 用于数据库迁移与模型管理。

## 3. 主要数据表设计

### 3.1 `users`

存储系统用户信息，支持患者、医生、管理员。

| 字段 | 数据类型 | 说明 |
|------|----------|------|
| id | INTEGER | 主键，自增 |
| username | VARCHAR | 登录账号 |
| password_hash | VARCHAR | 密码哈希 |
| role | VARCHAR | 用户角色（patient/therapist/admin） |
| full_name | VARCHAR | 姓名 |
| class_info | VARCHAR | 班级信息（可选） |
| student_id | VARCHAR | 学号（可选） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 3.2 `patients`

存储患者详细资料，可与 `users` 关联。

| 字段 | 数据类型 | 说明 |
|------|----------|------|
| id | INTEGER | 主键 |
| user_id | INTEGER | 关联 users.id |
| age | INTEGER | 年龄 |
| gender | VARCHAR | 性别 |
| height | FLOAT | 身高 |
| weight | FLOAT | 体重 |
| medical_history | TEXT | 病史 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 3.3 `prescriptions`

存储康复处方记录。

| 字段 | 数据类型 | 说明 |
|------|----------|------|
| id | INTEGER | 主键 |
| patient_id | INTEGER | 关联 patients.id |
| therapist_id | INTEGER | 关联 users.id |
| summary | TEXT | 处方摘要 |
| raw_input | JSON | 原始问诊输入 |
| status | VARCHAR | 处方状态（draft/approved/completed） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 3.4 `actions`

存储处方动作明细。

| 字段 | 数据类型 | 说明 |
|------|----------|------|
| id | INTEGER | 主键 |
| prescription_id | INTEGER | 关联 prescriptions.id |
| name | VARCHAR | 动作名称 |
| sets | INTEGER | 组数 |
| reps | INTEGER | 次数 |
| note | TEXT | 说明 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 3.5 `pose_feedback`

存储姿势纠正反馈记录。

| 字段 | 数据类型 | 说明 |
|------|----------|------|
| id | INTEGER | 主键 |
| patient_id | INTEGER | 关联 patients.id |
| request_data | JSON | 请求姿势数据 |
| feedback | JSON | 反馈文本列表 |
| created_at | TIMESTAMP | 创建时间 |

## 4. 数据模型示例（SQLAlchemy）

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False)
    full_name = Column(String(128))
    class_info = Column(String(128))
    student_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Patient(Base):
    __tablename__ = 'patients'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    age = Column(Integer)
    gender = Column(String(16))
    height = Column(String(32))
    weight = Column(String(32))
    medical_history = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Prescription(Base):
    __tablename__ = 'prescriptions'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False)
    therapist_id = Column(Integer, ForeignKey('users.id'))
    summary = Column(Text)
    raw_input = Column(JSON)
    status = Column(String(32), default='draft')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Action(Base):
    __tablename__ = 'actions'
    id = Column(Integer, primary_key=True)
    prescription_id = Column(Integer, ForeignKey('prescriptions.id'), nullable=False)
    name = Column(String(128), nullable=False)
    sets = Column(Integer)
    reps = Column(Integer)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PoseFeedback(Base):
    __tablename__ = 'pose_feedback'
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patients.id'))
    request_data = Column(JSON)
    feedback = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

## 5. 数据库设计原则

- 使用外键确保数据关系一致性。
- 为常用查询字段添加索引，如 `patient_id`、`therapist_id`。
- 使用 JSON 字段存储结构化可变数据，如原始问诊输入与反馈。
- 记录创建/更新时间，支持历史追踪。
- 预留用户角色字段，支持权限控制。

## 6. 备份与迁移

- 使用 `Alembic` 管理数据库变更。
- 定期备份生产数据库。
- 在上线前执行数据模型评审，确认表结构与业务需求匹配。

## 7. 后续扩展

- 增加 `resources` 表存储康复资源与知识库条目。
- 增加 `appointment` 表管理康复预约与随访。
- 增加 `evaluation` 表记录康复评估结果。
- 增加 `notification` 表存储系统消息与提醒。
