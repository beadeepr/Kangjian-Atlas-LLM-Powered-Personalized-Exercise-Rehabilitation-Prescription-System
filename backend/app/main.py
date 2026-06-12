from fastapi import FastAPI
from .api import router as api_router

app = FastAPI(title="康健图谱 API")

app.include_router(api_router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}
