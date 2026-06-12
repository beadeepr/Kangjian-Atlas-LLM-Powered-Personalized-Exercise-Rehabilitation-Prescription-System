# 架构与类设计文档

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. 技术架构概述

项目采用前后端分离架构，当前已经完成可运行的 MVP 链路：

- 前端：静态 HTML + CSS + JavaScript，负责用户信息采集、康复处方展示、摄像头控制和动作反馈展示。
- 后端：FastAPI，提供处方生成、动作知识库查询、姿态纠正、历史处方查询和大模型连通性测试接口。
- 数据存储：SQLite + SQLAlchemy，保存处方、处方动作和姿态反馈记录。
- 知识库：`knowledge/actions.json` 使用 JSON 结构化存储康复动作、适用症状、组数、频次、禁忌症和进阶/降阶规则。
- AI/LLM 层：`backend/app/doubao.py` 通过火山方舟/豆包 OpenAI 兼容接口生成处方摘要，并在接口异常时使用本地安全兜底摘要。
- 姿态纠正层：`backend/app/algorithms.py` 基于前端传入的姿态关键点计算角度和距离，返回动作反馈、评分和状态。

整体调用链路：

```text
前端问诊表单
  -> FastAPI /api/generate_prescription
  -> 知识库检索候选动作
  -> 组装提示词模板
  -> 调用豆包大模型
  -> 解析模型输出并保存 SQLite
  -> 返回处方摘要与动作列表
```

姿态纠正链路：

```text
前端摄像头/模拟关键点
  -> FastAPI /api/correct_pose
  -> analyze_pose(action_id, keypoints, visibility)
  -> 规则算法生成 feedback/score/status
  -> 保存反馈记录并返回前端
```

## 2. 系统组件

### 2.1 前端组件

- `frontend/index.html`
  - 包含用户信息采集、疼痛部位选择、活动度评分、处方展示、训练反馈页面。
  - 提供摄像头区域和模拟姿态检测按钮。

- `frontend/config.js`
  - 配置 API 地址、Demo 模式、动作目录和动作 ID 映射。
  - 可通过 `APP_CONFIG.setDemoMode(false); location.reload();` 切换到真实后端。

- `frontend/app.js`
  - 提交问诊信息到 `/api/generate_prescription`。
  - 拉取历史处方 `/api/prescriptions`。
  - 发送动作关键点到 `/api/correct_pose`。
  - 渲染处方动作、反馈分数和动作状态。

- `frontend/mock.js`
  - Demo 模式下构造本地处方和模拟关键点。
  - 后端不可用时提供兜底展示能力。

- `frontend/style.css`
  - 定义问诊、处方、训练反馈页面样式。

### 2.2 后端组件

- `backend/app/main.py`
  - 创建 FastAPI 应用。
  - 注册 CORS、API 路由和 `/health` 健康检查。
  - 启动时初始化 SQLite 数据库。

- `backend/app/api.py`
  - 定义主要接口：
    - `POST /api/generate_prescription`
    - `GET /api/prescriptions`
    - `GET /api/prescriptions/{id}`
    - `GET /api/actions`
    - `POST /api/correct_pose`
    - `POST /api/test_doubao`

- `backend/app/crud.py`
  - 实现处方生成、数据库写入、动作记录保存、姿态反馈保存。
  - 根据用户主诉和疼痛部位从知识库中选择候选动作。

- `backend/app/doubao.py`
  - 自动读取根目录 `.env` 或 `backend/.env`。
  - 调用豆包/火山方舟 OpenAI 兼容接口。
  - 解析模型文本和 JSON 输出，敏感字段脱敏。
  - API 异常时返回本地兜底处方摘要。

- `backend/app/knowledge.py`
  - 读取动作知识库和提示词模板。
  - 根据症状关键词、疼痛部位和动作标签进行基础检索。
  - 提供本地处方摘要渲染能力。

- `backend/app/algorithms.py`
  - 实现动作关键点分析。
  - 当前支持 `neck_side_bend` 和 `wall_squat` 两类动作反馈。
  - 使用 Python 标准库计算角度和距离，不依赖额外数学库。

