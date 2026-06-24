# 【康健图谱】——基于大模型的个性化运动康复处方生成系统

## 项目信息

### 项目名称
【康健图谱】——基于大模型的个性化运动康复处方生成系统

### 项目描述
本项目是一个面向运动康复场景的个性化处方生成系统。系统通过前端采集用户主诉、疼痛部位、活动度评分等信息，后端结合结构化康复知识库和 DeepSeek 大模型生成康复处方，并提供基于姿态关键点的动作纠正反馈。

当前版本已完成可运行 MVP：

- FastAPI 后端 API 服务
- SQLite 数据库存储处方和姿态反馈
- DeepSeek/火山方舟大模型集成
- 康复动作知识库与提示词模板
- 处方生成 API
- 姿态纠正 API
- 前端问诊、处方展示和训练反馈页面

---

## 团队成员

| 班级 | 学号 | 姓名 | Github/Gitee用户 | 职责 |
|------|------|------|------------------|------|
| 软件2403 | U202417374 | 王恒 | beadeepr | 项目负责人、架构与后端、大模型集成 |
| 软件2403 | U202417382 | 周硕 | hhh0164 | 算法与测试 |
| 软件2403 | U202417369 | 刘经纬 | lg997 | 前端开发 |

---

## 技术栈

- 后端：FastAPI、Python、SQLAlchemy、SQLite
- 前端：HTML、CSS、JavaScript
- AI/LLM：DeepSeek/火山方舟 OpenAI 兼容接口
- 知识库：JSON 结构化动作库
- 姿态纠正：基于关键点的规则算法

---

## 快速开始

### 1. 克隆项目

```powershell
git clone https://github.com/beadeepr/Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System.git
cd Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System
```

### 2. 创建并激活虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如 PowerShell 阻止脚本执行，可在当前窗口临时允许：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 3. 安装后端依赖

```powershell
pip install -r backend/requirements.txt
```

### 4. 配置 DeepSeek API

复制 `.env.sample` 为 `.env`：

```powershell
Copy-Item .env.sample .env
```

在 `.env` 中填写自己的火山方舟/DeepSeek 配置：

```env
DeepSeek_API_KEY=your_api_key
DeepSeek_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DeepSeek_MODEL_ID=your_model_id
```

注意：

- `.env` 是本地私密文件，已加入 `.gitignore`。
- 不要把真实 API Key 写入 `.env.sample`。
- 如果 DeepSeek 调用失败，后端会使用本地兜底摘要，保证演示流程不中断。

### 5. 启动后端

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务地址：

```text
http://localhost:8000
```

Swagger 文档：

```text
http://localhost:8000/docs
```

### 6. 启动前端

前端为静态页面，可直接打开：

```text
frontend/index.html
```

也可以使用本地静态服务：

```bash
cd frontend
npx http-server
```

前端默认使用 Demo 模式。若要连接真实后端，在浏览器 Console 执行：

```javascript
APP_CONFIG.setDemoMode(false);
location.reload();
```

---

## 核心接口测试

### 健康检查

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### 查看动作知识库

```powershell
Invoke-RestMethod http://localhost:8000/api/actions | ConvertTo-Json -Depth 10
```

### 测试 DeepSeek 连通性

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/test_deepseek |
  ConvertTo-Json -Depth 10
```

### 生成康复处方

```powershell
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/generate_prescription `
  -ContentType "application/json" `
  -Body '{"name":"测试","age":30,"symptoms":"腰痛，久坐后加重","history":"无","pain_regions":["腰部"],"mobility_score":5}' |
  ConvertTo-Json -Depth 10
```

### 查询历史处方

```powershell
Invoke-RestMethod http://localhost:8000/api/prescriptions | ConvertTo-Json -Depth 10
```

### 姿态纠正接口

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

---

## 功能模块

### 1. 系统架构与后端

- FastAPI 后端框架
- REST API 路由
- SQLite 数据库
- SQLAlchemy ORM 模型
- CORS 配置
- 健康检查

### 2. 大模型集成与知识库

- DeepSeek API 接入
- `.env` 自动加载
- 结构化动作知识库
- 知识库候选动作检索
- 处方提示词模板
- 模型输出解析与本地兜底

### 3. 前端交互与演示

- 用户信息采集
- 疼痛部位选择
- 活动度评分
- 处方结果展示
- 动作卡片展示
- 模拟姿态检测反馈

### 4. 动作纠正算法

- 接收姿态关键点
- 计算角度和距离
- 返回纠正建议
- 返回评分和状态
- 当前支持：
  - `neck_side_bend`：颈部侧屈拉伸
  - `wall_squat`：靠墙静蹲

---

## 项目结构

```text
Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── api.py               # API 路由
│   │   ├── crud.py              # 数据库与业务逻辑
│   │   ├── database.py          # 数据库连接与初始化
│   │   ├── models.py            # SQLAlchemy 模型
│   │   ├── schema.py            # Pydantic 请求/响应模型
│   │   ├── knowledge.py         # 知识库读取与检索
│   │   ├── doubao.py            # DeepSeek API 调用封装
│   │   └── algorithms.py        # 姿态纠正算法
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── config.js
│   ├── mock.js
│   ├── style.css
│   └── assets/
├── knowledge/
│   ├── actions.json             # 康复动作知识库
│   └── prompt_template.txt      # 大模型提示词模板
├── README.md
├── architect.md
├── backend_api.md
├── assign.md
├── .env.sample
└── .gitignore
```

---

## 知识库说明

`knowledge/actions.json` 中每个动作包含：

- `id`：动作唯一标识
- `name`：动作名称
- `target_conditions`：适用病症
- `body_regions`：身体部位
- `sets`：组数
- `reps`：次数
- `frequency`：训练频次
- `description`：动作说明
- `contraindications`：禁忌症
- `progression`：进阶条件
- `regression`：降阶方案

当前覆盖颈部、肩部、腰部、膝关节等常见康复场景。

---

## 安全说明

- 系统生成内容仅用于课程项目和康复建议演示，不替代医生诊断。
- 出现剧烈疼痛、麻木无力、大小便异常、外伤后疼痛、发热或症状快速加重时，应及时就医。
- 大模型输出经过提示词约束，但仍建议由专业人员审核。
- 真实 API Key 仅写入本地 `.env`，不要提交到 GitHub。

---

## 文档

- `architect.md`：系统架构、模块设计、数据模型和后续扩展。
- `backend_api.md`：后端接口、请求/响应示例和测试命令。
- `assign.md`：团队分工、完成情况、里程碑和风险。
- `user_stories.md`：用户故事。
- `use_cases.md`：用例与交互场景。

---

## 更新日志

- 2026-06-12：项目初始化，建立基础项目结构。
- 2026-06-12：完成 FastAPI 后端、SQLite 数据模型、知识库、DeepSeek 集成、处方生成 API 和姿态纠正 API。

---

## 后续计划

- 接入 MediaPipe Pose，实现真实视频关键点提取。
- 扩展更多动作纠正算法。
- 增加用户登录、患者档案和医生审核流程。
- 增加训练打卡、处方导出和数据可视化。
- 补充自动化测试、测试报告和部署说明。
