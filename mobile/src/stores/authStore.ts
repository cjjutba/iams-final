/**
 * Auth Store - Zustand State Management
 *
 * Manages authentication state including user, tokens, and auth actions.
 * Integrates with storage for persistence and API for authentication.
 */

import { create } from 'zustand';
import { api, storage, getErrorMessage } from '../utils';
import type {
  User,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  VerifyStudentIdRequest,
  VerifyStudentIdResponse,
} from '../types';

interface AuthState {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  loadUser: () => Promise<void>;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  verifyStudentId: (data: VerifyStudentIdRequest) => Promise<VerifyStudentIdResponse>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  // Load user from storage and verify with backend
  loadUser: async () => {
    set({ isLoading: true, error: null });

    try {
      const accessToken = await storage.getAccessToken();

      if (!accessToken) {
        set({ isLoading: false, isAuthenticated: false, user: null });
        return;
      }

      // Get user from backend to verify token
      const response = await api.get<AuthResponse>('/auth/me');

      if (response.data && response.data.user) {
        await storage.setUser(response.data.user);
        set({
          user: response.data.user,
          isAuthenticated: true,
          isLoading: false,
        });
      } else {
        // Invalid response, clear auth
        await storage.clearAuth();
        set({ isLoading: false, isAuthenticated: false, user: null });
      }
    } catch (error) {
      console.error('Failed to load user:', error);
      await storage.clearAuth();
      set({
        error: getErrorMessage(error),
        isLoading: false,
        isAuthenticated: false,
        user: null,
      });
    }
  },

  // Login with email/student ID + password
  login: async (data: LoginRequest) => {
    set({ isLoading: true, error: null });

    try {
      // Convert to URLSearchParams for form data
      const formData = new URLSearchParams();
      formData.append('email', data.email);
      formData.append('password', data.password);

      const response = await api.post<AuthResponse>('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, refresh_token, user } = response.data;

      // Store tokens and user
      await storage.setAccessToken(access_token);
      await storage.setRefreshToken(refresh_token);
      if (user) {
        await storage.setUser(user);
      }

      set({
        user: user || null,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      console.error('Login failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
        isAuthenticated: false,
      });
      throw error;
    }
  },

  // Register new student account
  register: async (data: RegisterRequest) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.post<AuthResponse>('/auth/register', data);

      const { access_token, refresh_token, user } = response.data;

      // Store tokens and user
      await storage.setAccessToken(access_token);
      await storage.setRefreshToken(refresh_token);
      if (user) {
        await storage.setUser(user);
      }

      set({
        user: user || null,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      console.error('Registration failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Verify student ID (Step 1 of registration)
  verifyStudentId: async (data: VerifyStudentIdRequest): Promise<VerifyStudentIdResponse> => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.post<VerifyStudentIdResponse>('/auth/verify-student-id', data);

      set({ isLoading: false });
      return response.data;
    } catch (error) {
      console.error('Student ID verification failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Logout
  logout: async () => {
    set({ isLoading: true, error: null });

    try {
      // Clear local storage
      await storage.clearAuth();

      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    } catch (error) {
      console.error('Logout failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));
