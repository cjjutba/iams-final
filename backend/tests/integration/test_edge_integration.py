"""
Integration Tests for Edge API (Raspberry Pi Interface)

Tests the POST /face/process endpoint that receives detected faces
from edge devices and processes them for attendance tracking.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np

from app.config import settings


API = settings.API_PREFIX


class TestEdgeProcessEndpoint:
    """Tests for POST /api/v1/face/process (Edge API)"""

    @pytest.fixture()
    def mock_face_service(self):
        """Mock FaceService for edge tests.

        The edge API uses face_service.facenet.get_embedding() and
        face_service.faiss.search_with_margin() directly (not recognize_face).
        """
        with patch('app.routers.face.FaceService') as mock:
            service_instance = MagicMock()

            # Mock facenet
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()  # PIL Image mock
            )
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            service_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )

            # Mock FAISS search_with_margin to return a confident match
            service_instance.faiss.search_with_margin = MagicMock(
                return_value={
                    "user_id": "test-user-id-123",
                    "confidence": 0.85,
                    "is_ambiguous": False,
                }
            )

            # Keep recognize_face for any code that still uses it
            async def mock_recognize(img_bytes, threshold=None):
                return "test-user-id-123", 0.85

            service_instance.recognize_face = AsyncMock(side_effect=mock_recognize)

            mock.return_value = service_instance
            yield mock

    def test_process_single_face_success(
        self,
        client,
        test_room,
        test_schedule,
        test_student,
        test_enrollment,
        test_face_image_base64,
        mock_face_service
    ):
        """Edge device sends single face and gets successful match"""
        payload = {
            "room_id": str(test_room.id),
            "timestamp": datetime.utcnow().isoformat(),
            "faces": [
                {
                    "image": test_face_image_base64,
                    "bbox": [100, 150, 112, 112]
                }
            ]
        }

        # Mock presence service to avoid DB issues
        with patch('app.routers.face.PresenceService') as mock_presence:
            presence_instance = MagicMock()
            presence_instance.log_detection = AsyncMock()
            mock_presence.return_value = presence_instance

            response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["processed"] == 1
        assert len(data["data"]["matched"]) == 1
        assert data["data"]["unmatched"] == 0

        # Check matched user
        matched = data["data"]["matched"][0]
        assert matched["user_id"] == "test-user-id-123"
        assert matched["confidence"] == 0.85

    def test_process_multiple_faces(
        self,
        client,
        test_room,
        test_face_image_base64,
        mock_face_service
    ):
        """Edge device sends multiple faces for batch processing"""
        payload = {
            "room_id": str(test_room.id),
            "timestamp": datetime.utcnow().isoformat(),
            "faces": [
                {"image": test_face_image_base64, "bbox": [100, 100, 112, 112]},
                {"image": test_face_image_base64, "bbox": [300, 100, 112, 112]},
                {"image": test_face_image_base64, "bbox": [500, 100, 112, 112]},
            ]
        }

        with patch('app.routers.face.PresenceService') as mock_presence:
            presence_instance = MagicMock()
            presence_instance.log_detection = AsyncMock()
            mock_presence.return_value = presence_instance

            response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["processed"] == 3
        assert len(data["data"]["matched"]) == 3

    def test_process_no_match_faces(self, client, test_room, test_face_image_base64):
        """Edge device sends faces that don't match any registered users"""
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            # Mock embedding generation + no match via search_with_margin
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            service_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )
            service_instance.faiss.search_with_margin = MagicMock(
                return_value={
                    "user_id": None,
                    "confidence": None,
                    "is_ambiguous": False,
                }
            )
            mock_service.return_value = service_instance

            payload = {
                "room_id": str(test_room.id),
                "timestamp": datetime.utcnow().isoformat(),
                "faces": [
                    {"image": test_face_image_base64, "bbox": [100, 100, 112, 112]}
                ]
            }

            response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["processed"] == 1
        assert len(data["data"]["matched"]) == 0
        assert data["data"]["unmatched"] == 1

    def test_process_mixed_results(self, client, test_room, test_face_image_base64):
        """Some faces match, others don't"""
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            # Mock get_embedding
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            service_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )

            # Mock search_with_margin to alternate match/no match
            call_count = 0

            def mock_search_with_margin(embedding, k=3, threshold=None, margin=None):
                nonlocal call_count
                call_count += 1
                if call_count % 2 == 1:
                    return {
                        "user_id": f"user-{call_count}",
                        "confidence": 0.85,
                        "is_ambiguous": False,
                    }
                else:
                    return {
                        "user_id": None,
                        "confidence": None,
                        "is_ambiguous": False,
                    }

            service_instance.faiss.search_with_margin = MagicMock(
                side_effect=mock_search_with_margin
            )
            mock_service.return_value = service_instance

            payload = {
                "room_id": str(test_room.id),
                "timestamp": datetime.utcnow().isoformat(),
                "faces": [
                    {"image": test_face_image_base64, "bbox": [100, 100, 112, 112]},
                    {"image": test_face_image_base64, "bbox": [200, 100, 112, 112]},
                    {"image": test_face_image_base64, "bbox": [300, 100, 112, 112]},
                    {"image": test_face_image_base64, "bbox": [400, 100, 112, 112]},
                ]
            }

            response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["processed"] == 4
        assert len(data["data"]["matched"]) == 2
        assert data["data"]["unmatched"] == 2

    def test_process_invalid_base64_image(self, client, test_room):
        """
        Edge device sends invalid Base64 data.

        Invalid Base64 is handled gracefully: the face is counted as unmatched
        but NOT processed (processed=0), since we couldn't decode the image.
        """
        payload = {
            "room_id": str(test_room.id),
            "timestamp": datetime.utcnow().isoformat(),
            "faces": [
                {"image": "not-valid-base64!@#$%", "bbox": [100, 100, 112, 112]}
            ]
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Should handle gracefully: success=True, but face counted as unmatched
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["processed"] == 0  # Invalid Base64 prevents processing
        assert data["data"]["unmatched"] == 1  # But counts as unmatched

    def test_process_empty_faces_array(self, client, test_room):
        """
        Edge device sends request with no faces - should be rejected.

        Empty faces arrays are now rejected at schema level (422 validation error).
        The RPi should only send requests when it detects faces.
        """
        payload = {
            "room_id": str(test_room.id),
            "timestamp": datetime.utcnow().isoformat(),
            "faces": []
        }

        response = client.post(f"{API}/face/process", json=payload)

        # Schema validation should reject empty faces array
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "ValidationError"
        # Verify the error mentions faces field
        assert any("faces" in str(detail) for detail in data["error"]["details"])

    def test_process_missing_room_id(self, client, test_face_image_base64):
        """Request without room_id should fail validation"""
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "faces": [{"image": test_face_image_base64}]
        }

        response = client.post(f"{API}/face/process", json=payload)

        assert response.status_code == 422  # Validation error

    def test_process_no_active_schedule(
        self,
        client,
        test_room,
        test_face_image_base64,
        mock_face_service
    ):
        """Process faces when no schedule is active for the room"""
        # Send request at time when no schedule is active
        payload = {
            "room_id": str(test_room.id),
            "timestamp": "2024-01-15T02:00:00Z",  # 2 AM, unlikely to have class
            "faces": [{"image": test_face_image_base64, "bbox": [100, 100, 112, 112]}]
        }

        with patch('app.routers.face.PresenceService') as mock_presence:
            presence_instance = MagicMock()
            presence_instance.log_detection = AsyncMock()
            mock_presence.return_value = presence_instance

            with patch('app.routers.face.ScheduleRepository') as mock_repo:
                repo_instance = MagicMock()
                repo_instance.get_current_schedule = MagicMock(return_value=None)
                mock_repo.return_value = repo_instance

                response = client.post(f"{API}/face/process", json=payload)

        # Should still return success but log warning
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Faces were recognized but presence not logged
        assert data["data"]["processed"] >= 0


