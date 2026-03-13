"""
Camera Test Tool for IAMS

Tests your camera setup and analyzes whether it provides sufficient resolution
for face detection and recognition in a classroom.

Usage:
    # Test RTSP camera (Reolink P340)
    python tools/test_camera.py --rtsp "rtsp://admin:password@192.168.1.100/Preview_01_main"

    # Test USB webcam
    python tools/test_camera.py --usb 0

    # Test with face detection enabled
    python tools/test_camera.py --rtsp "rtsp://..." --detect

    # Save test frames to disk
    python tools/test_camera.py --rtsp "rtsp://..." --save

    # Analyze coverage for a specific room depth
    python tools/test_camera.py --rtsp "rtsp://..." --room-depth 8

Requirements:
    pip install opencv-python numpy mediapipe
"""

import argparse
import math
import os
import sys
import time

# Add parent dir so we can import from app if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def connect_rtsp(url: str, transport: str = "tcp"):
    """Connect to RTSP stream and return VideoCapture + test frame."""
    import cv2

    print("\n[1/4] Connecting to RTSP stream...")

    # Mask password for display
    safe_url = url
    if "@" in url:
        prefix = url.split("@")[0]
        if ":" in prefix.split("//")[1]:
            safe_url = prefix.rsplit(":", 1)[0] + ":****@" + url.split("@")[1]
    print(f"  URL: {safe_url}")
    print(f"  Transport: {transport}")

    # Set RTSP transport preference via environment
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("  FAILED: Could not open RTSP stream")
        print("  Check: URL, credentials, camera power, network connection")
        return None, None

    # Wait for stream to stabilize
    print("  Waiting for stream to stabilize...")
    time.sleep(2)

    ret, frame = cap.read()
    if not ret or frame is None:
        print("  FAILED: Could not read frame from stream")
        cap.release()
        return None, None

    print("  SUCCESS: Connected to RTSP stream")
    return cap, frame


def connect_usb(index: int = 0):
    """Connect to USB camera and return VideoCapture + test frame."""
    import cv2

    print(f"\n[1/4] Connecting to USB camera (index={index})...")

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"  FAILED: Could not open camera at index {index}")
        return None, None

    # Try to set high resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    ret, frame = cap.read()
    if not ret or frame is None:
        print("  FAILED: Could not read frame")
        cap.release()
        return None, None

    print("  SUCCESS: Connected to USB camera")
    return cap, frame


def analyze_frame(frame, camera_hfov_deg: float = 93.0):
    """Analyze frame resolution and estimate face pixel coverage."""

    height, width = frame.shape[:2]
    total_pixels = width * height
    mp = total_pixels / 1_000_000

    print("\n[2/4] Frame Analysis:")
    print(f"  Resolution: {width} x {height} ({mp:.1f} MP)")
    print(f"  Aspect ratio: {width / height:.2f}")
    print(f"  Horizontal FOV: {camera_hfov_deg}°")

    # Calculate pixels-per-face at various distances
    print("\n  Face pixel coverage estimates (face width ~18cm):")
    print(f"  {'Distance':>10} | {'Frame covers':>14} | {'Pixels/face':>12} | {'Quality':>15}")
    print(f"  {'-' * 10}-+-{'-' * 14}-+-{'-' * 12}-+-{'-' * 15}")

    hfov_rad = math.radians(camera_hfov_deg)
    face_width_m = 0.18  # average face width

    for distance in [2, 3, 4, 5, 6, 7, 8, 10]:
        coverage_m = 2 * distance * math.tan(hfov_rad / 2)
        pixels_per_meter = width / coverage_m
        face_pixels = pixels_per_meter * face_width_m

        if face_pixels >= 160:
            quality = "Excellent"
        elif face_pixels >= 100:
            quality = "Good"
        elif face_pixels >= 80:
            quality = "Marginal"
        elif face_pixels >= 50:
            quality = "Poor"
        else:
            quality = "Too small"

        print(f"  {distance:>8}m | {coverage_m:>11.1f}m | {face_pixels:>9.0f} px | {quality:>15}")

    return width, height


