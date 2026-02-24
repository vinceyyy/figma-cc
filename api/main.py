from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.feedback import router as feedback_router

app = FastAPI(title="Figma AI Feedback")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permissive for prototype; tighten for production
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(feedback_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
