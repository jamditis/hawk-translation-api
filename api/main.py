from fastapi import FastAPI
from api.routes.translate import router as translate_router
from review.routes import router as review_router

app = FastAPI(
    title="Hawk News Service translation API",
    description=(
        "Human translator-centered API for translating journalism content. "
        "Machine translation generates a first draft; professional human translators "
        "review, edit, and certify the final output."
    ),
    version="1.0.0",
)

app.include_router(translate_router, prefix="/v1")
app.include_router(review_router, prefix="/review")


@app.get("/health")
def health():
    return {"status": "ok"}
