# 后端接口文档

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. API 概览

当前后端通过 FastAPI 提供以下接口：

- `GET /health`
- `GET /api/actions`
- `POST /api/generate_prescription`
- `GET /api/prescriptions`
- `GET /api/prescriptions/{prescription_id}`
- `POST /api/correct_pose`
- `POST /api/test_doubao`

基准 URL 示例：

```text
http://localhost:8000
```

FastAPI 自动文档：

```text
http://localhost:8000/docs
```

## 2. 环境配置

后端通过 `.env` 自动读取豆包/火山方舟 API 配置：

```env
DOUBAO_API_KEY=your_api_key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_ID=your_model_id
```

说明：

- `.env` 为本地私密配置，已加入 `.gitignore`。
- `.env.sample` 只保留占位示例，不应写入真实 API Key。
- 未配置或调用失败时，处方生成接口会返回本地兜底摘要，保证演示链路不中断。

## 3. 健康检查

### 3.1 GET /health

描述：检查后端服务是否正常运行。

请求参数：无。

响应示例：

```json
{
  "status": "ok"
}
```

测试命令：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## 4. 动作知识库接口

### 4.1 GET /api/actions

描述：返回结构化康复动作知识库。

响应示例：

```json
[
  {
    "id": "neck_side_bend",
    "name": "颈部侧屈拉伸",
    "sets": 3,
    "reps": 1,
    "note": "坐姿或站姿，缓慢将头向一侧倾斜，停留20秒，左右交替完成。",
    "description": "坐姿或站姿，缓慢将头向一侧倾斜，停留20秒，左右交替完成。",
    "frequency": "每日1次",
    "contraindications": "颈椎不稳、急性炎症期、牵拉时放射痛明显者禁忌。",
    "progression": "疼痛评分低于3分时，可逐步延长至30秒。",
    "regression": "不适时减少侧屈幅度，保持轻微牵拉感即可。",
    "body_regions": ["颈部"],
    "target_conditions": ["颈椎病", "肩颈疼痛"]
  }
]
```

测试命令：

```powershell
Invoke-RestMethod http://localhost:8000/api/actions
```

## 5. 生成康复处方

### 5.1 POST /api/generate_prescription

描述：根据用户主诉、既往病史、疼痛部位和活动度评分，从知识库检索动作，并调用豆包大模型生成康复处方摘要。

请求头：

```text
Content-Type: application/json
```

请求体示例：

```json
{
  "name": "张三",
  "age": 32,
  "symptoms": "腰痛，久坐后加重",
  "history": "长期伏案工作",
  "pain_regions": ["腰部"],
  "mobility_score": 5
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string/null | 否 | 用户姓名 |
| `age` | number/null | 否 | 用户年龄 |
| `symptoms` | string | 是 | 主诉或症状描述 |
| `history` | string/null | 否 | 既往病史 |
| `pain_regions` | string[]/null | 否 | 疼痛部位，如 `["颈部", "腰部"]` |
| `mobility_score` | number/null | 否 | 活动度自评，建议 1-10 |

响应体示例：

```json
{
  "id": 1,
  "patient_name": "张三",
  "patient_age": 32,
  "summary": "患者存在腰痛和久坐后加重表现，建议从低强度伸展和核心稳定训练开始...",
  "actions": [
    {
      "id": "mckenzie_press_up",
      "name": "麦肯基俯卧撑",
      "sets": 3,
      "reps": 10,
      "note": "俯卧位双手撑地，骨盆尽量贴近床面...",
      "description": "俯卧位双手撑地，骨盆尽量贴近床面，缓慢伸直肘部抬起上半身，腰部保持可耐受的伸展。",
      "frequency": "每日1-2次",
      "contraindications": "伸展后腿痛加重、急性腰椎骨折、马尾综合征风险者禁忌。",
      "progression": "若疼痛向腰部集中且无下肢症状加重，可逐步增加次数。",
      "regression": "先从俯卧放松或肘撑俯卧开始。",
      "body_regions": ["腰部"],
      "target_conditions": ["腰椎间盘突出", "腰痛"]
    }
  ],
  "raw_response": {
    "model_text": "...",
    "model_json": null,
    "raw": null
  }
}
```

测试命令：

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/generate_prescription `
  -ContentType "application/json" `
  -Body '{"name":"测试","age":30,"symptoms":"腰痛，久坐后加重","history":"无","pain_regions":["腰部"],"mobility_score":5}' |
  ConvertTo-Json -Depth 10
```

