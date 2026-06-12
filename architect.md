# 架构与类设计文档

## 项目名称
康健图谱 — 基于大模型的个性化运动康复处方生成系统

## 1. 技术架构概述

项目采用前后端分离架构：

- 前端：静态页面 + JavaScript，负责用户输入、摄像头采集、展示结果。
- 后端：FastAPI，负责REST API提供处方生成、姿势纠正等服务。
- 数据存储：当前项目为MVP阶段，未引入数据库，后期建议采用关系型数据库（如PostgreSQL、MySQL）或轻量级SQLite。
- AI/LLM层：当前后端接口为占位实现，未来可接入大模型推理服务或外部API。

## 2. 系统组件

### 2.1 前端组件

- `index.html`
  - 页面结构：标题、问诊表单、摄像头预览、反馈结果区。
  - 通过 `app.js` 与后端 API 交互。

- `app.js`
  - `generate_prescription`：向 `/api/generate_prescription` 发起 POST 请求。
  - `startCam`：调用浏览器摄像头并输出到 `<video>`。
  - `sendFrame`：采集当前帧并调用 `/api/correct_pose`。

- `style.css`
  - 基础布局与样式，提供简洁可读的页面展示。

### 2.2 后端组件

- `backend/app/main.py`
  - 创建 FastAPI 应用实例。
  - 注册 API 路由前缀 `/api`。
  - 提供健康检查接口 `/health`。

- `backend/app/api.py`
  - 定义业务路由：
    - `POST /api/generate_prescription`
    - `POST /api/correct_pose`
  - 当前实现为占位版本，返回示例数据。

- `backend/app/schema.py`
  - 定义请求与响应数据模型：
    - `PrescriptionRequest`
    - `PrescriptionResponse`
    - `PoseCorrectionRequest`
    - `PoseCorrectionResponse`

- `backend/app/models.py`
  - 预留数据库模型位置。
  - 当前未实现具体 ORM。

## 3. 类设计

### 3.1 后端类设计

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

class PoseCorrectionRequest(BaseModel):
    keypoints: Optional[List[List[float]]]

class PoseCorrectionResponse(BaseModel):
    feedback: List[str]
```

这些类定义了后端 API 的输入输出契约，便于类型校验和自动生成文档。

### 3.2 前端模块设计

前端主文件 `app.js` 的功能模块：

- `apiBase`：API 基础地址配置。
- `submit` 按钮事件：负责发送问诊信息并显示返回结果。
- 摄像头模块：
  - `startCam`：请求视频权限并渲染视频流。
  - `sendFrame`：将当前视频帧转换为图像，并发送矫正请求。

后续可将前端逻辑拆分为：
- `ui/form.js`：问诊表单模块
- `ui/camera.js`：摄像头控制模块
- `ui/result.js`：结果渲染模块

## 4. 推荐架构扩展

### 4.1 后端扩展

- 引入数据库：使用 SQLAlchemy + Alembic 实现数据持久化。
- 设计领域模型：
  - Patient
  - Prescription
  - Action
  - Therapist
  - PoseFeedback
- 增加服务层：将核心业务逻辑从路由中抽离。
- 集成 LLM：封装 `LLMService`，负责提示词构建与调用。

### 4.2 前端扩展

- 使用现代框架：如 React、Vue 或 Svelte，实现组件化界面。
- 引入状态管理：用于管理患者信息、处方结果、摄像头状态等。
- 增加路由：支持登录、患者列表、康复记录、资源页面等。

### 4.3 部署架构

- 后端部署：FastAPI + Uvicorn 或 Gunicorn。
- 前端部署：静态文件托管于 GitHub Pages、Vercel 或自建 Nginx。
- 生产环境建议：使用反向代理（Nginx）、HTTPS、日志收集和监控。

## 5. 总结

当前项目为 MVP 原型，已具备基础前后端交互能力。后续应重点补全数据库、模型推理、用户管理和交互界面。