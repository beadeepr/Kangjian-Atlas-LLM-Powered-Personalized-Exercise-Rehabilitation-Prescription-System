# 康健图谱 — LLM 驱动的个性化康复处方系统（MVP）

1. 后端（FastAPI）

- 进入 `backend` 目录并创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. 前端（静态示例）

- 打开 `frontend/index.html` 直接在浏览器中运行，或用 `http-server` 提供本地静态服务。

3. 知识库与提示词

- 示例知识库存放在 `knowledge/actions.json`。
- 提示词模板在 `knowledge/prompt_template.txt`。

项目结构

```
backend/
	app/
		main.py
		api.py
		models.py
		schema.py
	requirements.txt
frontend/
	index.html
	app.js
	style.css
knowledge/
	actions.json
	prompt_template.txt
README.md
```

# Kangjian-Atlas-LLM-Powered-Personalized-Exercise-Rehabilitation-Prescription-System