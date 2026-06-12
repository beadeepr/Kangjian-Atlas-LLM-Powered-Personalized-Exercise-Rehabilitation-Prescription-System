# 后端接口文档

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. API 概览

当前后端通过 FastAPI 提供以下核心接口：

- `GET /health`
- `POST /api/generate_prescription`
- `POST /api/correct_pose`

基准 URL 示例：`http://localhost:8000`

## 2. 健康检查

### 2.1 GET /health

- 描述：检查后台服务是否正常运行。
- 请求参数：无。
- 响应示例：

```json
{
  "status": "ok"
}
```

- 状态码：200

## 3. 生成康复处方

### 3.1 POST /api/generate_prescription

- 描述：根据患者主诉生成初步康复处方。
- 请求头：
  - `Content-Type: application/json`
- 请求体示例：

```json
{
  "name": "张三",
  "age": 32,
  "symptoms": "颈部疼痛，活动受限",
  "history": "长期低头工作"
}
```

- 响应体示例：

```json
{
  "summary": "基于主诉 颈部疼痛，活动受限 的初步康复处方（示例）",
  "actions": [
    {
      "name": "颈部侧屈拉伸",
      "sets": 3,
      "reps": 10,
      "note": "温和进行，出现强烈疼痛停止"
    }
  ]
}
```

- 返回模型：`PrescriptionResponse`

### 3.2 请求与响应模型定义

```python
class PrescriptionRequest(BaseModel):
    name: Optional[str]
    age: Optional[int]
    symptoms: str
    history: Optional[str]

class ActionItem(BaseModel):
    name: str
    sets: int
    reps: int
    note: Optional[str]

class PrescriptionResponse(BaseModel):
    summary: str
    actions: List[ActionItem]
```

### 3.3 业务说明

- `symptoms` 为必需字段，当前实现要求必须提供。
- 后续实现中，可接入 LLM 或专家系统生成更准确康复动作。
- 响应中包含动作清单和说明信息。

## 4. 姿势纠正接口

### 4.1 POST /api/correct_pose

- 描述：提交姿态数据，获取纠正反馈。
- 请求头：
  - `Content-Type: application/json`
- 请求体示例：

```json
{
  "keypoints": [[0.1, 0.2], [0.3, 0.4]]
}
```

- 响应体示例：

```json
{
  "feedback": [
    "请收下巴，头部前屈过多。",
    "膝盖角度合适，继续保持。"
  ]
}
```

- 返回模型：`PoseCorrectionResponse`

### 4.2 请求与响应模型定义

```python
class PoseCorrectionRequest(BaseModel):
    keypoints: Optional[List[List[float]]]

class PoseCorrectionResponse(BaseModel):
    feedback: List[str]
```

### 4.3 业务说明

- 当前示例实现仅返回静态反馈。
- 后续可在后端引入姿态分析模块、深度学习模型或图像处理服务。
- 若使用图像数据，建议改为接收 base64 或 multipart/form-data。

## 5. 其他说明

- FastAPI 自动生成 Swagger 文档：`http://localhost:8000/docs`
- 如果部署到生产环境，可通过环境变量配置不同的 `apiBase`。
- 建议后续添加认证与授权机制，保护接口访问。

## 6. 扩展建议

### 6.1 建议添加的接口

- `POST /api/login`：用户登录
- `POST /api/register`：用户注册
- `GET /api/patients/{id}`：获取患者详情
- `GET /api/prescriptions/{id}`：获取处方详情
- `POST /api/prescriptions/{id}/feedback`：提交康复反馈
- `POST /api/resources`：管理康复资源

### 6.2 错误处理

- 使用 FastAPI `HTTPException` 返回标准错误码和提示信息。
- 常见错误：400 参数错误、401 未授权、404 未找到、500 服务异常。

### 6.3 API 文档维护

- 建议编写 `OpenAPI` 文档，并保持与实现同步。
- 在接口版本迭代时，使用 `v1`、`v2` 等路径版本化。
