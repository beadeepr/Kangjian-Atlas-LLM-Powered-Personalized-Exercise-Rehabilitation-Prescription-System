# 架构与类设计文档

> 版本：v2.0 | 更新日期：2026-06-24
> 本文档基于真实代码 `backend/` 全部模块和 `frontend/` 最新状态整理

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. 技术架构概述

项目采用前后端分离架构，当前已完成覆盖全功能链路的完整系统：

### 1.1 整体技术栈

| 层级 | 技术选型 |
|------|----------|
| 前端 | 静态 HTML + CSS + JavaScript（原生，无框架依赖） |
| 前端姿态 | MediaPipe Pose（33 关键点），支持模拟关键点演示模式 |
| 后端框架 | FastAPI（Python 3.13+） |
| 鉴权 | 自定义 JWT（PBKDF2-HMAC-SHA256 密码哈希） |
| 关系数据库 | 开发：SQLite / 生产：PostgreSQL 17 |
| ORM | SQLAlchemy（`Base.metadata.create_all` 启动建表） |
| 缓存 | Redis（可选，`REDIS_URL` 未配置时自动禁用） |
| 对象存储 | 开发：本地 `backend/uploads` / 生产：MinIO |
| RAG 向量检索 | Chroma / Qdrant / local JSON fallback |
| 大模型 | DeepSeek（火山方舟 OpenAI 兼容接口），本地安全兜底摘要 |
| 姿态识别 | RTMPose ONNX 模型 + 规则算法（algorithms.py + pose_runtime.py） |
| 3D 可视化 | 基于关键点矩阵运算，生成骨骼数据和 AR 叠加信息 |
| 语音纠错 | 文本级语音提示，按状态生成不同语气 |
| 疲劳算法 | 多维生理指标加权评估系统 |

### 1.2 核心调用链路

```
处方生成链路：
前端问诊表单 → FastAPI /api/generate_prescription
  → 读取患者档案 + 影像风险等级
  → validators 检测红旗症状（高风险则拦截）
  → RAG 检索知识上下文（knowledge/actions.json + 向量索引）
  → safety 模块过滤/降阶高风险动作
  → DeepSeek 大模型/本地兜底生成处方摘要
  → database 写入 prescriptions + actions
  → 返回处方摘要与动作列表

姿态纠正链路（规则算法）：
前端摄像头/模拟关键点 → FastAPI /api/correct_pose
  → algorithms.py 计算角度和距离
  → 返回 feedback / score / status
  → spatial.py 可同时生成 3D 骨骼 + AR 叠加
  → voice_feedback.py 生成语音提示文本

姿态推理链路（RTMPose ONNX）：
前端 WebSocket/单帧 → /api/pose/infer_frame / /api/pose/ws
  → pose_runtime.py 加载 ONNX 模型推理
  → stream_manager 管理 session 和帧队列
  → 返回关键点 + 反馈 + 置信度

训练打卡与报告链路：
患者训练打卡 → /api/training_checkins
  → 写入 training_checkins 表
  → progress_reports.py 生成周报/月报/custom
  → /trends 日期聚合 /visualization 统计可视化

医患协同链路：
患者绑定医生 → doctor_patient_links（active）
  → 分享处方 → prescription_reviews（pending）
  → 医生审核 → 更新 review 状态
  → 医生/系统提调整建议 → prescription_adjustments（proposed）
  → 患者采纳 → 生成新 prescriptions + actions

疲劳监测链路：
穿戴指标提交 → /api/wearables/metrics
  → fatigue.py 拟合近 20 条历史记录
  → 计算 fatigue_score + risk_level + signals + recommendation
  → 写入 wearable_metrics 表
```

## 2. 系统组件

### 2.1 前端组件

`frontend/` 目录结构（静态 SPA，无构建工具）：

| 文件 | 说明 |
|------|------|
| `index.html` | 主页面（问诊表单 → 处方展示 → 姿态检测 → 训练反馈 → 历史记录） |
| `config.js` | API 地址、Demo 模式开关、动作 ID 映射 |
| `app.js` | 全部交互逻辑：提交问诊、拉取处方、渲染动作、姿态反馈显示 |
| `mock.js` | Demo 模式下的本地处方构造和模拟关键点兜底 |
| `style.css` | 完整样式（问诊、处方、训练反馈、3D 画布） |

演示模式可通过 `APP_CONFIG.setDemoMode(false); location.reload()` 切换到真实后端。

### 2.2 后端组件

`backend/app/` 目录结构（17 个 Python 模块）：

#### 2.2.1 基础设施层

