/**
 * Config - Application Configuration
 *
 * Environment-specific settings and configuration constants.
 */

import Constants from 'expo-constants';

const isDev = __DEV__;

// Read from EXPO_PUBLIC_ env vars if set, otherwise fall back to defaults.
// To override: set EXPO_PUBLIC_API_BASE_URL in your .env file.
const API_BASE_URL_ENV = process.env.EXPO_PUBLIC_API_BASE_URL;
const WS_BASE_URL_ENV  = process.env.EXPO_PUBLIC_WS_BASE_URL;

// Supabase settings (read from env — empty strings disable Supabase mode)
const SUPABASE_URL_ENV      = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
const SUPABASE_ANON_KEY_ENV = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

// Derive the dev machine IP from Expo's debuggerHost (e.g. "192.168.1.9:8081")
// so the API URL automatically matches whatever network Metro is using.
const debuggerHost = Constants.expoConfig?.hostUri
  ?? Constants.manifest?.debuggerHost
  ?? '';
const devHostIp = debuggerHost.split(':')[0] || '192.168.1.9';

export const config = {
  // API URLs — prefer env var, then auto-detect from Metro host in dev
  API_BASE_URL: API_BASE_URL_ENV
    ?? (isDev
      ? `http://${devHostIp}:8000/api/v1`
      : 'https://api.iams.com/api/v1'),

  WS_URL: WS_BASE_URL_ENV
    ?? (isDev
      ? `ws://${devHostIp}:8000/api/v1/ws`
      : 'wss://api.iams.com/api/v1/ws'),

  // Supabase
  SUPABASE_URL: SUPABASE_URL_ENV,
  SUPABASE_ANON_KEY: SUPABASE_ANON_KEY_ENV,
  /** True when both SUPABASE_URL and SUPABASE_ANON_KEY are provided */
  USE_SUPABASE_AUTH: !!(SUPABASE_URL_ENV && SUPABASE_ANON_KEY_ENV),

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

  // HLS streaming
  /** Build the HLS playlist URL for a given room. */
  getHlsUrl: (roomId: string) =>
    `${
      API_BASE_URL_ENV
        ?? (isDev
          ? `http://${devHostIp}:8000/api/v1`
          : 'https://api.iams.com/api/v1')
    }/hls/${roomId}/playlist.m3u8`,

  // App info
  APP_VERSION: Constants.manifest?.version || '1.0.0',
  APP_NAME: 'IAMS',
} as const;

export type Config = typeof config;
