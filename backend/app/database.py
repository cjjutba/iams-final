"""
Database Configuration and Session Management

Provides SQLAlchemy engine, session factory, and base class for models.
Connects to PostgreSQL using SQLAlchemy.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import logger, settings

# Create SQLAlchemy engine
# Using synchronous engine for simplicity (can upgrade to async later if needed)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=300,  # Recycle connections every 5 minutes to avoid stale connections
    echo=False,  # Never echo SQL — too noisy; use logger.debug in queries if needed
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI to get database session

    Yields:
        Database session

    Usage:
        @app.get("/users/")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables

    This creates all tables defined by models that inherit from Base.
    Use Alembic migrations in production instead of this function.
    """
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def check_db_connection() -> bool:
    """
    Check if database connection is working

    Returns:
        True if connection successful, False otherwise
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
    finally:
        db.close()
