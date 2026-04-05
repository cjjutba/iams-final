/**
 * Storage Utilities
 *
 * Uses AsyncStorage for large values (tokens, user profile) to avoid
 * SecureStore's 2048-byte limit. SecureStore is kept for small, sensitive items.
 */

import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { User } from '../types';

// Storage keys
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  USER: 'user',
  ONBOARDING_COMPLETE: 'onboarding_complete',
  LAST_USER_ROLE: 'last_user_role',
  PENDING_FACE_IMAGES: 'pending_face_images',
} as const;

/**
 * Storage object with async methods
 */
export const storage = {
  // Access token (AsyncStorage — Supabase JWTs can exceed SecureStore's 2048-byte limit)
  async getAccessToken(): Promise<string | null> {
    try {
      return await AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    } catch (error) {
      console.error('Failed to get access token:', error);
      return null;
    }
  },

  async setAccessToken(token: string): Promise<boolean> {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token);
      return true;
    } catch (error) {
      console.error('Failed to set access token:', error);
      return false;
    }
  },

  // Refresh token (AsyncStorage — same reason as access token)
  async getRefreshToken(): Promise<string | null> {
    try {
      return await AsyncStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
    } catch (error) {
      console.error('Failed to get refresh token:', error);
      return null;
    }
  },

  async setRefreshToken(token: string): Promise<boolean> {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, token);
      return true;
    } catch (error) {
      console.error('Failed to set refresh token:', error);
      return false;
    }
  },

  // User object (AsyncStorage — not sensitive, just display data)
  async getUser(): Promise<User | null> {
    try {
      const userJson = await AsyncStorage.getItem(STORAGE_KEYS.USER);
      return userJson ? JSON.parse(userJson) : null;
    } catch (error) {
      console.error('Failed to get user:', error);
      return null;
    }
  },

  async setUser(user: User): Promise<boolean> {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
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

  // Last user role (for post-logout navigation)
  async getLastUserRole(): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(STORAGE_KEYS.LAST_USER_ROLE);
    } catch (error) {
      console.error('Failed to get last user role:', error);
      return null;
    }
  },

  async setLastUserRole(role: string): Promise<boolean> {
    try {
      await SecureStore.setItemAsync(STORAGE_KEYS.LAST_USER_ROLE, role);
      return true;
    } catch (error) {
      console.error('Failed to set last user role:', error);
      return false;
    }
  },

  // Clear all auth data
  async clearAuth(): Promise<boolean> {
    try {
      await Promise.all([
        AsyncStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN),
        AsyncStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN),
        AsyncStorage.removeItem(STORAGE_KEYS.USER),
      ]);
      return true;
    } catch (error) {
      console.error('Failed to clear auth:', error);
      return false;
    }
  },

  // Pending face images (saved during registration when tokens aren't available yet)
  async getPendingFaceImages(): Promise<string[] | null> {
    try {
      const json = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_FACE_IMAGES);
      return json ? JSON.parse(json) : null;
    } catch (error) {
      console.error('Failed to get pending face images:', error);
      return null;
    }
  },

  async setPendingFaceImages(images: string[]): Promise<boolean> {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.PENDING_FACE_IMAGES, JSON.stringify(images));
      return true;
    } catch (error) {
      console.error('Failed to set pending face images:', error);
      return false;
    }
  },

  async clearPendingFaceImages(): Promise<void> {
    try {
      await AsyncStorage.removeItem(STORAGE_KEYS.PENDING_FACE_IMAGES);
    } catch (error) {
      console.error('Failed to clear pending face images:', error);
    }
  },

  // Clear all storage
  async clearAll(): Promise<boolean> {
    try {
      await Promise.all([
        AsyncStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN),
        AsyncStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN),
        AsyncStorage.removeItem(STORAGE_KEYS.USER),
        SecureStore.deleteItemAsync(STORAGE_KEYS.ONBOARDING_COMPLETE),
      ]);
      return true;
    } catch (error) {
      console.error('Failed to clear all storage:', error);
      return false;
    }
  },
};
