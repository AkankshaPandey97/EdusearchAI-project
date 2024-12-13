import json
from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .core.security import get_api_key
from backend.config import get_settings
from backend.api.endpoints import notes, qa, search, materials, playlists, reports, citation, summarization, segments
from .middleware.rate_limit import RateLimitMiddleware
from fastapi.responses import JSONResponse
from backend.utils.error_handling import WorkflowError, ErrorSeverity, ErrorCategory, StateManager
from backend.utils.logging_config import setup_logging, logger
from backend.utils.model_loader import get_model_loader
from backend.utils.json_encoder import CustomJSONEncoder, serialize_datetime
from fastapi.encoders import jsonable_encoder
import time
from datetime import datetime
import logging

# Setup logging
setup_logging()

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=CustomJSONEncoder
        ).encode("utf-8")

app = FastAPI(
    title="EduSearch AI",
    description="API for processing and enriching educational content",
    version="1.0.0",
    default_response_class=CustomJSONResponse,
    json_encoder=json.JSONEncoder(default=serialize_datetime)
)

# Add middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"Status: {response.status_code} "
        f"Duration: {duration:.2f}s"
    )
    return response

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
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
    tags=["playlists"]
)
app.include_router(
    reports.router,
    prefix="/api/v1/reports",
    tags=["reports"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(
    citation.router,
    prefix="/api/v1/citation",
    tags=["citation"],
    dependencies=[Depends(get_api_key)]
)
app.include_router(summarization.router, prefix="/api/v1")
app.include_router(
    segments.router,
    tags=["segments"]
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
        code="SYSTEM_ERROR",
        message=str(exc),
        severity=ErrorSeverity.HIGH,
        category=ErrorCategory.SYSTEM,
        context={"path": request.url.path}
    )
    await state_manager.add_error(error)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Disable authentication for development (temporarily)
@app.middleware("http")
async def bypass_auth(request, call_next):
    response = await call_next(request)
    return response

# Use the custom JSON encoder
#@app.middleware("http")
#async def custom_json_encoder_middleware(request, call_next):
#    response = await call_next(request)
#    response.body = jsonable_encoder(response.body, custom_encoder={datetime: lambda v: v.isoformat()})
#    return response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Include routers
app.include_router(qa.router)
app.include_router(playlists.router)
app.include_router(summarization.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting application...")
    # Any startup configuration can go here
    logger.info("Application startup complete")