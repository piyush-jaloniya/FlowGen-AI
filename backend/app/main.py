import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Allow frontend requests from React app
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API router
app.include_router(router, prefix="/api", tags=["API"])

@app.get("/")
def root():
    return {"message": "Backend running OK"}
