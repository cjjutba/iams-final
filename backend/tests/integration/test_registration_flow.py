"""
Integration Tests for Face Registration & Recognition Flow

Tests the complete face registration workflow from student signup
through face capture to recognition.
"""

import pytest
import io
from PIL import Image
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np

from app.config import settings


API = settings.API_PREFIX


class TestFaceRegistrationFlow:
    """Test complete face registration workflow"""

    def _create_test_image_file(self, filename="test.jpg"):
        """Helper to create a mock UploadFile"""
        from fastapi import UploadFile

        img = Image.new('RGB', (160, 160), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)

        return UploadFile(
            file=img_bytes,
            filename=filename
        )

    @pytest.mark.asyncio
    async def test_register_face_minimum_images(
        self,
        db_session,
        test_student
    ):
        """Register face with minimum 3 images"""
        from app.services.face_service import FaceService

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            def mock_embedding(img_bytes):
                emb = np.random.randn(512).astype(np.float32)
                return emb / np.linalg.norm(emb)

            mock_facenet.get_embedding = MagicMock(side_effect=mock_embedding)

            # Mock FAISS
            mock_faiss.add = MagicMock(return_value=1)
            mock_faiss.save = MagicMock()

            face_service = FaceService(db_session)

            # Create 3 test images
            images = [self._create_test_image_file(f"face_{i}.jpg") for i in range(3)]

            # Register face
            faiss_id, message = await face_service.register_face(
                str(test_student.id),
                images
            )

            assert faiss_id == 1
            assert "successfully" in message.lower()

            # Verify embedding was added to FAISS
            mock_faiss.add.assert_called_once()
            mock_faiss.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_face_maximum_images(
        self,
        db_session,
        test_student
    ):
        """Register face with maximum 5 images"""
        from app.services.face_service import FaceService

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            def mock_embedding(img_bytes):
                emb = np.random.randn(512).astype(np.float32)
                return emb / np.linalg.norm(emb)

            mock_facenet.get_embedding = MagicMock(side_effect=mock_embedding)

            # Mock FAISS
            mock_faiss.add = MagicMock(return_value=2)
            mock_faiss.save = MagicMock()

            face_service = FaceService(db_session)

            # Create 5 test images
            images = [self._create_test_image_file(f"face_{i}.jpg") for i in range(5)]

            # Register face
            faiss_id, message = await face_service.register_face(
                str(test_student.id),
                images
            )

            assert faiss_id == 2
            assert "successfully" in message.lower()

    @pytest.mark.asyncio
    async def test_register_face_too_few_images(
        self,
        db_session,
        test_student
    ):
        """Attempt to register with fewer than 3 images should fail"""
        from app.services.face_service import FaceService
        from app.utils.exceptions import ValidationError

        face_service = FaceService(db_session)

        # Create only 2 images
        images = [self._create_test_image_file(f"face_{i}.jpg") for i in range(2)]

        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await face_service.register_face(str(test_student.id), images)

        assert "minimum" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_register_face_too_many_images(
        self,
        db_session,
        test_student
    ):
        """Attempt to register with more than 5 images should fail"""
        from app.services.face_service import FaceService
        from app.utils.exceptions import ValidationError

        face_service = FaceService(db_session)

        # Create 6 images
        images = [self._create_test_image_file(f"face_{i}.jpg") for i in range(6)]

        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await face_service.register_face(str(test_student.id), images)

        assert "maximum" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_face(
        self,
        db_session,
        test_student
    ):
        """Attempt to register face twice should fail"""
        from app.services.face_service import FaceService
        from app.utils.exceptions import ValidationError

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            def mock_embedding(img_bytes):
                emb = np.random.randn(512).astype(np.float32)
                return emb / np.linalg.norm(emb)

            mock_facenet.get_embedding = MagicMock(side_effect=mock_embedding)
            mock_faiss.add = MagicMock(return_value=1)
            mock_faiss.save = MagicMock()

            face_service = FaceService(db_session)

            # First registration
            images = [self._create_test_image_file(f"face_{i}.jpg") for i in range(3)]
            await face_service.register_face(str(test_student.id), images)

            # Second registration should fail
            images2 = [self._create_test_image_file(f"face2_{i}.jpg") for i in range(3)]

            with pytest.raises(ValidationError) as exc_info:
                await face_service.register_face(str(test_student.id), images2)

            assert "already" in str(exc_info.value).lower()


class TestFaceReregistrationFlow:
    """Test face re-registration (update) workflow"""

    def _create_test_image_file(self, filename="test.jpg"):
        """Helper to create a mock UploadFile"""
        from fastapi import UploadFile

        img = Image.new('RGB', (160, 160), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)

        return UploadFile(
            file=img_bytes,
            filename=filename
        )

    @pytest.mark.asyncio
    async def test_reregister_existing_face(
        self,
        db_session,
        test_student
    ):
        """Re-register existing face successfully"""
        from app.services.face_service import FaceService

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            def mock_embedding(img_bytes):
                emb = np.random.randn(512).astype(np.float32)
                return emb / np.linalg.norm(emb)

            mock_facenet.get_embedding = MagicMock(side_effect=mock_embedding)
            mock_faiss.add = MagicMock(side_effect=[1, 2])  # Two registrations
            mock_faiss.save = MagicMock()

            face_service = FaceService(db_session)

            # Initial registration
            images1 = [self._create_test_image_file(f"face_{i}.jpg") for i in range(3)]
            faiss_id1, _ = await face_service.register_face(
                str(test_student.id),
                images1
            )

            # Re-registration
            images2 = [self._create_test_image_file(f"new_{i}.jpg") for i in range(3)]
            faiss_id2, message = await face_service.reregister_face(
                str(test_student.id),
                images2
            )

            assert faiss_id2 == 2
            assert faiss_id2 != faiss_id1
            assert "re-registered" in message.lower()


