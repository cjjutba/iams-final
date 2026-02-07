# Edge Device Specialist - Agent Memory

## Critical Learnings

### Camera Initialization Strategy
- **Try picamera2 first, fallback to OpenCV** - Pi Camera Module is preferred but USB webcam fallback is essential
- **Test capture after initialization** - Camera may report as "opened" but fail to capture frames
- **Wait 2 seconds after camera start** - Camera needs time to stabilize before first capture
- **picamera2 returns RGB, OpenCV returns BGR** - Always convert picamera2 to BGR for consistency

### MediaPipe on Raspberry Pi
- **Use MediaPipe 0.10.8** - Latest version with ARM64 support
- **Short-range model (0) is faster** - Best for indoor classroom scenarios (up to 2m)
- **Confidence threshold 0.5 is balanced** - Lower = more false positives, higher = missed faces
- **MediaPipe Face Detection uses TFLite runtime** - Efficient on ARM CPU without GPU
- **Bounding box coordinates are absolute pixels** - Not normalized like some models

### Queue Management Patterns
- **Use collections.deque(maxlen=500)** - Automatic oldest-item dropping when full
- **Thread-safe operations with threading.Lock** - Queue accessed from main thread and retry worker
- **TTL enforcement before retry** - Remove stale entries before processing queue
- **Exponential backoff for retries** - 1s, 2s, 4s to avoid overwhelming backend
- **Separate retry worker thread** - Non-blocking queue processing

### HTTP Communication Best Practices
- **Use httpx for async HTTP** - Better than requests for async/await patterns
- **Connection pooling reduces overhead** - Reuse HTTP client across requests
- **Classify errors for retry decisions** - 4xx = permanent (no retry), 5xx/network = transient (retry)
- **Timeout must be < scan interval** - Prevent request pileup

### Configuration Validation
- **Fail fast on startup** - Validate all config before initializing components
- **BACKEND_URL and ROOM_ID are required** - System cannot function without these
- **Provide actionable error messages** - Tell user exactly what's wrong and how to fix

### Resource Management
- **Use context managers (with statements)** - Ensures proper cleanup on errors
- **Graceful shutdown on SIGTERM/SIGINT** - Handle Ctrl+C and systemd stop
- **Close resources in reverse order** - Stop retry worker → detector → camera → HTTP client
- **Log all resource lifecycle events** - Initialization, errors, shutdown for debugging

### Performance Optimization
- **15 FPS is sufficient for attendance** - Higher FPS wastes CPU without accuracy gain
- **640x480 resolution balances quality and speed** - Higher resolution slows detection
- **JPEG quality 70% is optimal** - Lower quality reduces file size with minimal quality loss
- **Process all detected faces in batch** - More efficient than one-by-one

### Edge API Contract
- **POST /api/v1/face/process** - Matches EdgeProcessRequest schema in backend
- **Timestamp must be ISO 8601 format** - `datetime.isoformat() + "Z"`
- **Faces array supports batch processing** - Send multiple faces per request
- **Bounding box format: [x, y, width, height]** - Matches MediaPipe output

## File Structure Implemented

```
edge/
├── app/
│   ├── __init__.py       # Package metadata
│   ├── main.py           # Main application entry point
│   ├── config.py         # Environment variable management
│   ├── camera.py         # Camera capture (picamera2 + OpenCV fallback)
│   ├── detector.py       # MediaPipe face detection
│   ├── processor.py      # Face cropping and JPEG encoding
│   ├── sender.py         # HTTP client for backend API
│   └── queue_manager.py  # Offline queue with retry logic
├── run.py                # Entry point script
├── requirements.txt      # ARM-compatible dependencies
├── .env.example          # Configuration template
└── README.md             # Setup and deployment guide
```

## Deployment Patterns

### Systemd Service Pattern
- **Service runs as pi user** - Avoid running as root
- **WorkingDirectory = /home/pi/iams/edge** - Ensures .env is found
- **Restart=always, RestartSec=10** - Auto-restart on crashes
- **StandardOutput=journal** - Logs to systemd journal
- **Environment="PYTHONUNBUFFERED=1"** - Immediate log output

### Network Topology Considerations
- **Edge device and backend on same LAN** - Lowest latency, no firewall issues
- **Backend URL must be IP or resolvable hostname** - DNS may not work on all networks
- **Port 8000 must be accessible** - Check firewall rules on backend server

## Common Pitfalls

### Camera Not Detected
- **Pi Camera requires libcamera** - Must be installed and camera interface enabled
- **USB Webcam requires video group** - Add user to video group: `usermod -a -G video pi`
- **Wrong CAMERA_INDEX** - Try 0, 1, 2 to find correct device

### MediaPipe Import Errors
- **Python version must be 3.9+** - MediaPipe ARM wheels not available for older versions
- **Virtual environment recommended** - Avoid system package conflicts
- **May need to install libopencv-dev** - Some ARM systems require this

### Queue Growing Indefinitely
- **Backend down for extended period** - Queue fills to 500, starts dropping
- **Network latency too high** - Requests timeout faster than queue can drain
- **Solution: Monitor queue size in logs** - Alert if utilization > 50%

## Future Enhancements

### Potential Improvements
- **Add GPU acceleration support** - If Raspberry Pi 5 GPU support becomes available
- **Implement frame skipping** - Process every Nth frame to reduce CPU load
- **Add local face caching** - Remember recent detections to reduce duplicate sends
- **Implement health check endpoint** - HTTP server for monitoring edge device status
- **Add prometheus metrics** - Export queue size, FPS, error rate for Grafana

### Testing Recommendations
- **Unit tests for processor.py** - Mock frame data, verify crop/resize/encode
- **Integration tests with video file** - Use pre-recorded video instead of live camera
- **Network failure simulation** - Test queue and retry logic by blocking backend
- **Performance benchmarks** - Measure FPS and latency on actual Raspberry Pi 4/5

## References

- **MediaPipe Face Detection:** https://google.github.io/mediapipe/solutions/face_detection
- **picamera2 Documentation:** https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
- **Backend API Contract:** `backend/app/routers/face.py` (POST /face/process)