| 模块 | 职责 |
|------|------|
| `main.py` | FastAPI 应用入口，注册 CORS、路由、/health 健康检查、启动数据库 |
| `database.py` | SQLAlchemy 引擎初始化，支持 SQLite / PostgreSQL 切换，SQLite 补列 |
| `models.py` | 12 张表的 ORM 定义（users, patient_profiles, prescriptions, actions, pose_feedback, imaging_reports, training_checkins, wearable_metrics, doctor_patient_links, prescription_reviews, prescription_adjustments, user_feedback） |
| `schema.py` | 全部 Pydantic 请求/响应模型，用于参数校验和 Swagger 文档生成 |
| `auth.py` | JWT 创建与解密，PBKDF2-HMAC-SHA256 密码哈希验证 |
| `cache.py` | Redis 缓存封装（JSON 读写 + 健康检查），未配置时自动禁用 |
| `object_storage.py` | 文件存储抽象层，支持本地文件/ MinIO 双后端切换 |

#### 2.2.2 核心业务层

| 模块 | 职责 |
|------|------|
| `api.py` | 全部 REST API 路由（约 60+ 端点），参数校验、权限控制、业务编排 |
| `crud.py` | 数据库 CRUD 操作封装（create/read/update/delete/query） |
| `knowledge.py` | 动作知识库读取（actions.json）、提示词模板加载、候选动作检索 |
| `doubao.py` | DeepSeek/火山方舟大模型调用，文本输出解析，API 异常本地兜底 |
| `validators.py` | 红旗症状检测（剧烈疼痛/骨折/马尾综合征等）、疼痛部位校验、症状安全过滤 |
| `safety.py` | 动作安全过滤，按风险等级和患者情况降阶或排除高风险动作 |
| `education.py` | 知识科普问答，结合 RAG 检索结果和大模型生成通俗回答 |

#### 2.2.3 姿态与 AI 层

| 模块 | 职责 |
|------|------|
| `algorithms.py` | 规则算法动作纠正（neck_side_bend, wall_squat 等），纯 Python 计算 |
| `pose_runtime.py` | RTMPose ONNX 模型加载、单帧/批量推理、StreamSession 管理器、WebSocket 帧队列 |
| `spatial.py` | 3D 骨骼生成、AR 叠加信息计算、骨架规范定义 |
| `voice_feedback.py` | 语音纠错提示文本生成，按 status/score 自动选择语气和长度 |

#### 2.2.4 数据分析层

| 模块 | 职责 |
|------|------|
| `fatigue.py` | 多维疲劳评估算法，系统构建近 20 条历史指标趋势分析 |
| `progress_reports.py` | 训练进度报告生成（weekly / monthly / custom），含趋势摘要和动作统计 |
| `action_metadata.py` | 动作元数据增强（分类、阶段、目标肌群、器材、常见错误、正确提示等） |

#### 2.2.5 协同与管理层

| 模块 | 职责 |
|------|------|
| `collaboration.py` | 医患关系管理、处方审核流程、处方调整建议（医生/系统）、调整采纳执行 |
| `admin_management.py` | 管理端看板统计、用户列表、反馈管理和 CRUD |
| `test_reports.py` | 自动化测试报告输入输出，支持 Markdown / JSON 格式 |

#### 2.2.6 其他后端文件

| 文件 | 说明 |
|------|------|
| `rag.py` | RAG 向量检索（Chromadb / Qdrant / local JSON），知识索引构建与检索 |
| `main.py` | FastAPI 应用启动入口，`uvicorn app.main:app` |
| 根目录 `backend/run_backend_tests.py` | 全量后端自动化测试脚本 |

### 2.3 知识库与附件

| 路径 | 说明 |
|------|------|
| `knowledge/actions.json` | 结构化康复动作库，当前 16 个动作（颈部/肩部/腰部/膝/踝/髋） |
| `knowledge/prompt_template.txt` | DeepSeek 提示词模板 |
| `knowledge/rag_store/` | RAG 向量索引持久化目录 |
| `models/` | RTMPose ONNX 模型文件 |
| `backend/uploads/` | 开发阶段影像报告文件存储 |

## 3. 数据模型设计

详见 [`db.md`](db.md) 数据库设计文档，共 **12 张表**（11 张业务表 + 1 张用户反馈表）：

