import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .api.v1 import router as api_router
from .config import get_settings
from .middleware import SecurityMiddleware


logger = logging.getLogger("minecraft_manager")
settings = get_settings()
app = FastAPI(
    title="Minecraft Server Manager API",
    version=__version__,
    docs_url="/api/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.docs_enabled else None,
)
app.add_middleware(SecurityMiddleware)
app.include_router(api_router)


@app.get("/healthz", include_in_schema=False)
async def health():
    return {"status": "ok", "version": __version__}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"http_{exc.status_code}", "message": str(exc.detail), "request_id": getattr(request.state, "request_id", None)}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Request validation failed", "request_id": getattr(request.state, "request_id", None), "details": {"fields": [{"path": ".".join(map(str, error["loc"])), "message": error["msg"]} for error in exc.errors()]}}},
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled request error", extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred", "request_id": getattr(request.state, "request_id", None)}},
    )