- `backend/app/models.py`
  - 定义 SQLAlchemy ORM：
    - `PrescriptionModel`
    - `ActionModel`
    - `PoseFeedbackModel`

- `backend/app/schema.py`
  - 定义请求/响应数据模型，用于参数校验和 Swagger 文档生成。

- `backend/app/database.py`
  - 配置 SQLite 连接。
  - 初始化表结构。
  - 对开发阶段旧表自动补充 `raw_response` 字段。

## 3. 数据模型设计

### 3.1 PrescriptionModel

保存一次康复处方生成记录：

- `id`：处方 ID
- `patient_name`：患者姓名
- `patient_age`：患者年龄
- `symptoms`：主诉
- `history`：既往病史
- `summary`：处方摘要
- `raw_response`：大模型原始返回与解析结果
- `created_at` / `updated_at`：记录时间

### 3.2 ActionModel

保存处方中推荐的动作：

- `id`：动作记录 ID
- `prescription_id`：所属处方
- `name`：动作名称
- `sets`：组数
- `reps`：次数
- `note`：动作说明或注意事项

### 3.3 PoseFeedbackModel

保存姿态纠正请求和反馈：

- `id`：反馈记录 ID
- `request_data`：动作 ID、关键点、可见度和时间戳
- `feedback`：纠正建议列表
- `created_at`：记录时间

## 4. API 数据契约

### 4.1 处方生成请求

```python
class PrescriptionRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    symptoms: str
    history: Optional[str] = None
    pain_regions: Optional[List[str]] = None
    mobility_score: Optional[int] = None
```

### 4.2 动作条目

```python
class ActionItem(BaseModel):
    id: Optional[str] = None
    name: str
    sets: int
    reps: int
    note: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    contraindications: Optional[str] = None
    progression: Optional[str] = None
    regression: Optional[str] = None
    body_regions: Optional[List[str]] = None
    target_conditions: Optional[List[str]] = None
```

### 4.3 姿态纠正请求与响应

```python
class PoseCorrectionRequest(BaseModel):
    action_id: Optional[str] = None
    keypoints: Optional[List[List[float]]] = None
    visibility: Optional[List[float]] = None
    timestamp: Optional[int] = None

class PoseCorrectionResponse(BaseModel):
    feedback: List[str]
    score: int = 0
    status: str = "warning"
```

## 5. 知识库与提示词设计

知识库位于 `knowledge/actions.json`，当前覆盖颈部、肩部、腰部、膝关节等常见康复场景。每个动作包含：

- 动作 ID 和名称
- 适用病症和身体部位
- 组数、次数、频次
- 动作描述
- 禁忌症
- 进阶条件
- 降阶方案

提示词模板位于 `knowledge/prompt_template.txt`，将用户信息和知识库候选动作组织为上下文，并要求模型输出结构化 JSON，包含：

- `summary`：总体康复目标和训练原则
- `actions`：推荐动作列表
- `warnings`：风险提示
- `follow_up`：复查或调整建议

## 6. 部署与配置

后端使用 `.env` 配置豆包 API：

```env
DOUBAO_API_KEY=your_api_key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_ID=your_model_id
```

`.env` 已加入 `.gitignore`，提交代码时只提交 `.env.sample`。

启动后端：

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 7. 后续扩展

- 引入 Alembic 管理数据库迁移。
- 增加用户登录、患者档案和医生审核流程。
- 接入 MediaPipe，在前端从真实视频流提取关键点。
- 扩展更多动作算法和标准动作模板。
- 增加自动化测试和接口回归测试脚本。
- 增加处方导出、训练打卡、数据统计和可视化模块。

## 8. 总结

当前系统已完成可运行 MVP：前端可提交问诊信息，后端可基于知识库和豆包大模型生成康复处方，SQLite 可保存处方记录，姿态纠正接口可返回动作反馈、评分和状态。后续工作重点是完善真实视频关键点提取、增加测试覆盖和优化前端演示体验。
