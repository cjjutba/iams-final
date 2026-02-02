/**
 * Storage Utilities - SecureStore Wrapper
 *
 * Secure storage for sensitive data (tokens, user info).
 * Uses Expo SecureStore for encrypted storage.
 */

import * as SecureStore from 'expo-secure-store';
import { User } from '../types';

// Storage keys
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  USER: 'user',
  ONBOARDING_COMPLETE: 'onboarding_complete',
} as const;

/**
 * Storage object with async methods
 */
export const storage = {
  // Access token
  async getAccessToken(): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(STORAGE_KEYS.ACCESS_TOKEN);
    } catch (error) {
      console.error('Failed to get access token:', error);
      return null;
    }
  },

  async setAccessToken(token: string): Promise<boolean> {
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.ACCESS_TOKEN, token);
      return true;
    } catch (error) {
      console.error('Failed to set access token:', error);
      return false;
    }
  },

  // Refresh token
  async getRefreshToken(): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(STORAGE_KEYS.REFRESH_TOKEN);
    } catch (error) {
      console.error('Failed to get refresh token:', error);
      return null;
    }
  },

  async setRefreshToken(token: string): Promise<boolean> {
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.REFRESH_TOKEN, token);
      return true;
    } catch (error) {
      console.error('Failed to set refresh token:', error);
      return false;
    }
  },

  // User object
  async getUser(): Promise<User | null> {
    try {
      const userJson = await SecureStore.getItemAsync(STORAGE_KEYS.USER);
      return userJson ? JSON.parse(userJson) : null;
    } catch (error) {
      console.error('Failed to get user:', error);
      return null;
    }
  },

  async setUser(user: User): Promise<boolean> {
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.USER, JSON.stringify(user));
      return true;
    } catch (error) {
      console.error('Failed to set user:', error);
      return false;
    }
  },

  // Onboarding status
  async getOnboardingComplete(): Promise<boolean> {
    try {
      const value = await SecureStore.getItemAsync(STORAGE_KEYS.ONBOARDING_COMPLETE);
      return value === 'true';
    } catch (error) {
      console.error('Failed to get onboarding status:', error);
      return false;
    }
  },

  async setOnboardingComplete(complete: boolean): Promise<boolean> {
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.ONBOARDING_COMPLETE, complete.toString());
      return true;
    } catch (error) {
      console.error('Failed to set onboarding status:', error);
      return false;
    }
  },

  // Clear all auth data
  async clearAuth(): Promise<boolean> {
    try {
      await Promise.all([
        SecureStore.deleteItemAsync(STORAGE_KEYS.ACCESS_TOKEN),
        SecureStore.deleteItemAsync(STORAGE_KEYS.REFRESH_TOKEN),
        SecureStore.deleteItemAsync(STORAGE_KEYS.USER),
      ]);
      return true;
    } catch (error) {
      console.error('Failed to clear auth:', error);
      return false;
    }
  },

  // Clear all storage
  async clearAll(): Promise<boolean> {
    try {
      await Promise.all([
        SecureStore.deleteItemAsync(STORAGE_KEYS.ACCESS_TOKEN),
        SecureStore.deleteItemAsync(STORAGE_KEYS.REFRESH_TOKEN),
        SecureStore.deleteItemAsync(STORAGE_KEYS.USER),
        SecureStore.deleteItemAsync(STORAGE_KEYS.ONBOARDING_COMPLETE),
      ]);
      return true;
    } catch (error) {
      console.error('Failed to clear all storage:', error);
      return false;
    }
  },
};
