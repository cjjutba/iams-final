/**
 * Face Service
 *
 * Handles face registration and management:
 * - Face registration (initial and re-registration)
 * - Face status checking
 * - Image upload with FormData
 */

import { api } from '../utils/api';
import type { FaceRegisterResponse, FaceStatusResponse, ApiResponse } from '../types';

export const faceService = {
  /**
   * Register face images (initial registration)
   * @param images - Array of base64 image strings or image URIs
   */
  async registerFace(images: string[]): Promise<FaceRegisterResponse> {
    const formData = new FormData();

    // Add each image to FormData
    images.forEach((image, index) => {
      // If image is a URI (file://), create blob
      if (image.startsWith('file://')) {
        const file = {
          uri: image,
          type: 'image/jpeg',
          name: `face_${index}.jpg`,
        } as any;
        formData.append('images', file);
      } else {
        // If base64, convert to blob
        formData.append('images', image);
      }
    });

    const response = await api.post<ApiResponse<FaceRegisterResponse>>(
      '/face/register',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data.data!;
  },

  /**
   * Re-register face images (replace existing)
   * @param images - Array of base64 image strings or image URIs
   */
  async reregisterFace(images: string[]): Promise<FaceRegisterResponse> {
    const formData = new FormData();

    // Add each image to FormData
    images.forEach((image, index) => {
      if (image.startsWith('file://')) {
        const file = {
          uri: image,
          type: 'image/jpeg',
          name: `face_${index}.jpg`,
        } as any;
        formData.append('images', file);
      } else {
        formData.append('images', image);
      }
    });

    const response = await api.post<ApiResponse<FaceRegisterResponse>>(
      '/face/reregister',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data.data!;
  },

  /**
   * Check current face registration status
   */
  async checkFaceStatus(): Promise<FaceStatusResponse> {
    const response = await api.get<ApiResponse<FaceStatusResponse>>('/face/status');
    return response.data.data!;
  },

  /**
   * Delete face registration
   */
  async deleteFaceRegistration(): Promise<void> {
    await api.delete('/face/registration');
  },
};
