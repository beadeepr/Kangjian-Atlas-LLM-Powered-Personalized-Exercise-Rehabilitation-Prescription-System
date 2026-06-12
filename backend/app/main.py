from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router as api_router
from .database import init_db

app = FastAPI(title="康健图谱 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}
