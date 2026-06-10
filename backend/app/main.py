from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import expenses, parse, statements, recon, dashboard, export

app = FastAPI(title="Kharcha API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not settings.auth_token:
        return await call_next(request)
    if request.url.path in ("/health", "/"):
        return await call_next(request)
    header = request.headers.get("Authorization", "")
    if header != f"Bearer {settings.auth_token}":
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)

app.include_router(parse.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(statements.router, prefix="/api")
app.include_router(recon.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
