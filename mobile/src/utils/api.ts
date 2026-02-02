/**
 * API Client - Axios Instance with Interceptors
 *
 * Centralized HTTP client with:
 * - Base URL configuration
 * - Auth token injection
 * - Automatic token refresh
 * - Error handling
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { storage } from './storage';

// Get base URL from environment
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000/api/v1';

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - Add auth token
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    try {
      const accessToken = await storage.getAccessToken();

      if (accessToken && config.headers) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }

      return config;
    } catch (error) {
      return config;
    }
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    // If 401 Unauthorized, attempt token refresh
    if (error.response?.status === 401 && originalRequest && !(originalRequest as any)._retry) {
      (originalRequest as any)._retry = true;

      try {
        const refreshToken = await storage.getRefreshToken();

        if (!refreshToken) {
          // No refresh token, clear auth and reject
          await storage.clearAuth();
          return Promise.reject(error);
        }

        // Attempt to refresh token
        const response = await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          { refresh_token: refreshToken },
          {
            headers: { 'Content-Type': 'application/json' },
          }
        );

        const { access_token } = response.data;

        // Store new access token
        await storage.setAccessToken(access_token);

        // Retry original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, clear auth
        await storage.clearAuth();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