class TestFaceRecognitionFlow:
    """Test face recognition workflow"""

    @pytest.mark.asyncio
    async def test_recognize_registered_face(
        self,
        db_session,
        test_student
    ):
        """Recognize a face that was previously registered"""
        from app.services.face_service import FaceService

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            test_embedding = np.random.randn(512).astype(np.float32)
            test_embedding = test_embedding / np.linalg.norm(test_embedding)

            mock_facenet.get_embedding = MagicMock(return_value=test_embedding)

            # Mock FAISS search to return match
            mock_faiss.search = MagicMock(
                return_value=[(str(test_student.id), 0.92)]
            )

            face_service = FaceService(db_session)

            # Recognize face
            img = Image.new('RGB', (112, 112), color='blue')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()

            user_id, confidence = await face_service.recognize_face(img_bytes)

            assert user_id == str(test_student.id)
            assert confidence == 0.92

    @pytest.mark.asyncio
    async def test_recognize_unknown_face(
        self,
        db_session
    ):
        """Recognize a face that is not registered"""
        from app.services.face_service import FaceService

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            test_embedding = np.random.randn(512).astype(np.float32)
            test_embedding = test_embedding / np.linalg.norm(test_embedding)

            mock_facenet.get_embedding = MagicMock(return_value=test_embedding)

            # Mock FAISS search to return no match
            mock_faiss.search = MagicMock(return_value=[])

            face_service = FaceService(db_session)

            # Recognize face
            img = Image.new('RGB', (112, 112), color='red')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()

            user_id, confidence = await face_service.recognize_face(img_bytes)

            assert user_id is None
            assert confidence is None

    @pytest.mark.asyncio
    async def test_recognize_with_custom_threshold(
        self,
        db_session,
        test_student
    ):
        """Recognize face with custom confidence threshold"""
        from app.services.face_service import FaceService

        with patch('app.services.face_service.insightface_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            test_embedding = np.random.randn(512).astype(np.float32)
            test_embedding = test_embedding / np.linalg.norm(test_embedding)

            mock_facenet.get_embedding = MagicMock(return_value=test_embedding)

            # Mock FAISS search with custom threshold
            mock_faiss.search = MagicMock(
                return_value=[(str(test_student.id), 0.75)]
            )

            face_service = FaceService(db_session)

            # Recognize with threshold 0.7
            img = Image.new('RGB', (112, 112), color='green')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()

            user_id, confidence = await face_service.recognize_face(
                img_bytes,
                threshold=0.7
            )

            assert user_id == str(test_student.id)
            assert confidence == 0.75

            # Verify threshold was passed to FAISS
            mock_faiss.search.assert_called_with(
                test_embedding,
                k=1,
                threshold=0.7
            )


class TestFaceAPIEndpoints:
    """Test face registration/recognition API endpoints"""

    def test_register_face_endpoint(
        self,
        client,
        test_student,
        auth_headers_student
    ):
        """Test POST /face/register endpoint"""
        # Create mock files
        files = []
        for i in range(3):
            img = Image.new('RGB', (160, 160), color='blue')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes.seek(0)
            files.append(('images', ('face.jpg', img_bytes, 'image/jpeg')))

        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()

            async def mock_register(user_id, images):
                return 123, "Face registered successfully"

            service_instance.register_face = AsyncMock(side_effect=mock_register)
            mock_service.return_value = service_instance

            response = client.post(
                f"{API}/face/register",
                files=files,
                headers=auth_headers_student
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["embedding_id"] == 123

    def test_get_face_status_registered(
        self,
        client,
        test_student,
        auth_headers_student
    ):
        """Test GET /face/status for registered user"""
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.get_face_status = MagicMock(
                return_value={
                    "registered": True,
                    "registered_at": "2024-01-15T10:00:00",
                    "embedding_id": 456
                }
            )
            mock_service.return_value = service_instance

            response = client.get(
                f"{API}/face/status",
                headers=auth_headers_student
            )

        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is True
        assert data["embedding_id"] == 456

    def test_get_face_status_not_registered(
        self,
        client,
        test_student,
        auth_headers_student
    ):
        """Test GET /face/status for user without face registration"""
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.get_face_status = MagicMock(
                return_value={
                    "registered": False,
                    "registered_at": None,
                    "embedding_id": None
                }
            )
            mock_service.return_value = service_instance

            response = client.get(
                f"{API}/face/status",
                headers=auth_headers_student
            )

        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is False
        assert data["embedding_id"] is None
