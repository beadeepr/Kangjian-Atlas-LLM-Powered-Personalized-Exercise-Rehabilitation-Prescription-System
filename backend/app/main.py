from fastapi import FastAPI
from .api import router as api_router
from .database import init_db

app = FastAPI(title="康健图谱 API")

app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}
