from fastapi import FastAPI
from api.routes.translate import router as translate_router

app = FastAPI(
    title="Hawk News Service translation API",
    description="Translation API for local and nonprofit newsrooms",
    version="1.0.0",
)

app.include_router(translate_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
