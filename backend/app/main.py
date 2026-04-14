import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .routers import router


class CancelledErrorFilter(logging.Filter):
    """Filter out CancelledError exceptions during shutdown"""
    def filter(self, record):
        # Suppress CancelledError tracebacks during shutdown
        if record.exc_info and isinstance(record.exc_info[1], asyncio.CancelledError):
            return False
        if "CancelledError" in str(record.getMessage()):
            return False
        return True


# Apply filter to suppress CancelledError during shutdown
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.addFilter(CancelledErrorFilter())
starlette_logger = logging.getLogger("starlette")
starlette_logger.addFilter(CancelledErrorFilter())

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    # Cleanup code can go here if needed


app = FastAPI(
    title="FlowGen AI: The Unified Code Visualization Engine for Flowcharts and Workflows",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow frontend requests from React app
# Use environment variable for production deployments
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
origins = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

# Configure max request body size (for file uploads)
# This needs to be set at the server level, not in FastAPI
# Add this to your uvicorn command: --limit-max-requests 250000000

# Register API router
app.include_router(router, prefix="/api", tags=["API"])

@app.get("/")
def root():
    return {"message": "Backend running OK"}
