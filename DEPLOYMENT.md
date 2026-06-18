# 部署说明与线上演示环境

## 后端环境变量

复制 `.env.sample` 为 `.env`，并按部署环境填写：

```env
APP_ENV=production
DEMO_MODE=false
CORS_ORIGINS=https://your-frontend.example.com
DATABASE_URL=sqlite:///backend/database.db
DOUBAO_API_KEY=your_api_key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_ID=your_model_id
JWT_SECRET=change_this_to_a_long_random_secret
JWT_EXPIRE_SECONDS=604800
ADMIN_ACCOUNTS=admin
```

说明：

- `CORS_ORIGINS` 用英文逗号分隔多个前端地址。
- `DATABASE_URL` 默认使用 SQLite；线上演示可挂载 `backend/database.db` 或替换为其他 SQLAlchemy 数据库地址。
- `JWT_SECRET` 必须改为较长随机字符串。
- `.env` 不提交到 GitHub。
- 豆包配置缺失时，处方生成会走本地兜底摘要，演示流程不会中断。

## 本地生产方式启动

在项目根目录执行：

```powershell
.\backend\start_server.ps1
```

默认监听：

```text
http://localhost:8000
```

## Docker 部署

构建镜像：

```powershell
docker build -f backend/Dockerfile -t kangjian-atlas-backend .
```

运行容器：

```powershell
docker run --rm -p 8000:8000 --env-file .env kangjian-atlas-backend
```

## 线上演示检查接口

健康检查：

```text
GET /health
```

就绪检查：

```text
GET /ready
```

部署信息：

```text
GET /api/deployment/info
```

该接口不会返回 API Key 或 JWT Secret，只返回配置是否存在和数据库状态。

## 演示账号建议

1. 注册普通用户账号，用于患者端演示。
2. 注册 `admin` 账号或在 `.env` 中设置 `ADMIN_ACCOUNTS`，用于管理员知识库维护演示。
3. 先运行自动化测试脚本生成报告：

```powershell
.\.venv\Scripts\python.exe backend\run_backend_tests.py
```

然后通过管理员接口读取：

```text
GET /api/admin/test_report
```

## 部署后验证流程

1. 访问 `/health`，确认返回 `{"status":"ok"}`。
2. 访问 `/ready`，确认数据库状态为 `ok`。
3. 访问 `/api/deployment/info`，确认豆包、CORS、环境配置状态。
4. 注册/登录用户，生成一条康复处方。
5. 导出处方，验证 `/api/prescriptions/{id}/export?format=md`。
6. 登录管理员账号，验证 `/api/admin/actions`。
