"""
Edge Device Environment Configuration Validator

Validates environment variables and system requirements for Raspberry Pi edge device.
Run this before starting the edge device to catch configuration issues early.
"""

import os
import sys
import platform
from pathlib import Path
from urllib.parse import urlparse


def check_python_version():
    """Check Python version (3.8+ required)"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✓ Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python version: {version.major}.{version.minor}.{version.micro} (3.8+ required)")
        return False


def check_platform():
    """Check if running on Raspberry Pi"""
    system = platform.system()
    machine = platform.machine()
    print(f"✓ Platform: {system} {machine}")

    # Check if Raspberry Pi
    if system == "Linux" and (machine.startswith("arm") or machine.startswith("aarch")):
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip()
                if 'Raspberry Pi' in model:
                    print(f"✓ Device: {model}")
                    return True
        except FileNotFoundError:
            pass

    print(f"⚠️  Not detected as Raspberry Pi (will proceed anyway)")
    return True


def validate_server_url(url: str) -> bool:
    """Validate backend server URL"""
    if not url:
        print(f"❌ BACKEND_URL: Not set")
        return False

    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            print(f"❌ BACKEND_URL: Invalid URL format")
            return False

        if result.scheme not in ['http', 'https']:
            print(f"❌ BACKEND_URL: Invalid scheme (expected http or https)")
            return False

        print(f"✓ BACKEND_URL: {url}")
        return True
    except Exception as e:
        print(f"❌ BACKEND_URL: Error parsing URL - {e}")
        return False


def validate_camera():
    """Check if camera is available"""
    try:
        # Try to import cv2
        import cv2
        print(f"✓ OpenCV installed: {cv2.__version__}")

        # Try to open camera
        camera_index = int(os.getenv('CAMERA_INDEX', '0'))
        cap = cv2.VideoCapture(camera_index)

        if cap.isOpened():
            print(f"✓ Camera accessible at index {camera_index}")
            cap.release()
            return True
        else:
            print(f"⚠️  Camera not accessible at index {camera_index}")
            print(f"   This may be normal if camera is not connected yet")
            return True  # Don't fail validation
    except ImportError:
        print(f"⚠️  OpenCV not installed (will install from requirements.txt)")
        return True
    except Exception as e:
        print(f"⚠️  Camera check failed: {e}")
        return True  # Don't fail validation


def validate_env():
    """
    Validate all environment variables and system requirements

    Returns:
        bool: True if all validations pass, False otherwise
    """
    print("\n" + "="*60)
    print("IAMS Edge Device - Environment Configuration Validation")
    print("="*60 + "\n")

    all_valid = True

    # System checks
    print("System Requirements:")
    print("-" * 60)
    all_valid &= check_python_version()
    all_valid &= check_platform()
    all_valid &= validate_camera()
    print()

    # Required variables
    print("Required Variables:")
    print("-" * 60)

    server_url = os.getenv('BACKEND_URL')
    all_valid &= validate_server_url(server_url)

    print()

    # Numeric settings
    print("Configuration:")
    print("-" * 60)

    try:
        camera_index = int(os.getenv('CAMERA_INDEX', '0'))
        print(f"✓ CAMERA_INDEX: {camera_index}")
    except ValueError:
        print(f"❌ CAMERA_INDEX: Invalid integer")
        all_valid = False

    try:
        frame_width = int(os.getenv('CAMERA_WIDTH', '640'))
        frame_height = int(os.getenv('CAMERA_HEIGHT', '480'))
        print(f"✓ Camera size: {frame_width}x{frame_height}")
    except ValueError:
        print(f"❌ CAMERA_WIDTH/CAMERA_HEIGHT: Invalid integers")
        all_valid = False

    try:
        queue_size = int(os.getenv('QUEUE_MAX_SIZE', '500'))
        queue_ttl = int(os.getenv('QUEUE_TTL_SECONDS', '300'))
        print(f"✓ Queue: max={queue_size}, ttl={queue_ttl}s")
    except ValueError:
        print(f"❌ Queue settings: Invalid integers")
        all_valid = False

    try:
        retry_interval = int(os.getenv('RETRY_INTERVAL_SECONDS', '10'))
        print(f"✓ RETRY_INTERVAL_SECONDS: {retry_interval}")
    except ValueError:
        print(f"❌ RETRY_INTERVAL_SECONDS: Invalid integer")
        all_valid = False

    room_id = os.getenv('ROOM_ID', '')
    if room_id:
        print(f"✓ ROOM_ID: {room_id}")
    else:
        print(f"⚠️  ROOM_ID: Not set (will detect all faces without room association)")

    print()

    # File paths
    print("File Paths:")
    print("-" * 60)

    log_file = os.getenv('LOG_FILE', 'logs/edge.log')
    log_path = Path(log_file)
    log_dir = log_path.parent

    if not log_dir.exists():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created log directory: {log_dir}")
        except Exception as e:
            print(f"❌ Cannot create log directory: {e}")
            all_valid = False
    else:
        print(f"✓ Log directory exists: {log_dir}")

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
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            print("⚠️  python-dotenv not installed. Using system environment variables.\n")
    else:
        print("⚠️  No .env file found. Using system environment variables.\n")

    # Run validation
    success = validate_env()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