| 表名 | 核心用途 | 关键交互模块 |
|------|----------|-------------|
| users | 用户身份与角色 | auth.py, api.py |
| patient_profiles | 患者档案 | api.py, crud.py |
| prescriptions | 康复处方 | api.py, crud.py, doubao.py |
| actions | 动作明细（处方快照） | api.py, crud.py |
| pose_feedback | 姿态纠正记录 | api.py, algorithms.py |
| imaging_reports | 影像报告 | api.py, validators.py |
| training_checkins | 训练打卡 | api.py, progress_reports.py |
| wearable_metrics | 穿戴指标与疲劳 | api.py, fatigue.py |
| doctor_patient_links | 医患绑定 | api.py, collaboration.py |
| prescription_reviews | 处方审核 | api.py, collaboration.py |
| prescription_adjustments | 处方调整 | api.py, collaboration.py |
| user_feedback | 用户反馈 | api.py, admin_management.py |

## 4. API 接口清单（全部 60+ 端点）

### 4.1 认证接口

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/register` | 无 | 注册账号 |
| POST | `/api/login` | 无 | 登录返回 JWT |

### 4.2 患者档案

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/patient_profiles` | 用户 | 查询所有档案 |
| POST | `/api/patient_profiles` | 用户 | 创建档案 |
| GET | `/api/patient_profiles/{id}` | 用户 | 查单个档案 |
| PUT | `/api/patient_profiles/{id}` | 用户 | 更新档案 |
| DELETE | `/api/patient_profiles/{id}` | 用户 | 删除档案 |

### 4.3 影像报告

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/imaging_reports` | 用户 | 查询报告列表（可按档案过滤） |
| POST | `/api/imaging_reports` | 用户 | 上传报告（支持 png/jpg/pdf/txt） |
| GET | `/api/imaging_reports/{id}` | 用户 | 查单条报告详情 |

### 4.4 处方生成与查询

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/generate_prescription` | 可选 | 生成个性化康复处方 |
| GET | `/api/prescriptions` | 用户 | 历史处方列表 |
| GET | `/api/prescriptions/{id}` | 用户 | 单条处方详情 |
| GET | `/api/prescriptions/{id}/export` | 用户 | 导出处方（md/txt/json） |

### 4.5 动作知识库

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/actions` | 无 | 查询康复动作库 |

### 4.6 知识问答与 RAG

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/knowledge/articles` | 无 | 知识文章列表 |
| GET | `/api/knowledge/rag/status` | 用户 | RAG 索引状态 |
| POST | `/api/knowledge/rag/reindex` | 管理员 | 触发索引重建 |
| POST | `/api/knowledge/rag/search` | 用户 | 语义搜索 |
| POST | `/api/knowledge/qa` | 用户 | 科普问答（RAG + 大模型） |

### 4.7 训练打卡

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/training_checkins` | 用户 | 查询打卡记录 |
| POST | `/api/training_checkins` | 用户 | 新增打卡 |
| GET | `/api/training_checkins/trends` | 用户 | 趋势数据聚合 |
| GET | `/api/training_checkins/visualization` | 用户 | 可视化统计数据 |
| GET | `/api/training_checkins/report` | 用户 | 进度报告 |
| GET | `/api/training_checkins/report/export` | 用户 | 导出报告（md/txt/json） |
| GET | `/api/training_checkins/{id}` | 用户 | 单条打卡详情 |
| PUT | `/api/training_checkins/{id}` | 用户 | 更新打卡 |
| DELETE | `/api/training_checkins/{id}` | 用户 | 删除打卡 |

### 4.8 姿态纠正与推理

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/correct_pose` | 无 | 规则算法动作纠正 |
| GET | `/api/pose/status` | 用户 | RTMPose 模型状态 |
| POST | `/api/pose/infer_frame` | 用户 | 单帧姿态推理 |
| POST | `/api/pose/infer_batch` | 用户 | 批量帧推理（最多 30 帧） |
| GET | `/api/pose/stream/session` | 用户 | 创建流式会话 |
| DELETE | `/api/pose/stream/session/{id}` | 用户 | 关闭流式会话 |
| WS | `/api/pose/ws` | 无 | WebSocket 实时推理 |
| POST | `/api/pose/webrtc/offer` | 用户 | WebRTC 会话 |

### 4.9 3D 骨骼与 AR

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/visual/skeleton/spec` | 用户 | 骨骼结构规范 |
| POST | `/api/visual/skeleton/frame` | 用户 | 单帧 3D 骨骼数据 |
| POST | `/api/visual/ar/overlay` | 用户 | AR 叠加提示 |

### 4.10 语音纠错提示

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/voice/cue` | 用户 | 生成语音提示文本 |

