"""
IAMS Backend - FastAPI Application Entry Point

Main application file that initializes FastAPI, configures middleware,
registers routers, and handles application lifecycle events.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings, logger
from app.database import check_db_connection, get_db
from app.utils.exceptions import (
    IAMSException,
    iams_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)

# Import routers
from app.routers import auth, users, face, schedules, attendance, websocket, notifications, presence

# Global scheduler instance for background tasks
scheduler = AsyncIOScheduler()


# ===== FastAPI Application =====

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Attendance Monitoring System - Backend API",
    version="1.0.0",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    contact={
        "name": "IAMS Development Team",
        "email": "support@iams.jrmsu.edu.ph",
    },
    license_info={
        "name": "MIT",
    }
)


# ===== CORS Middleware =====

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Exception Handlers =====

# Custom IAMS exceptions
app.add_exception_handler(IAMSException, iams_exception_handler)

# Pydantic validation errors
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Generic exception handler for unexpected errors
app.add_exception_handler(Exception, generic_exception_handler)


# ===== Startup and Shutdown Events =====

@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler

    Performs initialization tasks:
    - Check database connection
    - Load FAISS index (once face service is implemented)
    - Warm up FaceNet model (once face service is implemented)
    """
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API prefix: {settings.API_PREFIX}")

    # Check database connection
    db_connected = check_db_connection()
    if not db_connected:
        logger.error("Failed to connect to database. Application may not function correctly.")
    else:
        logger.info("Database connection established")

    # Load FaceNet model and FAISS index
    try:
        from app.services.ml.face_recognition import facenet_model
        from app.services.ml.faiss_manager import faiss_manager

        logger.info("Loading FaceNet model...")
        facenet_model.load_model()

        logger.info("Loading FAISS index...")
        faiss_manager.load_or_create_index()

        logger.info("Face recognition system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize face recognition: {e}")

    # Initialize APScheduler for continuous presence tracking
    try:
        from app.services.presence_service import PresenceService
        from app.database import SessionLocal

        logger.info("Initializing presence tracking scheduler...")

        # Create presence service instance (will be called by scheduler)
        async def run_presence_scan_cycle():
            """Background task to run presence scan cycles"""
            db = SessionLocal()
            try:
                presence_service = PresenceService(db)
                await presence_service.run_scan_cycle()
            except Exception as e:
                logger.error(f"Error in presence scan cycle: {e}")
            finally:
                db.close()

        # Schedule continuous presence tracking (every 60 seconds)
        scheduler.add_job(
            run_presence_scan_cycle,
            'interval',
            seconds=settings.SCAN_INTERVAL_SECONDS,
            id='presence_scan_cycle',
            replace_existing=True,
            max_instances=1  # Prevent overlapping runs
        )

        # Start the scheduler
        scheduler.start()
        logger.info(f"Presence tracking scheduler started (scan interval: {settings.SCAN_INTERVAL_SECONDS}s)")

    except Exception as e:
        logger.error(f"Failed to initialize presence tracking scheduler: {e}")

    logger.info(f"{settings.APP_NAME} startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler

    Performs cleanup tasks:
    - Save FAISS index
    - Close database connections
    """
    logger.info(f"Shutting down {settings.APP_NAME}...")

    # Stop APScheduler
    try:
        if scheduler.running:
            logger.info("Stopping presence tracking scheduler...")
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")

    # Save FAISS index
    try:
        from app.services.ml.faiss_manager import faiss_manager
        logger.info("Saving FAISS index...")
        faiss_manager.save()
    except Exception as e:
        logger.error(f"Failed to save FAISS index: {e}")

    logger.info(f"{settings.APP_NAME} shutdown complete")


# ===== Health Check Endpoint =====

@app.get(f"{settings.API_PREFIX}/health", tags=["System"])
async def health_check():
    """
    Health check endpoint

    Returns the system status and version information.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "debug": settings.DEBUG
    }


@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint

    Returns a welcome message.
    """
    return {
        "message": f"{settings.APP_NAME} API is running",
        "docs": f"{settings.API_PREFIX}/docs"
    }


# ===== Router Includes =====

# Auth routes
app.include_router(
    auth.router,
    prefix=f"{settings.API_PREFIX}/auth",
    tags=["Authentication"]
)

# User routes
app.include_router(
    users.router,
    prefix=f"{settings.API_PREFIX}/users",
    tags=["Users"]
)

# Face recognition routes
app.include_router(
    face.router,
    prefix=f"{settings.API_PREFIX}/face",
    tags=["Face Recognition"]
)

# Schedule routes
app.include_router(
    schedules.router,
    prefix=f"{settings.API_PREFIX}/schedules",
    tags=["Schedules"]
)

# Attendance routes
app.include_router(
    attendance.router,
    prefix=f"{settings.API_PREFIX}/attendance",
    tags=["Attendance"]
)

# Notification routes
app.include_router(
    notifications.router,
    prefix=f"{settings.API_PREFIX}/notifications",
    tags=["Notifications"]
)

# Presence tracking routes
app.include_router(
    presence.router,
    prefix=f"{settings.API_PREFIX}/presence",
    tags=["Presence Tracking"]
)

# WebSocket routes
app.include_router(
    websocket.router,
    prefix=f"{settings.API_PREFIX}/ws",
    tags=["WebSocket"]
)


# ===== Development Server =====

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )
