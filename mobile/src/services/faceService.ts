/**
 * Face Service
 *
 * Handles face registration and management:
 * - Initial face registration (3-5 images)
 * - Re-registration (replace existing embeddings)
 * - Face status checking
 * - Face deregistration
 *
 * Images are uploaded as multipart/form-data using React Native's
 * FormData with { uri, type, name } objects for file:// URIs or
 * raw base64 strings.
 *
 * All endpoints are relative to the base URL configured in api.ts.
 * Backend router prefix: /face
 *
 * IMPORTANT: The backend returns response data directly from the
 * Pydantic response_model -- there is NO generic ApiResponse wrapper.
 *
 * @see backend/app/routers/face.py
 * @see backend/app/schemas/face.py
 */

import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';

import { api } from '../utils/api';
import type { FaceRegisterResponse, FaceStatusResponse, ImageQualityResponse } from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Upload timeout: 60 seconds (images can be large) */
const UPLOAD_TIMEOUT_MS = 60_000;

/** Validation timeout: 15 seconds (single image, lightweight) */
const VALIDATE_TIMEOUT_MS = 15_000;

/** Max dimension for face images before upload (backend uses 112x112 for recognition) */
const MAX_IMAGE_DIMENSION = 800;

/** JPEG compression quality for face images (0-1) */
const IMAGE_COMPRESS_QUALITY = 0.7;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Compress a file:// image by resizing and lowering JPEG quality.
 * Reduces ~5 MB phone photos to ~100-200 KB — plenty for face recognition
 * (backend uses 112x112 input) and avoids nginx 413 errors.
 */
const compressImage = async (uri: string): Promise<string> => {
  try {
    const result = await manipulateAsync(
      uri,
      [{ resize: { width: MAX_IMAGE_DIMENSION } }],
      { compress: IMAGE_COMPRESS_QUALITY, format: SaveFormat.JPEG },
    );
    return result.uri;
  } catch {
    // If compression fails, fall back to the original image.
    // nginx allows 50M so uncompressed images will still upload.
    console.warn('[FaceService] Image compression failed, using original');
    return uri;
  }
};

/**
 * Build a FormData payload from an array of image sources.
 *
 * Compresses file:// images first to avoid large uploads, then wraps them
 * in the { uri, type, name } shape that RN's FormData polyfill encodes
 * as multipart parts.
 *
 * The field name `images` matches the FastAPI parameter:
 *   `images: List[UploadFile] = File(...)`
 */
const buildImageFormData = async (images: string[]): Promise<FormData> => {
  const formData = new FormData();

  for (let index = 0; index < images.length; index++) {
    let uri = images[index];

    // Compress file:// images to reduce payload size
    if (uri.startsWith('file://') || uri.startsWith('content://')) {
      uri = await compressImage(uri);
    }

    const file = {
      uri,
      type: 'image/jpeg',
      name: `face_${index}.jpg`,
    } as unknown as Blob;
    formData.append('images', file);
  }

  return formData;
};

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const faceService = {
  /**
   * Register face images for the current student (Step 3 of registration).
   *
   * Uploads 3-5 face images which the backend processes into FaceNet
   * embeddings and stores in the FAISS index.
   *
   * @param images - Array of image URIs (file://) or base64 strings (3-5 images)
   * @returns Registration result with embedding_id and user_id
   * @throws AxiosError on validation, processing, or permission errors
   *
   * Backend: POST /face/register (201 Created, student only)
   * Request: multipart/form-data with field "images" (List[UploadFile])
   * Response: FaceRegisterResponse { success, message, embedding_id, user_id }
   */
  async registerFace(images: string[]): Promise<FaceRegisterResponse> {
    const formData = await buildImageFormData(images);

    const response = await api.post<FaceRegisterResponse>(
      '/face/register',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: UPLOAD_TIMEOUT_MS,
      },
    );

    return response.data;
  },

  /**
   * Re-register face images (replace existing registration).
   *
   * Same as registerFace but overwrites any existing embeddings.
   * Useful when recognition accuracy degrades or appearance changes.
   *
   * @param images - Array of image URIs (file://) or base64 strings (3-5 images)
   * @returns Registration result with new embedding_id
   * @throws AxiosError on validation, processing, or permission errors
   *
   * Backend: POST /face/reregister (200 OK, student only)
   * Request: multipart/form-data with field "images" (List[UploadFile])
   * Response: FaceRegisterResponse { success, message, embedding_id, user_id }
   */
  async reregisterFace(images: string[]): Promise<FaceRegisterResponse> {
    const formData = await buildImageFormData(images);

    const response = await api.post<FaceRegisterResponse>(
      '/face/reregister',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: UPLOAD_TIMEOUT_MS,
      },
    );

    return response.data;
  },

  /**
   * Check whether the current user has a registered face.
   *
   * @returns Face status including registration timestamp
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /face/status
   * Response: FaceStatusResponse { registered, registered_at?, embedding_id? }
   */
  async getFaceStatus(): Promise<FaceStatusResponse> {
    const response = await api.get<FaceStatusResponse>('/face/status');
    return response.data;
  },

  /**
   * Remove face registration for a user.
   *
   * Students can only deregister their own face.
   * Admins can deregister any user.
   *
   * WARNING: This rebuilds the FAISS index on the backend, which may
   * take noticeable time for large indices.
   *
   * @param userId - The UUID of the user whose face should be deregistered
   * @returns Success confirmation
   * @throws AxiosError (403 if student tries to delete another user, 404 if not found)
   *
   * Backend: DELETE /face/{userId}
   * Response: { success: boolean, message: string }
   */
  async deleteFaceRegistration(
    userId: string,
  ): Promise<{ success: boolean; message: string }> {
    const response = await api.delete<{ success: boolean; message: string }>(
      `/face/${userId}`,
    );
    return response.data;
  },

  /**
   * Validate a single face image quality before adding it to the capture set.
   *
   * Runs server-side quality gating (blur, brightness, face size, det confidence)
   * using the mobile-calibrated blur threshold so the user can retake a bad
   * angle immediately instead of failing at final submission.
   *
   * @param imageUri - file:// URI of the captured image
   * @returns Quality validation result with pass/fail and rejection reasons
   * @throws AxiosError on network or server errors
   *
   * Backend: POST /face/validate-image (accepts authenticated or unauthenticated)
   * Request: multipart/form-data with field "image" (single UploadFile)
   * Response: ImageQualityResponse { passed, blur_score, brightness, ... }
   */
  async validateImage(imageUri: string): Promise<ImageQualityResponse> {
    const formData = new FormData();
    const file = {
      uri: imageUri,
      type: 'image/jpeg',
      name: 'check.jpg',
    } as unknown as Blob;
    formData.append('image', file);

    const response = await api.post<ImageQualityResponse>(
      '/face/validate-image',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: VALIDATE_TIMEOUT_MS,
      },
    );
    return response.data;
  },
};
