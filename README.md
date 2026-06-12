# 【康健图谱】——基于大模型的个性化运动康复处方生成系统

## 📋 项目信息

### 项目名称
【康健图谱】——基于大模型的个性化运动康复处方生成系统

### 项目描述
本项目是一个基于大型语言模型（LLM）的个性化康复处方生成系统，结合Atlas等技术，为用户提供定制化的运动康复处方。系统包含后端API服务、前端交互界面和知识库管理功能。

---

## 👥 团队成员

| 班级 | 学号 | 姓名 | Github/Gitee用户 | 职责 |
|------|------|------|------------------|------|
| 软件2403 | U202417374 | 王恒 | beadeepr | 项目负责人 |
| 软件2403 | U202417382 | 周硕 | hhh0164 | 算法与测试 |
| 软件2403 | U202417369 | 刘经纬 | lg997 | 前端开发 |

---

## 🚀 快速开始

### 1. 后端（FastAPI）

进入 `backend` 目录并创建虚拟环境：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将运行在 `http://localhost:8000`

### 2. 前端（静态示例）

打开 `frontend/index.html` 直接在浏览器中运行，或使用 `http-server` 提供本地静态服务：

```bash
cd frontend
npx http-server
```

### 3. 知识库与提示词

- 示例知识库存放在 `knowledge/actions.json`
- 提示词模板在 `knowledge/prompt_template.txt`

---

## 📁 项目结构

```
Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── main.py                  # 应用主入口
│   │   ├── api.py                   # API路由定义
│   │   ├── models.py                # 数据模型
│   │   └── schema.py                # 请求/响应Schema
│   └── requirements.txt              # Python依赖
├── frontend/                         # 前端应用
│   ├── index.html                   # HTML页面
│   ├── app.js                       # JavaScript逻辑
│   └── style.css                    # 样式表
├── knowledge/                        # 知识库和提示词
│   ├── actions.json                 # 动作知识库
│   └── prompt_template.txt          # 提示词模板
└── README.md                         # 项目文档
```

---

## 🔧 技术栈

- **后端**：FastAPI、Python
- **前端**：HTML、CSS、JavaScript
- **AI/LLM**：大型语言模型集成
- **知识库**：JSON格式数据存储

---

## 📝 更新日志

- **2026-06-12**：项目初始化，建立基础项目结构

---

## 📚 相关资源

（待补充）








*最后更新：2026-06-12*