### 4.11 穿戴设备与疲劳监测

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/wearables/metrics` | 用户 | 提交穿戴指标 |
| GET | `/api/wearables/metrics` | 用户 | 查询指标记录 |
| GET | `/api/wearables/fatigue/status` | 用户 | 当前疲劳状态 |

### 4.12 医患协同

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/doctor_links` | 用户 | 绑定医生 |
| GET | `/api/doctor/patients` | 医生 | 医生名下患者列表 |
| POST | `/api/prescriptions/{id}/reviews/share` | 用户 | 分享处方给医生 |
| GET | `/api/doctor/reviews` | 医生 | 待审核处方列表 |
| PUT | `/api/doctor/reviews/{id}` | 医生 | 提交审核意见 |
| POST | `/api/doctor/reviews/{id}/adjustments` | 医生 | 医生提出调整建议 |
| POST | `/api/prescriptions/{id}/adjustments/auto` | 用户 | 系统自动调整建议 |
| GET | `/api/prescription_adjustments` | 用户 | 查看待决策调整 |
| POST | `/api/prescription_adjustments/{id}/decision` | 用户 | 采纳/拒绝调整 |

### 4.13 用户反馈

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/feedback` | 可选 | 用户提交反馈 |

### 4.14 后台管理

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/api/admin/dashboard` | 管理员 | 管理看板 |
| GET | `/api/admin/users` | 管理员 | 用户列表（搜索/分页） |
| GET | `/api/admin/feedback` | 管理员 | 反馈列表筛选 |
| PUT | `/api/admin/feedback/{id}` | 管理员 | 更新反馈状态 |
| GET | `/api/admin/actions` | 管理员 | 动作库管理（搜索/过滤） |
| POST | `/api/admin/actions` | 管理员 | 新增动作 |
| GET | `/api/admin/actions/meta` | 管理员 | 动作库元信息 |
| GET | `/api/admin/actions/{id}` | 管理员 | 查单个动作 |
| PUT | `/api/admin/actions/{id}` | 管理员 | 更新动作 |
| DELETE | `/api/admin/actions/{id}` | 管理员 | 删除动作 |
| GET | `/api/admin/test_report` | 管理员 | 自动化测试报告 |

### 4.15 部署与测试

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health` | 无 | 快速健康检查 |
| GET | `/ready` | 无 | 完整就绪检查 |
| GET | `/api/deployment/info` | 无 | 部署环境信息 |
| POST | `/api/test_deepseek` | 无 | DeepSeek API 连通性测试 |
| POST | `/api/test_doubao` | 无 | 兼容别名（同上） |

## 5. 认证与鉴权设计

- **注册**：PBKDF2-HMAC-SHA256 加盐哈希密码，写入 `users` 表
- **登录**：验证密码 → 生成自定义 JWT（`create_access_token(user_id, account)`）
- **鉴权方式**：`Authorization: Bearer <token>` 请求头
- **角色体系**：

| 装饰器 | 允许角色 | 说明 |
|--------|---------|------|
| `get_current_user` | user / doctor / admin | 标准用户鉴权 |
| `get_doctor_user` | doctor / admin | 医生级权限 |
| `get_admin_user` | admin | 管理级权限 |
| `get_optional_user` | 无/任意 | 可选的登录态（反馈、处方生成匿名可用） |

- **管理账户**：由环境变量 `ADMIN_ACCOUNTS` 控制（逗号分隔），匹配时 role 提升为 admin
- **医生账户**：由环境变量 `DOCTOR_ACCOUNTS` 控制

## 6. 安全设计

### 6.1 处方安全

- **红旗症状检测**（`validators.py`）：检测 10+ 高风险关键词（剧烈疼痛、麻木、骨折、肿瘤、马尾综合征等），检测到则阻止处方生成，返回 `code: "red_flag_detected"`。
- **影像风险拦截**：处方生成前读取 `imaging_reports` 风险等级，`high` 时阻止。
- **动作安全过滤**（`safety.py`）：根据患者疼痛部位和禁忌症筛选/降阶候选动作。
- **大模型兜底**：API 调用失败时使用本地安全兜底摘要。

### 6.2 数据安全

- 密码不存储明文，使用 PBKDF2-HMAC-SHA256 加盐哈希。
- JWT Secret 通过环境变量配置，不提交代码仓库。
- `.env` 存储私密配置，`.env.sample` 存储示例占位符。
- `/api/deployment/info` 不返回 API Key 或 JWT Secret。

### 6.3 权限隔离

- 所有按用户隔离的查询均以 `current_user.id` 作为过滤条件。
- 医生必须与患者建立 `active` 关系后才能审核处方。
- 管理端接口仅限 `admin` 角色访问（`ADMIN_ACCOUNTS` 环境变量控制）。

## 7. 知识库与提示词设计

### 7.1 动作知识库

位置：`knowledge/actions.json`，结构化 JSON 格式。

当前覆盖 16 个康复动作，涵盖身体部位：

| 部位 | 动作数 |
|------|--------|
| 颈部 | 3 个 |
| 肩部 | 2 个 |
| 腰部 | 3 个 |
| 膝关节 | 2 个 |
| 踝关节 | 2 个 |
| 髋部 | 2 个 |
| 其他 | 2 个 |

每个动作包含完整字段：id, name, target_conditions, body_regions, sets, reps, category, difficulty_level, stage, target_muscles, equipment, demo_media, image, video_url, video_hint, image_hint, steps, common_mistakes, correct_cues, risk_level, frequency, description, contraindications, progression, regression。

### 7.2 提示词模板

位置：`knowledge/prompt_template.txt`

将用户信息和知识库候选动作组织为上下文，要求模型输出结构化 JSON，包含：
- `summary`：总体康复目标和训练原则
- `actions`：推荐动作列表
- `warnings`：风险提示
- `follow_up`：复查或调整建议

### 7.3 RAG 向量检索

支持三后端，通过 `RAG_VECTOR_PROVIDER` 环境变量切换：

| Provider | 持久化 | 适用场景 |
|----------|--------|----------|
| chroma | `knowledge/rag_store/chroma` | 单机部署 |
| qdrant | `QDRANT_URL` / `QDRANT_PATH` | 生产扩展 |
| local | JSON 索引 | 测试和演示 |

## 8. 缓存与存储设计

### 8.1 Redis 缓存（`cache.py`）

- 封装 JSON 读写：`cache_get_json()` / `cache_set_json()`
- 当前缓存键：`actions:v1`（动作库列表）
- 管理员修改动作后自动 `cache_delete("actions:v1")`
- 可通过 `/ready` 和 `/api/deployment/info` 查询健康状态
- `REDIS_URL` 未配置时自动返回 `disabled`，不影响本地开发

### 8.2 对象存储（`object_storage.py`）

- 支持本地文件 / MinIO 双后端
- 切换方式：环境变量 `OBJECT_STORAGE_BACKEND=local|minio`
- 影像报告文件路径规则：`imaging_reports/{user_id}/{sha256_digest[:16]}{extension}`
- 允许上传类型：png, jpg, jpeg, pdf, txt（≤ 5MB）

## 9. 部署与配置

### 9.1 环境变量

关键环境变量（通过 `.env` 或 docker-compose）：

```env
# 数据库
DATABASE_URL=sqlite:///backend/database.db
# 或 postgresql+psycopg://kangjian:kangjian_password@postgres:5432/kangjian_atlas

