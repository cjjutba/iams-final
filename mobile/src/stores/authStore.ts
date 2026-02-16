/**
 * Auth Store - Zustand State Management
 *
 * Manages authentication state including user, tokens, and auth actions.
 * Supports dual-mode: Supabase Auth (with email verification) and legacy JWT.
 * Delegates all API calls to authService for correct request/response handling.
 */

import { create } from 'zustand';
import { storage } from '../utils';
import { extractApiError } from '../utils/api';
import { getErrorMessage } from '../utils/helpers';
import { config } from '../constants/config';
import { authService } from '../services';
import { getSupabaseClient } from '../services/supabase';
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
  /** True when the user registered but hasn't verified email yet */
  emailVerificationPending: boolean;
  /** Email address for verification flow (set after registration) */
  pendingVerificationEmail: string | null;

  // Actions
  loadUser: () => Promise<void>;
  /** Refresh user data without affecting isLoading/isAuthenticated (safe for pull-to-refresh) */
  refreshUser: () => Promise<void>;
  initializeAuthListener: () => () => void;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  verifyStudentId: (studentId: string, birthdate: string) => Promise<VerifyStudentIdResponse>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resendVerification: (email: string) => Promise<void>;
  checkVerificationStatus: () => Promise<boolean>;
  clearError: () => void;
  clearVerificationPending: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  emailVerificationPending: false,
  pendingVerificationEmail: null,

  /**
   * Initialize Supabase auth state listener.
   * Returns an unsubscribe function for cleanup.
   * In legacy mode, returns a no-op.
   */
  initializeAuthListener: () => {
    const supabase = getSupabaseClient();

    if (!supabase || !config.USE_SUPABASE_AUTH) {
      return () => {};
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (event === 'SIGNED_IN' && session) {
          // Sync tokens to storage for API interceptor
          await storage.setAccessToken(session.access_token);
          if (session.refresh_token) {
            await storage.setRefreshToken(session.refresh_token);
          }
        } else if (event === 'SIGNED_OUT') {
          await storage.clearAuth();
          set({
            user: null,
            isAuthenticated: false,
            emailVerificationPending: false,
            pendingVerificationEmail: null,
          });
        } else if (event === 'TOKEN_REFRESHED' && session) {
          // Supabase auto-refreshed the token — sync to storage
          await storage.setAccessToken(session.access_token);
          if (session.refresh_token) {
            await storage.setRefreshToken(session.refresh_token);
          }
        }
      },
    );

    return () => subscription.unsubscribe();
  },

  // Load user from storage and verify with backend
  loadUser: async () => {
    set({ isLoading: true, error: null });

    try {
      const hasSession = await authService.isAuthenticated();

      if (!hasSession) {
        set({ isLoading: false, isAuthenticated: false, user: null });
        return;
      }

      // Fetch fresh user profile from backend
      const user = await authService.getMe();
      await storage.setUser(user);

      // Check email verification in Supabase mode
      if (config.USE_SUPABASE_AUTH && !user.email_verified) {
        set({
          user,
          isAuthenticated: false,
          isLoading: false,
          emailVerificationPending: true,
          pendingVerificationEmail: user.email,
        });
        return;
      }

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        emailVerificationPending: false,
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

  // Refresh user data without affecting navigation (safe for pull-to-refresh).
  // Unlike loadUser(), this does NOT set isLoading or change isAuthenticated,
  // so the RootNavigator won't unmount the current screen.
  refreshUser: async () => {
    try {
      const user = await authService.getMe();
      await storage.setUser(user);
      set({ user });
    } catch (error) {
      console.error('Failed to refresh user:', error);
      // Intentionally do NOT clear auth or set isAuthenticated=false.
      // The user stays on their current screen; stale data is better than a redirect.
    }
  },

  // Login with email/student ID + password
  login: async (data: LoginRequest) => {
    // Store current auth state to restore on error
    const currentState = get();
    set({ isLoading: true, error: null });

    try {
      const authData = await authService.login(data.email, data.password);

      // Check email verification in Supabase mode
      if (config.USE_SUPABASE_AUTH && authData.user && !authData.user.email_verified) {
        set({
          user: authData.user,
          isAuthenticated: false,
          isLoading: false,
          emailVerificationPending: true,
          pendingVerificationEmail: authData.user.email,
        });
        return;
      }

      set({
        user: authData.user || null,
        isAuthenticated: true,
        isLoading: false,
        emailVerificationPending: false,
      });
    } catch (error: any) {
      console.error('Login failed:', error);

      // Extract user-friendly error message
      let errorMessage: string;
      if (error.message && typeof error.message === 'string') {
        // Use error message from authService (already user-friendly)
        errorMessage = error.message;
      } else {
        // Extract from Axios error
        const apiError = extractApiError(error);
        errorMessage = apiError.message;
      }

      // Set error but DON'T change isAuthenticated to prevent navigation
      // This keeps the user on the login screen
      set({
        error: errorMessage,
        isLoading: false,
        // Preserve current auth state to prevent unwanted navigation
        isAuthenticated: currentState.isAuthenticated,
      });
      throw error;
    }
  },

  // Register new student account
  register: async (data: RegisterRequest) => {
    set({ isLoading: true, error: null });

    try {
      const result = await authService.register({
        student_id: data.student_id || '',
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone,
      });

      if (config.USE_SUPABASE_AUTH) {
        // Supabase mode: no tokens returned, email verification required
        set({
          user: result.user || null,
          isAuthenticated: false,
          isLoading: false,
          emailVerificationPending: true,
          pendingVerificationEmail: data.email,
        });
      } else {
        // Legacy mode: user is authenticated immediately
        set({
          user: result.user || null,
          isAuthenticated: true,
          isLoading: false,
        });
      }
    } catch (error) {
      console.error('Registration failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Verify student ID (Step 1 of registration - with birthdate verification)
  // Note: This doesn't change auth state, so we don't set isLoading to avoid
  // triggering RootNavigator re-renders that could reset navigation.
  verifyStudentId: async (studentId: string, birthdate: string): Promise<VerifyStudentIdResponse> => {
    set({ error: null });

    try {
      const result = await authService.verifyStudentId(studentId, birthdate);
      return result;
    } catch (error) {
      console.error('Student ID verification failed:', error);
      set({
        error: getErrorMessage(error),
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

  // Resend email verification
  resendVerification: async (email: string) => {
    set({ isLoading: true, error: null });

    try {
      await authService.resendVerification(email);
      set({ isLoading: false });
    } catch (error) {
      console.error('Resend verification failed:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
      throw error;
    }
  },

  // Check if email has been verified (uses public endpoint, no auth needed)
  checkVerificationStatus: async (): Promise<boolean> => {
    try {
      const email = get().pendingVerificationEmail;
      if (!email) return false;

      const verified = await authService.checkEmailVerified(email);
      if (verified) {
        set({
          isAuthenticated: false,
          emailVerificationPending: false,
          pendingVerificationEmail: null,
        });
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  // Logout
  logout: async () => {
    try {
      const currentUser = get().user;
      if (currentUser?.role) {
        await storage.setLastUserRole(currentUser.role);
      }

      await authService.logout();
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        emailVerificationPending: false,
        pendingVerificationEmail: null,
      });
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },

  // Clear verification pending state
  clearVerificationPending: () => {
    set({
      emailVerificationPending: false,
      pendingVerificationEmail: null,
    });
  },
}));
