/**
 * Auth Store - Zustand State Management
 *
 * Manages authentication state including user, tokens, and auth actions.
 * Delegates all API calls to authService for correct request/response handling.
 */

import { create } from 'zustand';
import { storage, getErrorMessage } from '../utils';
import { authService } from '../services';
import type {
  User,
  LoginRequest,
  RegisterRequest,
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
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
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

      // GET /auth/me returns UserResponse directly (not wrapped)
      const user = await authService.getMe();

      await storage.setUser(user);
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      console.error('Failed to load user:', error);
      await storage.clearAuth();
      set({
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
      // authService.login sends JSON { identifier, password } and stores tokens
      const authData = await authService.login(data.email, data.password);

      set({
        user: authData.user || null,
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
      // authService.register handles nested tokens response and stores tokens
      const result = await authService.register({
        student_id: data.student_id || '',
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone,
      });

      set({
        user: result.user || null,
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
      const result = await authService.verifyStudentId(data.student_id);
      set({ isLoading: false });
      return result;
    } catch (error) {
      console.error('Student ID verification failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Change password
  changePassword: async (oldPassword: string, newPassword: string) => {
    set({ isLoading: true, error: null });

    try {
      await authService.changePassword(oldPassword, newPassword);
      set({ isLoading: false });
    } catch (error) {
      console.error('Change password failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Update user profile
  updateProfile: async (data: Partial<User>) => {
    set({ isLoading: true, error: null });

    try {
      const currentUser = get().user;
      if (!currentUser) throw new Error('No user logged in');

      const updatedUser = await authService.updateProfile(currentUser.id, data);
      await storage.setUser(updatedUser);
      set({
        user: updatedUser,
        isLoading: false,
      });
    } catch (error) {
      console.error('Update profile failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Request password reset via email
  forgotPassword: async (email: string) => {
    set({ isLoading: true, error: null });

    try {
      await authService.forgotPassword(email);
      set({ isLoading: false });
    } catch (error) {
      console.error('Forgot password request failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Logout
  logout: async () => {
    try {
      // Save user role before clearing for post-logout navigation
      const currentUser = get().user;
      if (currentUser?.role) {
        await storage.setLastUserRole(currentUser.role);
      }

      await authService.logout();
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      // Always reset state regardless of API result
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));