class TestEdgeDeviceConcurrency:
    """Tests for multiple edge devices sending data concurrently"""

    def test_concurrent_device_requests(
        self,
        client,
        test_room,
        test_face_image_base64
    ):
        """Multiple edge devices send requests simultaneously"""
        import concurrent.futures

        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            service_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )
            service_instance.faiss.search_with_margin = MagicMock(
                return_value={
                    "user_id": "concurrent-user-123",
                    "confidence": 0.80,
                    "is_ambiguous": False,
                }
            )
            mock_service.return_value = service_instance

            with patch('app.routers.face.PresenceService'):
                # Simulate 5 concurrent requests
                def send_request(i):
                    payload = {
                        "room_id": str(test_room.id),
                        "timestamp": datetime.utcnow().isoformat(),
                        "faces": [{"image": test_face_image_base64}]
                    }
                    return client.post(f"{API}/face/process", json=payload)

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(send_request, i) for i in range(5)]
                    responses = [f.result() for f in futures]

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            assert response.json()["success"] is True


class TestEdgeQueueSimulation:
    """Simulate edge device queue behavior (offline/online transitions)"""

    def test_batch_processing_after_offline_period(
        self,
        client,
        test_room,
        test_face_image_base64
    ):
        """
        Simulate edge device coming back online and sending queued detections.
        Edge device accumulated 10 detections while offline.
        """
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            service_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )
            service_instance.faiss.search_with_margin = MagicMock(
                return_value={
                    "user_id": "offline-user-456",
                    "confidence": 0.88,
                    "is_ambiguous": False,
                }
            )
            mock_service.return_value = service_instance

            with patch('app.routers.face.PresenceService'):
                # Send 10 queued requests rapidly
                responses = []
                for i in range(10):
                    payload = {
                        "room_id": str(test_room.id),
                        "timestamp": datetime.utcnow().isoformat(),
                        "faces": [{"image": test_face_image_base64}]
                    }
                    response = client.post(f"{API}/face/process", json=payload)
                    responses.append(response)

        # All should be processed successfully
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["processed"] == 1


