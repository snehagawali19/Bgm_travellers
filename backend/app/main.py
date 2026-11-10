from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.customers import router as customer_router
from app.api.public import router as public_router
from app.api.operations import router as operations_router
from app.config import get_settings
from app.core.errors import AppError, app_error_handler, http_error_handler
from app.core.logging import configure_logging
from app.limiter import limiter

configure_logging()
settings = get_settings()

app = FastAPI(
    title="BGM Travels API",
    version="0.1.0",
    description="Scalable bus booking API for BGM Travels. Monetary amounts are integer paise.",
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests", "code": "rate_limited"})


app.include_router(public_router, prefix="/api/v1")
app.include_router(customer_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"service": "bgm-travels-api", "docs": "/docs"}
