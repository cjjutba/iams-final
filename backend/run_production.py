"""
Production Server Runner

Starts the FastAPI application in production mode with multiple workers.
Uses Uvicorn with recommended production settings.
"""

import os
import sys
import uvicorn
from pathlib import Path


def main():
    """Start production server with recommended settings"""

    # Ensure we're using the production environment
    env_file = Path(__file__).parent / '.env.production'
    if env_file.exists():
        print(f"Loading production environment from: {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file)
    else:
        print("⚠️  No .env.production file found. Using .env or system environment.")
        env_file = Path(__file__).parent / '.env'
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)

    # Validate environment before starting
    print("\nValidating environment configuration...")
    from scripts.validate_env import validate_env
    if not validate_env():
        print("❌ Environment validation failed. Please fix errors before starting.")
        sys.exit(1)

    # Check DEBUG mode
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    if debug:
        print("\n⚠️  WARNING: DEBUG=true detected in production!")
        print("   This should be set to DEBUG=false for production deployments.")
        response = input("   Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)

    # Determine number of workers
    # Recommendation: (2 x CPU cores) + 1
    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
    workers = int(os.getenv('WORKERS', (2 * cpu_count) + 1))

    print(f"\n{'='*60}")
    print(f"Starting IAMS Backend - Production Mode")
    print(f"{'='*60}")
    print(f"Workers: {workers} (CPU cores: {cpu_count})")
    print(f"Host: 0.0.0.0")
    print(f"Port: 8000")
    print(f"Debug: {debug}")
    print(f"{'='*60}\n")

    # Start server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=workers,
        reload=False,  # Never reload in production
        log_level="info",
        access_log=True,
        use_colors=False,  # Disable colors for log files
        proxy_headers=True,  # Trust X-Forwarded-* headers from reverse proxy
        forwarded_allow_ips="*",  # Allow all IPs (adjust if using specific proxy)
    )


if __name__ == "__main__":
    main()
