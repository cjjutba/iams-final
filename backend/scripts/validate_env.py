"""
Environment Configuration Validator

Validates that all required environment variables are set and properly formatted.
Run this before starting the backend server to catch configuration issues early.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def validate_url(url: str, name: str) -> bool:
    """Validate URL format"""
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            print(f"❌ {name}: Invalid URL format")
            return False
        print(f"✓ {name}: {url}")
        return True
    except Exception as e:
        print(f"❌ {name}: Error parsing URL - {e}")
        return False


def validate_database_url(url: str) -> bool:
    """Validate PostgreSQL connection string"""
    try:
        result = urlparse(url)
        if result.scheme not in ['postgresql', 'postgresql+psycopg2']:
            print(f"❌ DATABASE_URL: Invalid scheme (expected postgresql)")
            return False
        if 'pooler.supabase.com' in result.netloc:
            print(f"✓ DATABASE_URL: Using Supabase pooler (recommended)")
        elif 'supabase.com' in result.netloc:
            print(f"⚠️  DATABASE_URL: Direct connection detected (pooler recommended)")
        else:
            print(f"✓ DATABASE_URL: Custom PostgreSQL connection")
        return True
    except Exception as e:
        print(f"❌ DATABASE_URL: Error parsing - {e}")
        return False


def validate_path(path: str, name: str, should_exist: bool = False) -> bool:
    """Validate file/directory path"""
    path_obj = Path(path)
    if should_exist and not path_obj.exists():
        print(f"❌ {name}: Path does not exist: {path}")
        return False

    # Check if parent directory exists
    parent = path_obj.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
            print(f"✓ {name}: Created directory: {parent}")
        except Exception as e:
            print(f"❌ {name}: Cannot create directory - {e}")
            return False

    print(f"✓ {name}: {path}")
    return True


def validate_env():
    """
    Validate all required environment variables

    Returns:
        bool: True if all validations pass, False otherwise
    """
    print("\n" + "="*60)
    print("IAMS Backend - Environment Configuration Validation")
    print("="*60 + "\n")

    all_valid = True

    # Required variables
    required_vars = {
        'SUPABASE_URL': 'Supabase project URL',
        'SUPABASE_ANON_KEY': 'Supabase anonymous key',
        'DATABASE_URL': 'PostgreSQL connection string',
        'SECRET_KEY': 'JWT secret key',
    }

    print("Required Variables:")
    print("-" * 60)
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            print(f"❌ {var}: Missing ({description})")
            all_valid = False
        elif var == 'SUPABASE_URL':
            all_valid &= validate_url(value, var)
        elif var == 'DATABASE_URL':
            all_valid &= validate_database_url(value)
        elif var == 'SECRET_KEY':
            if value == 'dev-secret-key-change-in-production':
                print(f"⚠️  {var}: Using default dev key (change in production!)")
            elif len(value) < 32:
                print(f"⚠️  {var}: Key is short (recommend 32+ characters)")
            else:
                print(f"✓ {var}: Set ({len(value)} characters)")
        else:
            print(f"✓ {var}: Set")

    print()

    # Optional but recommended
    print("Optional Variables:")
    print("-" * 60)

    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    if service_key:
        print(f"✓ SUPABASE_SERVICE_KEY: Set")
    else:
        print(f"⚠️  SUPABASE_SERVICE_KEY: Not set (required for admin operations)")

    debug = os.getenv('DEBUG', 'true').lower()
    if debug == 'true':
        print(f"⚠️  DEBUG: Enabled (disable in production!)")
    else:
        print(f"✓ DEBUG: Disabled")

    cors_origins = os.getenv('CORS_ORIGINS', '["*"]')
    if '"*"' in cors_origins or "'*'" in cors_origins:
        print(f"⚠️  CORS_ORIGINS: Wildcard detected (specify exact origins in production)")
    else:
        print(f"✓ CORS_ORIGINS: Configured")

    print()

    # File paths
    print("File Paths:")
    print("-" * 60)

    faiss_path = os.getenv('FAISS_INDEX_PATH', 'data/faiss/faces.index')
    all_valid &= validate_path(faiss_path, 'FAISS_INDEX_PATH')

    upload_dir = os.getenv('UPLOAD_DIR', 'data/uploads/faces')
    all_valid &= validate_path(upload_dir, 'UPLOAD_DIR')

    log_file = os.getenv('LOG_FILE', 'logs/app.log')
    all_valid &= validate_path(log_file, 'LOG_FILE')

    print()

    # Numeric settings
    print("Numeric Settings:")
    print("-" * 60)

    try:
        threshold = float(os.getenv('RECOGNITION_THRESHOLD', '0.6'))
        if 0.0 <= threshold <= 1.0:
            print(f"✓ RECOGNITION_THRESHOLD: {threshold}")
        else:
            print(f"❌ RECOGNITION_THRESHOLD: Out of range (must be 0.0-1.0)")
            all_valid = False
    except ValueError:
        print(f"❌ RECOGNITION_THRESHOLD: Invalid number format")
        all_valid = False

    try:
        token_expire = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
        print(f"✓ ACCESS_TOKEN_EXPIRE_MINUTES: {token_expire}")
    except ValueError:
        print(f"❌ ACCESS_TOKEN_EXPIRE_MINUTES: Invalid integer")
        all_valid = False

    print()

    # Summary
    print("="*60)
    if all_valid:
        print("✓ All validations passed!")
        print("="*60 + "\n")
        return True
    else:
        print("❌ Some validations failed. Please fix errors above.")
        print("="*60 + "\n")
        return False


if __name__ == "__main__":
    # Load .env file if it exists
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        print(f"Loading environment from: {env_file}\n")
        from dotenv import load_dotenv
        load_dotenv(env_file)
    else:
        print("⚠️  No .env file found. Using system environment variables.\n")

    # Run validation
    success = validate_env()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
