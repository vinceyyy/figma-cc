from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.logging import RequestLoggingMiddleware, setup_logging
from api.routers.feedback import router as feedback_router

setup_logging(settings.log_level)

app = FastAPI(title="Figma AI Feedback")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permissive for prototype; tighten for production
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(feedback_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
