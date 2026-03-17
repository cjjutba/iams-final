/**
 * API Client - Axios Instance with Interceptors
 *
 * Centralized HTTP client with:
 * - Base URL configuration from app config
 * - Auth token injection via request interceptor
 * - Automatic token refresh on 401 with request queuing
 * - Supabase session-aware token handling when USE_SUPABASE_AUTH is enabled
 * - Consistent error normalization to ApiError shape
 * - Configurable timeout (default 30s)
 */

import axios, {
  AxiosError,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { storage } from './storage';
import { config } from '../constants/config';
import { getSupabaseClient } from '../services/supabase';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Normalized error shape returned by extractApiError.
 * Every service layer catch block should convert errors through this type.
 */
export interface ApiError {
  /** HTTP status code, or 0 for network / timeout errors */
  status: number;
  /** Human-readable error message safe for UI display */
  message: string;
  /** Raw detail payload from the backend (FastAPI format) */
  detail?: string | Record<string, unknown>;
  /** True when the error was caused by a network failure (offline, DNS, etc.) */
  isNetworkError: boolean;
  /** True when the request timed out */
  isTimeout: boolean;
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

/**
 * Pre-configured Axios instance used by every service module.
 *
 * Base URL is sourced from the centralised app config which itself
 * switches between dev and production URLs based on __DEV__.
 */
export const api = axios.create({
  baseURL: config.API_BASE_URL,
  timeout: config.API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---------------------------------------------------------------------------
// Token refresh state (shared across concurrent requests)
// ---------------------------------------------------------------------------

/** Whether a token refresh is currently in-flight */
let isRefreshing = false;

/**
 * Queue of callers waiting for the current refresh to complete.
 * Each entry is a pair of resolve / reject callbacks so the original
 * request can be retried (or rejected) once we know the outcome.
 */
let failedQueue: {
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}[] = [];

/**
 * Flush the queue after a refresh attempt finishes.
 * On success the new token is handed to every queued caller;
 * on failure every caller receives the error.
 */
const processQueue = (error: unknown, token: string | null = null): void => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    } else {
      prom.reject(new Error('Token refresh failed'));
    }
  });
  failedQueue = [];
};

/**
 * Get the current access token.
 * In Supabase mode, prefer the token from the Supabase session.
 * Falls back to storage for both modes.
 */
const getAccessToken = async (): Promise<string | null> => {
  if (config.USE_SUPABASE_AUTH) {
    const supabase = getSupabaseClient();
    if (supabase) {
      try {
        const { data } = await supabase.auth.getSession();
        if (data.session?.access_token) {
          return data.session.access_token;
        }
      } catch {
        // Fall through to storage
      }
    }
  }

  return storage.getAccessToken();
};

/**
 * Refresh the access token.
 * In Supabase mode uses supabase.auth.refreshSession().
 * In legacy mode calls the backend refresh endpoint directly.
 */
const refreshAccessToken = async (): Promise<string> => {
  if (config.USE_SUPABASE_AUTH) {
    const supabase = getSupabaseClient();
    if (supabase) {
      const { data, error } = await supabase.auth.refreshSession();

      if (error || !data.session) {
        throw error || new Error('No session returned from refresh');
      }

      const token = data.session.access_token;
      await storage.setAccessToken(token);
      if (data.session.refresh_token) {
        await storage.setRefreshToken(data.session.refresh_token);
      }

      return token;
    }
  }

  // Legacy mode: call backend refresh endpoint
  const refreshToken = await storage.getRefreshToken();

  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const response = await axios.post(
    `${config.API_BASE_URL}/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { 'Content-Type': 'application/json' } },
  );

  const { access_token } = response.data;
  await storage.setAccessToken(access_token);

  if (response.data.refresh_token) {
    await storage.setRefreshToken(response.data.refresh_token);
  }

  return access_token;
};

// ---------------------------------------------------------------------------
// Request interceptor - attach auth token
// ---------------------------------------------------------------------------

api.interceptors.request.use(
  async (requestConfig: InternalAxiosRequestConfig) => {
    try {
      const accessToken = await getAccessToken();
      if (accessToken && requestConfig.headers) {
        requestConfig.headers.Authorization = `Bearer ${accessToken}`;
      }
    } catch {
      // Silently continue -- missing token simply means the request
      // will be unauthenticated and the server will respond with 401.
    }
    return requestConfig;
  },
  (error) => Promise.reject(error),
);

// ---------------------------------------------------------------------------
// Response interceptor - 401 handling with token refresh + request queueing
// ---------------------------------------------------------------------------

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    // Only attempt a refresh for 401s on requests that have not been
    // retried yet and that actually have a config to retry.
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry
    ) {
      // If a refresh is already in-flight, queue this request.
      if (isRefreshing) {
        return new Promise<AxiosResponse>((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              resolve(api(originalRequest));
            },
            reject: (err: unknown) => {
              reject(err);
            },
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const newToken = await refreshAccessToken();

        // Flush queued requests with the new token.
        processQueue(null, newToken);

        // Retry the original request.
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed -- clear auth and reject everything.
        await storage.clearAuth();
        processQueue(refreshError, null);
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

// ---------------------------------------------------------------------------
// Error extraction utility
// ---------------------------------------------------------------------------

/**
 * Convert any thrown value into a consistent {@link ApiError} shape.
 *
 * Handles:
 * - Axios HTTP errors (4xx / 5xx) including FastAPI's `{ detail }` format
 * - Network errors (no response received)
 * - Timeout errors
 * - Non-Axios errors (unexpected throws)
 *
 * @param error - The value caught in a try/catch block
 * @returns A normalised ApiError object
 */
export const extractApiError = (error: unknown): ApiError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string | Record<string, unknown> }>;

    // Timeout
    if (axiosError.code === 'ECONNABORTED' || axiosError.code === 'ETIMEDOUT') {
      return {
        status: 0,
        message: 'Request timed out. Please try again.',
        isNetworkError: false,
        isTimeout: true,
      };
    }

    // Network error (offline, DNS failure, etc.)
    if (!axiosError.response) {
      return {
        status: 0,
        message: 'Network error. Please check your internet connection.',
        isNetworkError: true,
        isTimeout: false,
      };
    }

    // HTTP error with response
    const status = axiosError.response.status;
    const detail = axiosError.response.data?.detail;

    let message: string;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail === 'object') {
      // FastAPI validation errors come as objects; stringify for display.
      message = JSON.stringify(detail);
    } else {
      // Fall back to status-based messages.
      switch (status) {
        case 400:
          message = 'Bad request. Please check your input.';
          break;
        case 401:
          message = 'Session expired. Please log in again.';
          break;
        case 403:
          message = 'You do not have permission to perform this action.';
          break;
        case 404:
          message = 'The requested resource was not found.';
          break;
        case 422:
          message = 'Validation error. Please check your input.';
          break;
        case 429:
          message = 'Too many requests. Please slow down.';
          break;
        default:
          message =
            status >= 500
              ? 'Server error. Please try again later.'
              : 'Something went wrong. Please try again.';
      }
    }

    return {
      status,
      message,
      detail: detail ?? undefined,
      isNetworkError: false,
      isTimeout: false,
    };
  }

  // Non-Axios error
  const fallbackMessage =
    error instanceof Error ? error.message : 'An unexpected error occurred.';

  return {
    status: 0,
    message: fallbackMessage,
    isNetworkError: false,
    isTimeout: false,
  };
};

export default api;
