/**
 * Config - Application Configuration
 *
 * Environment-specific settings and configuration constants.
 */

import Constants from 'expo-constants';

const isDev = __DEV__;

export const config = {
  // API URLs
  API_BASE_URL: isDev
    ? 'http://192.168.1.11:8000/api/v1'
    : 'https://api.iams.com/api/v1',

  WS_URL: isDev
    ? 'ws://192.168.1.11:8000/api/v1/ws'
    : 'wss://api.iams.com/api/v1/ws',

  // Storage keys
  STORAGE_KEYS: {
    ACCESS_TOKEN: '@iams/access_token',
    REFRESH_TOKEN: '@iams/refresh_token',
    USER: '@iams/user',
    ONBOARDING_COMPLETE: '@iams/onboarding_complete',
  },

  // API settings
  API_TIMEOUT: 30000, // 30 seconds

  // Pagination
  DEFAULT_PAGE_SIZE: 20,

  // Face registration
  REQUIRED_FACE_IMAGES: 5,
  FACE_IMAGE_QUALITY: 0.8,

  // Session settings
  TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000, // 5 minutes before expiry
  MAX_RETRY_ATTEMPTS: 3,

  // WebSocket settings
  WS_RECONNECT_INTERVAL: 5000, // 5 seconds
  WS_MAX_RECONNECT_ATTEMPTS: 5,

  // App info
  APP_VERSION: Constants.manifest?.version || '1.0.0',
  APP_NAME: 'IAMS',
} as const;

export type Config = typeof config;
