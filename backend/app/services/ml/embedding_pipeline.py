"""
Shared face embedding pipeline used by BOTH registration and recognition.

Guarantees identical preprocessing for both paths:
1. Detection: SCRFD (same model)
2. Alignment: 5-point landmark warp
3. Preprocessing: CLAHE + resize 112x112 + normalize [-1,1]
4. Embedding: ArcFace ONNX -> 512-dim L2-normalized
"""

import logging

import numpy as np

from app.services.ml.insightface_model import insightface_model

logger = logging.getLogger(__name__)


async def embed_face(image_bytes: bytes) -> np.ndarray | None:
    """Generate a 512-dim L2-normalized embedding from face image bytes.

    Used by both registration and recognition paths.
    Returns None if no face detected.
    """
    try:
        result = insightface_model.get_face_with_quality(image_bytes)
    except ValueError:
        # get_face_with_quality raises ValueError when no face is detected
        return None
    if result is None:
        return None
    return result["embedding"]


async def embed_faces_batch(images: list[bytes]) -> list[np.ndarray | None]:
    """Batch version of embed_face."""
    results = []
    for img_bytes in images:
        emb = await embed_face(img_bytes)
        results.append(emb)
    return results


def validate_registration_embeddings(
    embeddings: list[np.ndarray],
    min_cross_similarity: float = 0.5,
) -> tuple[bool, str]:
    """Validate that all registration embeddings are from the same person.

    Checks pairwise cosine similarity between all embeddings.
    Since embeddings are already L2-normalized, dot product = cosine similarity.
    """
    if len(embeddings) < 2:
        return True, "Single embedding, no cross-validation needed"

    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = float(np.dot(embeddings[i], embeddings[j]))
            if sim < min_cross_similarity:
                return False, (
                    f"Embeddings {i} and {j} have low similarity ({sim:.3f}). "
                    f"Ensure all captures are of the same person."
                )
    return True, "All embeddings are consistent"


def average_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    """Average and L2-normalize embeddings for FAISS storage."""
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg
