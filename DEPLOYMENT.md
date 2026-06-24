# 部署说明与生产存储栈

## 环境变量

复制 `.env.sample` 为 `.env`，按部署环境填写：

```env
APP_ENV=production
DEMO_MODE=false
CORS_ORIGINS=https://your-frontend.example.com
DATABASE_URL=postgresql+psycopg://kangjian:kangjian_password@postgres:5432/kangjian_atlas
REDIS_URL=redis://redis:6379/0
OBJECT_STORAGE_BACKEND=minio
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=kangjian-atlas
MINIO_SECURE=false
DeepSeek_API_KEY=your_api_key
DeepSeek_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DeepSeek_MODEL_ID=your_model_id
JWT_SECRET=change_this_to_a_long_random_secret
JWT_EXPIRE_SECONDS=604800
ADMIN_ACCOUNTS=admin
DOCTOR_ACCOUNTS=doctor
```

说明：

- `DATABASE_URL` 支持 SQLAlchemy 地址。开发默认可继续使用 SQLite，生产建议使用 PostgreSQL。
- `REDIS_URL` 为空时 Redis 缓存自动禁用；配置后用于热点数据缓存和健康检查。
- `OBJECT_STORAGE_BACKEND=local` 时上传文件写入本地 `backend/uploads`；设置为 `minio` 后写入 MinIO bucket。
- `.env` 不要提交到 GitHub。

## Docker Compose 启动

项目根目录执行：

```powershell
docker compose up --build
```

默认服务：

```text
API: http://localhost:8000
PostgreSQL: localhost:5432
Redis: localhost:6379
MinIO API: http://localhost:9000
MinIO Console: http://localhost:9001
```

MinIO 默认账号密码来自 `docker-compose.yml`：`minioadmin / minioadmin`。生产环境请改成强密码。

## 本地开发启动

只使用 SQLite 和本地文件存储时：

```powershell
.\backend\start_server.ps1
```

或直接运行：

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload
```

## 验证接口

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

`/ready` 和 `/api/deployment/info` 会返回数据库、Redis、对象存储状态，但不会返回 API Key 或 JWT Secret。

## 自动化测试

```powershell
.\.venv\Scripts\python.exe backend\run_backend_tests.py
```

测试报告会写入：

```text
backend/reports/backend_test_report.md
backend/reports/backend_test_report.json
```

管理员登录后也可以读取：

```text
GET /api/admin/test_report
```