def _get_model_path():
    """Download MediaPipe face detection model if not cached."""
    import urllib.request

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    model_path = os.path.join(cache_dir, "blaze_face_short_range.tflite")

    if not os.path.exists(model_path):
        url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
        print("  Downloading face detection model...")
        urllib.request.urlretrieve(url, model_path)
        print(f"  Model saved to {model_path}")

    return model_path


def detect_faces(frame):
    """Run MediaPipe face detection on frame."""
    import cv2

    print("\n[3/4] Face Detection:")

    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
    except ImportError:
        print("  SKIPPED: mediapipe not installed (pip install mediapipe)")
        return []

    # Download model if needed
    model_path = _get_model_path()

    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

    # Create detector with downloaded model
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceDetectorOptions(
        base_options=base_options,
        min_detection_confidence=0.5,
    )

    detector = vision.FaceDetector.create_from_options(options)
    result = detector.detect(mp_image)
    detector.close()

    faces = result.detections if result.detections else []
    print(f"  Detected {len(faces)} face(s)")

    height, width = frame.shape[:2]
    for i, detection in enumerate(faces):
        bbox = detection.bounding_box
        conf = detection.categories[0].score if detection.categories else 0
        face_w = bbox.width
        face_h = bbox.height
        print(f"  Face {i + 1}: {face_w}x{face_h} px, confidence={conf:.2f}")

        if face_w < 80:
            print("    WARNING: Face too small for reliable recognition (need 80+ px)")
        elif face_w < 160:
            print("    OK: Detectable, but will be upscaled for FaceNet (160x160)")
        else:
            print("    EXCELLENT: Good size for face recognition")

    return faces