### 5.2 请求与响应模型

```python
class PrescriptionRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    symptoms: str
    history: Optional[str] = None
    pain_regions: Optional[List[str]] = None
    mobility_score: Optional[int] = None

class PrescriptionResponse(BaseModel):
    id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    summary: str
    actions: List[ActionItem]
    raw_response: Optional[dict] = None
```

### 5.3 业务说明

- `symptoms` 为必需字段。
- 后端会根据 `symptoms` 和 `pain_regions` 从 `knowledge/actions.json` 中选择候选动作。
- 大模型提示词要求模型只从候选动作中选择，不编造动作。
- 豆包调用失败时，接口使用本地兜底摘要，避免生成流程中断。
- 处方、动作列表和模型原始返回会保存到 SQLite。

## 6. 查询处方记录

### 6.1 GET /api/prescriptions

描述：查询全部处方记录，按创建时间倒序返回。

测试命令：

```powershell
Invoke-RestMethod http://localhost:8000/api/prescriptions | ConvertTo-Json -Depth 10
```

### 6.2 GET /api/prescriptions/{prescription_id}

描述：根据处方 ID 查询单条处方。

示例：

```powershell
Invoke-RestMethod http://localhost:8000/api/prescriptions/1 | ConvertTo-Json -Depth 10
```

错误：

- 不存在时返回 `404 Prescription not found`。

## 7. 姿态纠正接口

### 7.1 POST /api/correct_pose

描述：提交动作 ID、姿态关键点和关键点可见度，返回纠正建议、评分和状态。

请求体示例：

```json
{
  "action_id": "neck_side_bend",
  "keypoints": [[0.5, 0.2, 0.0]],
  "visibility": [1.0],
  "timestamp": 1718179200000
}
```

实际调用时 `keypoints` 建议使用 MediaPipe Pose 的 33 个关键点。当前后端算法支持：

- `neck_side_bend`：颈部侧屈拉伸
- `wall_squat`：靠墙静蹲

响应示例：

```json
{
  "feedback": ["左侧拉伸良好，可以再低一点点。"],
  "score": 85,
  "status": "ok"
}
```

状态说明：

| status | 说明 |
|--------|------|
| `ok` | 动作基本标准 |
| `warning` | 动作需要调整 |
| `error` | 关键点不足、遮挡严重或动作暂未支持 |

### 7.2 请求与响应模型

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

### 7.3 测试命令

```powershell
$points = @()
for ($i = 0; $i -lt 33; $i++) { $points += ,@(0.0, 0.0, 0.0) }
$points[0] = @(0.5, 0.2, 0.0)
$points[7] = @(0.45, 0.2, 0.0)
$points[8] = @(0.58, 0.2, 0.0)
$points[11] = @(0.45, 0.35, 0.0)
$points[12] = @(0.55, 0.35, 0.0)

$body = @{
  action_id = "neck_side_bend"
  keypoints = $points
  visibility = @(1.0) * 33
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/correct_pose `
  -ContentType "application/json" `
  -Body $body
```

## 8. 豆包连通性测试

### 8.1 POST /api/test_doubao

描述：使用内置测试数据调用豆包处方生成逻辑，确认 `.env`、模型 ID 和调用链路是否可用。

测试命令：

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/test_doubao |
  ConvertTo-Json -Depth 10
```

响应示例：

```json
{
  "status": "success",
  "summary": {
    "text": "...",
    "json": null,
    "raw": {}
  }
}
```

## 9. 错误处理

- 请求缺少 `symptoms`：返回 `400 symptoms required`。
- 查询不存在的处方：返回 `404 Prescription not found`。
- 豆包未配置或调用失败：处方接口走本地兜底摘要；`/api/test_doubao` 会返回错误详情。
- 姿态关键点数量不足：返回 `status=error` 和对应反馈。
- 动作算法暂未支持：返回 `status=error` 和“该动作算法尚未实现”。

## 10. 后续扩展建议

- 增加认证与用户权限。
- 增加患者档案和医生审核流程。
- 引入 Alembic 管理数据库迁移。
- 接入前端 MediaPipe，从真实视频流提取关键点。
- 增加自动化测试和接口回归测试。
- 扩展动作算法覆盖更多知识库动作。
