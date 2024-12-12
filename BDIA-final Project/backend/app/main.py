from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .core.security import get_api_key
from backend.config import get_settings
from backend.api.endpoints import notes, qa, search, materials, playlists, reports
from .middleware.rate_limit import RateLimitMiddleware
from fastapi.responses import JSONResponse
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
from backend.utils.logging_config import setup_logging, logger
from backend.utils.model_loader import get_model_loader
import time

# Setup logging
setup_logging()

app = FastAPI(
    title="EduSearch AI",
    description="API for processing and enriching educational content",
    version="1.0.0"
)

# Add middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"Status: {response.status_code} "
        f"Duration: {duration:.2f}s"
    )
    return response

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    burst_limit=10,
    max_concurrent=20
)

# Include routers with API key protection
app.include_router(
    notes.router,
    prefix="/api/v1/notes",
    tags=["notes"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    qa.router,
    prefix="/api/v1/qa",
    tags=["qa"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    search.router,
    prefix="/api/v1/search",
    tags=["search"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    materials.router,
    prefix="/api/v1/materials",
    tags=["materials"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    playlists.router,
    prefix="/api/v1/playlists",
    tags=["playlists"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    reports.router,
    prefix="/api/v1/reports",
    tags=["reports"],
    dependencies=[Depends(get_api_key)]
)

# Public endpoints
@app.get("/")
async def root():
    return {
        "message": "Welcome to EduSearch AI",
        "docs_url": "/docs",
        "version": "1.0.0",
        "api_base": "/api/v1"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Initialize state manager for error handling
state_manager = StateManager()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting application...")
    try:
        settings = get_settings()
        model_loader = get_model_loader()
        await model_loader.get_model("gpt-4-turbo-preview", temperature=0.7)
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down application...")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error = WorkflowError(
        code="GLOBAL_ERROR",
        message=str(exc),
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.SYSTEM,
        context={"path": request.url.path}
    )
    logger.error(f"Global error: {str(exc)}", exc_info=True)
    await state_manager.add_error(error)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected error occurred",
            "error_code": error.code
        }
    )