# 大模型
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DEEPSEEK_MODEL_ID=your_model_id

# Redis（可选）
REDIS_URL=redis://redis:6379/0

# 对象存储（开发可选）
OBJECT_STORAGE_BACKEND=local

# RAG 向量存储
RAG_VECTOR_PROVIDER=auto

# 权限账户
ADMIN_ACCOUNTS=admin
DOCTOR_ACCOUNTS=

# 前端 CORS
CORS_ORIGINS=http://localhost:8080,http://localhost:8000

# 应用
APP_ENV=development
DEMO_MODE=false
JWT_SECRET=your_jwt_secret
```

### 9.2 启动方式

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Docker Compose 部署（已提供 `docker-compose.yml`）：
```bash
docker-compose up -d
```

## 10. 后续扩展

- 引入 Alembic 管理数据库迁移，替代 `_ensure_sqlite_columns()` 补列逻辑。
- 增加用户登录、患者档案和医生审核流程的前端界面。
- 接入 MediaPipe Pose 从前端真实视频流提取关键点（当前为模拟关键点演示模式）。
- 扩展更多动作规则算法和支持更多标准动作模板。
- 增加处方导出 PDF、训练打卡日历、数据统计看板模块。
- 增加自动化测试覆盖率和 CI/CD 集成。
- 增加审计日志表，记录管理操作和敏感数据访问。

## 11. 模块依赖关系总结

```text
api.py ── 入口编排层，依赖所有其他模块
  ├── schema.py（数据校验）
  ├── auth.py + database.py + models.py + crud.py（基础设施）
  ├── knowledge.py + doubao.py + rag.py（AI/知识）
  ├── validators.py + safety.py（安全）
  ├── algorithms.py + pose_runtime.py + spatial.py（姿态）
  ├── voice_feedback.py + fatigue.py（配套体验）
  ├── progress_reports.py + collaboration.py + admin_management.py（业务模块）
  ├── cache.py + object_storage.py（基础设施）
  └── education.py + test_reports.py + action_metadata.py（辅助模块）
```
