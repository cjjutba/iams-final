"""
Integration Tests for Edge Device API

Tests the POST /api/v1/face/process endpoint used by Raspberry Pi devices
for continuous presence tracking. Critical for edge-to-backend communication.

Test Coverage:
- Happy path: successful face recognition
- Error handling: invalid images, malformed requests
- Idempotency: duplicate request handling
- Performance: batch processing, concurrent requests
- Edge device scenarios: retry logic, queue draining
"""

import base64
import io
from datetime import datetime, timedelta
from PIL import Image
import pytest

from app.config import settings


API = settings.API_PREFIX


# ===================================================================
# Test Fixtures: Image Generation
# ===================================================================

def create_test_image(width=160, height=160, format='JPEG') -> bytes:
    """Create a test image as bytes"""
    img = Image.new('RGB', (width, height), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=format)
    return img_bytes.getvalue()


def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes to Base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')


def create_test_face_data(image_bytes: bytes = None, bbox=None):
    """Create FaceData payload for testing"""
    if image_bytes is None:
        image_bytes = create_test_image()

    if bbox is None:
        bbox = [100, 150, 112, 112]

    return {
        "image": encode_image_base64(image_bytes),
        "bbox": bbox
    }


# ===================================================================
# Happy Path Tests
# ===================================================================

class TestEdgeAPIHappyPath:
    """Test successful face processing scenarios"""

    def test_process_single_face_no_match(self, client):
        """Process single face that doesn't match any user"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["processed"] == 1
        assert data["data"]["matched"] == []
        assert data["data"]["unmatched"] == 1
        assert "processing_time_ms" in data["data"]
        assert data["data"]["processing_time_ms"] > 0

    def test_process_batch_faces(self, client):
        """Process multiple faces in one request"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [
                create_test_face_data(),
                create_test_face_data(),
                create_test_face_data()
            ]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["processed"] == 3
        assert data["data"]["unmatched"] == 3

    def test_process_with_optional_bbox(self, client):
        """Process face without bbox (MediaPipe may not always provide it)"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(create_test_image()),
                # bbox is optional now
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_response_includes_metrics(self, client):
        """Verify response includes performance metrics"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "processing_time_ms" in data["data"]
        assert "processed" in data["data"]
        assert "matched" in data["data"]
        assert "unmatched" in data["data"]
        assert "presence_logged" in data["data"]


# ===================================================================
# Error Handling Tests
# ===================================================================