class TestEdgeErrorHandling:
    """Test edge API error handling and resilience"""

    def test_process_with_faiss_search_error(
        self,
        client,
        test_room,
        test_face_image_base64
    ):
        """Handle FAISS search errors gracefully"""
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            # Mock embedding generation to succeed
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            service_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )

            # Mock search_with_margin to raise exception
            service_instance.faiss.search_with_margin = MagicMock(
                side_effect=Exception("FAISS index error")
            )
            mock_service.return_value = service_instance

            payload = {
                "room_id": str(test_room.id),
                "timestamp": datetime.utcnow().isoformat(),
                "faces": [{"image": test_face_image_base64}]
            }

            response = client.post(f"{API}/face/process", json=payload)

        # Should handle error and count as processed but unmatched
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["processed"] == 1
        assert data["data"]["unmatched"] == 1

    def test_process_with_presence_logging_error(
        self,
        client,
        test_room,
        test_schedule,
        test_student,
        test_face_image_base64
    ):
        """
        Face recognition succeeds but presence logging fails.
        Should still return successful recognition result.
        """
        # Mock FaceService with margin-aware search
        with patch('app.routers.face.FaceService') as mock_face_svc:
            face_instance = MagicMock()
            face_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            # Mock embedding generation + margin-aware search
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            face_instance.facenet.get_embedding = MagicMock(
                return_value=mock_embedding
            )
            face_instance.faiss.search_with_margin = MagicMock(
                return_value={
                    "user_id": str(test_student.id),
                    "confidence": 0.85,
                    "is_ambiguous": False,
                }
            )
            mock_face_svc.return_value = face_instance

            # Mock PresenceService to raise exception on feed_detection
            with patch('app.routers.face.PresenceService') as mock_presence:
                presence_instance = MagicMock()
                presence_instance.feed_detection = AsyncMock(
                    side_effect=Exception("Database error")
                )
                mock_presence.return_value = presence_instance

                with patch('app.routers.face.ScheduleRepository') as mock_repo:
                    repo_instance = MagicMock()
                    repo_instance.get_current_schedule = MagicMock(
                        return_value=test_schedule
                    )
                    mock_repo.return_value = repo_instance

                    payload = {
                        "room_id": str(test_room.id),
                        "timestamp": datetime.utcnow().isoformat(),
                        "faces": [{"image": test_face_image_base64}]
                    }

                    response = client.post(f"{API}/face/process", json=payload)

        # Should succeed despite logging error
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Face was recognized successfully
        assert len(data["data"]["matched"]) == 1
        assert data["data"]["matched"][0]["user_id"] == str(test_student.id)
