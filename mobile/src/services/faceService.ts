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

import { api } from '../utils/api';
import type { FaceRegisterResponse, FaceStatusResponse } from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Upload timeout: 60 seconds (images can be large) */
const UPLOAD_TIMEOUT_MS = 60_000;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Build a FormData payload from an array of image sources.
 *
 * Handles two image formats:
 * 1. `file://` URIs -- converted to React Native file upload objects
 *    with { uri, type, name } shape (RN's FormData polyfill handles
 *    the actual multipart encoding).
 * 2. Raw base64 strings -- appended directly; the backend's UploadFile
 *    handler decodes them server-side.
 *
 * The field name `images` matches the FastAPI parameter:
 *   `images: List[UploadFile] = File(...)`
 *
 * @param images - Array of image URIs or base64 strings
 * @returns Populated FormData instance
 */
const buildImageFormData = (images: string[]): FormData => {
  const formData = new FormData();

  images.forEach((image, index) => {
    if (image.startsWith('file://') || image.startsWith('content://')) {
      // React Native file upload object
      const file = {
        uri: image,
        type: 'image/jpeg',
        name: `face_${index}.jpg`,
      } as unknown as Blob;
      formData.append('images', file);
    } else if (image.startsWith('data:image/')) {
      // Data URI -- strip prefix and send as file-like object
      // Some camera libraries return data URIs; we re-wrap them.
      const base64Data = image.split(',')[1] || image;
      const file = {
        uri: `data:image/jpeg;base64,${base64Data}`,
        type: 'image/jpeg',
        name: `face_${index}.jpg`,
      } as unknown as Blob;
      formData.append('images', file);
    } else {
      // Assume raw base64 string
      const file = {
        uri: `data:image/jpeg;base64,${image}`,
        type: 'image/jpeg',
        name: `face_${index}.jpg`,
      } as unknown as Blob;
      formData.append('images', file);
    }
  });

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
    const formData = buildImageFormData(images);

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
    const formData = buildImageFormData(images);

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
};