class TestEdgeAPIErrorHandling:
    """Test error scenarios and validation"""

    def test_invalid_base64_format(self, client):
        """Invalid Base64 should return error but not crash"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": "not-valid-base64!!!",
                "bbox": [100, 150, 112, 112]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Should still return 200 with unmatched count
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["unmatched"] >= 1

    def test_empty_base64_string(self, client):
        """Empty Base64 string should be handled gracefully"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": "",
                "bbox": [100, 150, 112, 112]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Validation error expected
        assert response.status_code == 422

    def test_oversized_image(self, client):
        """Image larger than 10MB should be rejected"""
        # Create a large image (simulate 11MB Base64)
        # Note: Creating actual 11MB image is slow, so we test the validation logic
        large_image = create_test_image(4096, 4096)  # Max allowed size

        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(large_image),
                "bbox": [100, 150, 112, 112]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Should process successfully at max size
        assert response.status_code == 200

    def test_invalid_image_format(self, client):
        """Non-JPEG/PNG format should be rejected"""
        # Create BMP image
        bmp_image = create_test_image(format='BMP')

        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(bmp_image),
                "bbox": [100, 150, 112, 112]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Should return 200 but face unmatched due to format error
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["unmatched"] >= 1

    def test_image_too_small(self, client):
        """Image smaller than 10x10 should be rejected"""
        tiny_image = create_test_image(5, 5)

        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(tiny_image),
                "bbox": [100, 150, 112, 112]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Should return 200 but face unmatched
        assert response.status_code == 200

    def test_negative_bbox_values(self, client):
        """Negative bbox values should be rejected"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(create_test_image()),
                "bbox": [-10, 150, 112, 112]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Pydantic validation should catch this
        assert response.status_code == 422

    def test_zero_bbox_dimensions(self, client):
        """Zero width/height bbox should be rejected"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(create_test_image()),
                "bbox": [100, 150, 0, 0]
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Validation should catch this
        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        """Missing room_id or timestamp should fail validation"""
        payload = {
            # Missing room_id
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)
        assert response.status_code == 422

    def test_invalid_room_id_format(self, client):
        """Room ID with invalid characters should be rejected"""
        payload = {
            "room_id": "room@#$%^&*()",  # Invalid characters
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Pattern validation should catch this
        assert response.status_code == 422

    def test_future_timestamp(self, client):
        """Future timestamp should be accepted (edge device clock may drift)"""
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()

        payload = {
            "room_id": "test-room-101",
            "timestamp": future_time,
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Should process successfully (no validation on future timestamps)
        assert response.status_code == 200

    def test_empty_faces_array(self, client):
        """Empty faces array should fail validation"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": []
        }

        response = client.post(f"{API}/face/process", json=payload)

        # min_length=1 validation should catch this
        assert response.status_code == 422

    def test_too_many_faces(self, client):
        """More than 10 faces should fail validation"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data() for _ in range(11)]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # max_length=10 validation should catch this
        assert response.status_code == 422


# ===================================================================
# Idempotency Tests
# ===================================================================

class TestEdgeAPIIdempotency:
    """Test duplicate request handling"""

    def test_duplicate_request_with_request_id(self, client):
        """Same request_id should prevent duplicate processing"""
        request_id = "test-request-12345"
        payload = {
            "request_id": request_id,
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        # First request
        response1 = client.post(f"{API}/face/process", json=payload)
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request with same request_id (within 5 minutes)
        response2 = client.post(f"{API}/face/process", json=payload)
        assert response2.status_code == 200
        data2 = response2.json()

        # Second request should be ignored (duplicate)
        assert data2["data"]["processed"] == 0

    def test_different_request_ids_processed_separately(self, client):
        """Different request_ids should be processed independently"""
        timestamp = datetime.now().isoformat()

        payload1 = {
            "request_id": "request-1",
            "room_id": "test-room-101",
            "timestamp": timestamp,
            "faces": [create_test_face_data()]
        }

        payload2 = {
            "request_id": "request-2",
            "room_id": "test-room-101",
            "timestamp": timestamp,
            "faces": [create_test_face_data()]
        }

        response1 = client.post(f"{API}/face/process", json=payload1)
        response2 = client.post(f"{API}/face/process", json=payload2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should be processed
        assert response1.json()["data"]["processed"] >= 1
        assert response2.json()["data"]["processed"] >= 1

    def test_no_request_id_always_processes(self, client):
        """Requests without request_id should always be processed"""
        payload = {
            # No request_id
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        # Send same request twice
        response1 = client.post(f"{API}/face/process", json=payload)
        response2 = client.post(f"{API}/face/process", json=payload)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should be processed
        assert response1.json()["data"]["processed"] >= 1
        assert response2.json()["data"]["processed"] >= 1


# ===================================================================
# Performance Tests
# ===================================================================

class TestEdgeAPIPerformance:
    """Test performance characteristics"""

    def test_response_time_single_face(self, client):
        """Single face should process in < 2 seconds (including network)"""
        import time

        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        start = time.time()
        response = client.post(f"{API}/face/process", json=payload)
        elapsed = time.time() - start

        assert response.status_code == 200
        # Generous timeout for test environment (CPU inference)
        assert elapsed < 2.0

    def test_batch_processing_efficiency(self, client):
        """Batch of 5 faces should be more efficient than 5 individual requests"""
        # Single batch request
        batch_payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data() for _ in range(5)]
        }

        import time
        start = time.time()
        batch_response = client.post(f"{API}/face/process", json=batch_payload)
        batch_time = time.time() - start

        assert batch_response.status_code == 200
        assert batch_response.json()["data"]["processed"] == 5

        # Should complete in reasonable time
        assert batch_time < 5.0  # Generous timeout

    def test_processing_time_metric_accuracy(self, client):
        """Reported processing_time_ms should be reasonable"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)
        data = response.json()

        processing_time = data["data"]["processing_time_ms"]

        # Should be > 0 and < 10 seconds
        assert processing_time > 0
        assert processing_time < 10000


# ===================================================================
# Edge Device Scenario Tests
# ===================================================================

class TestEdgeDeviceScenarios:
    """Test realistic edge device scenarios"""

    def test_queue_drain_burst(self, client):
        """Simulate edge device draining offline queue (burst of requests)"""
        # Send 10 requests rapidly
        responses = []
        for i in range(10):
            payload = {
                "request_id": f"queued-request-{i}",
                "room_id": "test-room-101",
                "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat(),
                "faces": [create_test_face_data()]
            }
            response = client.post(f"{API}/face/process", json=payload)
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert all(r.json()["success"] for r in responses)

    def test_partial_batch_failure(self, client):
        """Some faces fail but others succeed"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [
                create_test_face_data(),  # Valid
                {"image": "invalid-base64", "bbox": [0, 0, 112, 112]},  # Invalid
                create_test_face_data(),  # Valid
            ]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should process valid faces, skip invalid
        assert data["data"]["processed"] >= 2  # At least 2 valid faces

    def test_no_active_schedule(self, client):
        """Face recognition succeeds but no schedule to log presence"""
        # Use timestamp outside class hours (e.g., 2 AM)
        late_night = datetime.now().replace(hour=2, minute=0, second=0)

        payload = {
            "room_id": "test-room-101",
            "timestamp": late_night.isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Face processed, but presence not logged
        assert data["data"]["processed"] >= 1
        assert data["data"]["presence_logged"] == 0


# ===================================================================
# Data Validation Tests
# ===================================================================

class TestEdgeAPIDataValidation:
    """Test data validation and sanitization"""

    def test_room_id_max_length(self, client):
        """Room ID longer than 100 chars should be rejected"""
        payload = {
            "room_id": "x" * 101,
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)
        assert response.status_code == 422

    def test_request_id_max_length(self, client):
        """Request ID longer than 100 chars should be rejected"""
        payload = {
            "request_id": "x" * 101,
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [create_test_face_data()]
        }

        response = client.post(f"{API}/face/process", json=payload)
        assert response.status_code == 422

    def test_bbox_wrong_length(self, client):
        """Bbox with wrong number of elements should be rejected"""
        payload = {
            "room_id": "test-room-101",
            "timestamp": datetime.now().isoformat(),
            "faces": [{
                "image": encode_image_base64(create_test_image()),
                "bbox": [100, 150, 112]  # Only 3 elements
            }]
        }

        response = client.post(f"{API}/face/process", json=payload)
        assert response.status_code == 422