def save_results(frame, faces, output_dir: str = "test_output"):
    """Save test frame and annotated frame."""
    import cv2

    print("\n[4/4] Saving Results:")

    os.makedirs(output_dir, exist_ok=True)

    # Save raw frame
    raw_path = os.path.join(output_dir, "test_frame_raw.jpg")
    cv2.imwrite(raw_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"  Raw frame: {raw_path}")

    # Save annotated frame
    annotated = frame.copy()
    height, width = frame.shape[:2]

    for detection in faces:
        bbox = detection.bounding_box
        conf = detection.categories[0].score if detection.categories else 0

        x, y = int(bbox.origin_x), int(bbox.origin_y)
        w, h = int(bbox.width), int(bbox.height)

        # Draw box
        color = (0, 255, 0) if w >= 80 else (0, 0, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

        # Draw label
        label = f"{w}x{h}px ({conf:.0%})"
        cv2.putText(annotated, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Add resolution overlay
    cv2.putText(annotated, f"{width}x{height}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    ann_path = os.path.join(output_dir, "test_frame_annotated.jpg")
    cv2.imwrite(ann_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"  Annotated: {ann_path}")

    # Save a smaller preview
    scale = 1280 / max(width, height)
    if scale < 1:
        preview = cv2.resize(annotated, None, fx=scale, fy=scale)
        prev_path = os.path.join(output_dir, "test_frame_preview.jpg")
        cv2.imwrite(prev_path, preview, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"  Preview:   {prev_path}")


def print_coverage_recommendation(width: int, height: int, room_depth: float, hfov: float = 93.0):
    """Print recommendation for camera placement."""
    hfov_rad = math.radians(hfov)
    face_width_m = 0.18

    # Calculate face pixels at room depth
    coverage_m = 2 * room_depth * math.tan(hfov_rad / 2)
    pixels_per_meter = width / coverage_m
    face_pixels_back = pixels_per_meter * face_width_m

    print(f"\n{'=' * 60}")
    print(f"COVERAGE RECOMMENDATION for {room_depth}m deep room")
    print(f"{'=' * 60}")
    print(f"Camera: {width}x{height}, {hfov}° HFOV")
    print(f"Back row distance: {room_depth}m")
    print(f"Face size at back: ~{face_pixels_back:.0f} pixels")

    if face_pixels_back >= 80:
        print("\nVERDICT: ONE CAMERA IS SUFFICIENT")
        print(f"Faces at the back row ({room_depth}m) are {face_pixels_back:.0f}px wide.")
        print(f"This is {'above' if face_pixels_back >= 160 else 'enough for'} the 80px minimum for detection.")
    else:
        # Calculate max distance where 1 camera works
        max_distance = (width * face_width_m) / (80 * 2 * math.tan(hfov_rad / 2))

        print("\nVERDICT: ONE CAMERA MAY NOT BE ENOUGH")
        print(f"Faces at {room_depth}m are only {face_pixels_back:.0f}px (need 80+).")
        print(f"Single camera works up to ~{max_distance:.1f}m depth.")
        print("\nOptions:")
        print(f"  1. CEILING MOUNT at center - reduces max distance to ~{room_depth / 2:.1f}m")

        # Check if ceiling mount solves it
        ceiling_distance = math.sqrt((room_depth / 2) ** 2 + 3**2)  # 3m ceiling
        ceiling_face_px = (width / (2 * ceiling_distance * math.tan(hfov_rad / 2))) * face_width_m
        print(
            f"     Face size from ceiling: ~{ceiling_face_px:.0f}px {'(sufficient!)' if ceiling_face_px >= 80 else '(still marginal)'}"
        )

        print("  2. TWO CAMERAS - one covers front half, one covers back half")
        half_depth = room_depth / 2
        half_face_px = (width / (2 * half_depth * math.tan(hfov_rad / 2))) * face_width_m
        print(f"     Face size per camera: ~{half_face_px:.0f}px (excellent)")

        print("  3. USE SUB-STREAM for detection, crop from MAIN stream for recognition")


def continuous_preview(cap, detect: bool = False):
    """Show continuous camera preview (press 'q' to quit, 's' to save)."""
    import cv2

    print("\nStarting live preview (press 'q' to quit, 's' to save frame)...")

    frame_count = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame, retrying...")
            time.sleep(1)
            continue

        frame_count += 1
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        display = frame.copy()
        h, w = display.shape[:2]

        # Scale for display
        scale = 1280 / max(w, h)
        if scale < 1:
            display = cv2.resize(display, None, fx=scale, fy=scale)

        # FPS overlay
        cv2.putText(display, f"{w}x{h} | {fps:.1f} FPS", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("IAMS Camera Test", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            path = f"snapshot_{int(time.time())}.jpg"
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"Saved: {path}")

    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="IAMS Camera Test Tool - Test your camera for face recognition")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--rtsp", type=str, help="RTSP URL (e.g., rtsp://admin:pass@192.168.1.100/Preview_01_main)")
    group.add_argument("--usb", type=int, nargs="?", const=0, help="USB camera index (default: 0)")

    parser.add_argument("--detect", action="store_true", help="Run face detection on captured frame")
    parser.add_argument("--save", action="store_true", help="Save test frames to disk")
    parser.add_argument("--preview", action="store_true", help="Show live camera preview window")
    parser.add_argument("--room-depth", type=float, default=0, help="Room depth in meters for coverage analysis")
    parser.add_argument(
        "--hfov", type=float, default=93.0, help="Camera horizontal FOV in degrees (default: 93 for Reolink P340)"
    )
    parser.add_argument("--transport", choices=["tcp", "udp"], default="tcp", help="RTSP transport (default: tcp)")
    parser.add_argument("--output-dir", type=str, default="test_output", help="Output directory for saved frames")

    args = parser.parse_args()

    print("=" * 60)
    print("  IAMS Camera Test Tool")
    print("  Intelligent Attendance Monitoring System")
    print("=" * 60)

    # Connect to camera
    if args.rtsp:
        cap, frame = connect_rtsp(args.rtsp, args.transport)
    else:
        cap, frame = connect_usb(args.usb)

    if cap is None or frame is None:
        print("\nFAILED: Could not connect to camera")
        sys.exit(1)

    try:
        # Analyze frame
        width, height = analyze_frame(frame, args.hfov)

        # Face detection
        faces = []
        if args.detect:
            faces = detect_faces(frame)
        else:
            print("\n[3/4] Face Detection: SKIPPED (use --detect to enable)")

        # Save results
        if args.save or args.detect:
            save_results(frame, faces, args.output_dir)
        else:
            print("\n[4/4] Save: SKIPPED (use --save to enable)")

        # Coverage recommendation
        if args.room_depth > 0:
            print_coverage_recommendation(width, height, args.room_depth, args.hfov)

        # Live preview
        if args.preview:
            continuous_preview(cap, args.detect)

        print("\nDone! Camera test complete.")

    finally:
        cap.release()


if __name__ == "__main__":
    main()
