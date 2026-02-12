/**
 * Auth Service
 *
 * Handles all authentication-related API calls with dual-mode support:
 * - Supabase Auth (when USE_SUPABASE_AUTH is enabled)
 * - Custom JWT (legacy fallback)
 *
 * Login and password flows use Supabase SDK directly when enabled.
 * Registration always goes through the backend (student ID verification).
 *
 * @see backend/app/routers/auth.py
 * @see backend/app/schemas/auth.py
 */

import { api } from '../utils/api';
import { storage } from '../utils/storage';
import { config } from '../constants/config';
import { getSupabaseClient } from './supabase';
import type {
  User,
  VerifyStudentIdResponse,
} from '../types';

// ---------------------------------------------------------------------------
// Request / Response types that match backend Pydantic schemas exactly
// ---------------------------------------------------------------------------

/** POST /auth/login -- mirrors backend LoginRequest */
interface LoginPayload {
  identifier: string;
  password: string;
}

/**
 * POST /auth/register -- mirrors backend RegisterRequest
 * Note: `role` is not sent because only students can self-register.
 */
interface RegisterPayload {
  student_id: string;
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
}

/** POST /auth/verify-student-id -- mirrors backend VerifyStudentIDRequest */
interface VerifyStudentIdPayload {
  student_id: string;
  birthdate: string; // ISO 8601 date format (YYYY-MM-DD)
}

/** Backend TokenResponse shape (returned by POST /auth/login) */
interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user: User;
}

/**
 * Backend RegisterResponse shape (returned by POST /auth/register)
 *
 * In Supabase mode `tokens` is null — the user must verify their email
 * before they can sign in via Supabase SDK.
 * In legacy mode `tokens` contains access/refresh tokens.
 */
interface RegisterResponse {
  success: boolean;
  message: string;
  user: User;
  tokens: TokenResponse | null;
}

/** POST /auth/change-password -- mirrors backend PasswordChange */
interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
}

/** Simple success response from change-password, logout, etc. */
interface SuccessResponse {
  success: boolean;
  message: string;
}

/** POST /auth/forgot-password -- mirrors backend ForgotPasswordRequest */
interface ForgotPasswordPayload {
  email: string;
}

/**
 * PATCH /users/{user_id} -- mirrors backend UserUpdate
 * Profile update goes through the users router, not auth.
 */
interface ProfileUpdatePayload {
  email?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const authService = {
  /**
   * Verify that a student ID exists in the university database and that
   * the provided birthdate matches the official record.
   * This is Step 1 of the student self-registration flow with 2FA verification.
   * Always uses the backend API (student records are server-side only).
   */
  async verifyStudentId(studentId: string, birthdate: string): Promise<VerifyStudentIdResponse> {
    const payload: VerifyStudentIdPayload = { student_id: studentId, birthdate };

    interface BackendVerifyResponse {
      valid: boolean;
      student_info?: {
        student_id: string;
        first_name?: string;
        last_name?: string;
        course?: string;
        year?: number;
        section?: string;
        email?: string;
        contact_number?: string;
      };
      message: string;
    }

    const response = await api.post<BackendVerifyResponse>(
      '/auth/verify-student-id',
      payload,
    );
    const backendData = response.data;

    return {
      success: backendData.valid,
      data: {
        valid: backendData.valid,
        first_name: backendData.student_info?.first_name,
        last_name: backendData.student_info?.last_name,
        course: backendData.student_info?.course,
        year: backendData.student_info?.year?.toString(),
        section: backendData.student_info?.section,
        email: backendData.student_info?.email,
        phone: backendData.student_info?.contact_number,
      },
      message: backendData.message, // Pass through backend message
    };
  },

  /**
   * Register a new student account.
   * This always goes through the backend because student ID verification
   * must happen server-side before account creation.
   *
   * In Supabase mode: backend creates Supabase Auth user + local record.
   * A verification email is sent automatically. No tokens are returned —
   * the user must verify email first, then sign in.
   *
   * In legacy mode: tokens are returned and the user is signed in immediately.
   */
  async register(data: RegisterPayload): Promise<RegisterResponse> {
    const response = await api.post<RegisterResponse>('/auth/register', data);
    const result = response.data;

    // Legacy mode: persist tokens immediately
    if (result.tokens) {
      if (result.tokens.access_token) {
        await storage.setAccessToken(result.tokens.access_token);
      }
      if (result.tokens.refresh_token) {
        await storage.setRefreshToken(result.tokens.refresh_token);
      }
    }

    if (result.user) {
      await storage.setUser(result.user);
    }

    return result;
  },

  /**
   * Authenticate with email or student ID plus password.
   *
   * Supabase mode: uses supabase.auth.signInWithPassword(), then fetches
   * the full user profile from the backend via GET /auth/me.
   *
   * Legacy mode: sends credentials to POST /auth/login and stores tokens.
   */
  async login(identifier: string, password: string): Promise<TokenResponse> {
    const supabase = getSupabaseClient();

    if (supabase && config.USE_SUPABASE_AUTH) {
      // Supabase requires an email. If identifier looks like a student ID
      // (contains a dash), resolve it to an email via the backend resolve endpoint.
      let email = identifier;
      if (identifier.includes('-') && !identifier.includes('@')) {
        try {
          const resolveResp = await api.post<{ email: string }>(
            '/auth/resolve-email',
            { identifier, password },
          );
          email = resolveResp.data.email;
        } catch (error: any) {
          // Convert resolve-email errors to user-friendly messages
          if (error.response?.status === 404) {
            throw new Error('Student ID not found. Please check your ID or register for an account.');
          }
          if (error.response?.status === 401) {
            throw new Error('Invalid Student ID or password. Please check your credentials and try again.');
          }
          if (error.response?.data?.detail) {
            throw new Error(error.response.data.detail);
          }
          // Re-throw other errors
          throw error;
        }
      }

      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        throw new Error(error.message);
      }

      if (!data.session) {
        throw new Error('No session returned from authentication');
      }

      // Store the Supabase session tokens for the API interceptor
      await storage.setAccessToken(data.session.access_token);
      if (data.session.refresh_token) {
        await storage.setRefreshToken(data.session.refresh_token);
      }

      // Fetch the full user profile from our backend
      const user = await this.getMe();
      await storage.setUser(user);

      return {
        access_token: data.session.access_token,
        refresh_token: data.session.refresh_token,
        token_type: 'bearer',
        user,
      };
    }

    // Legacy mode
    const payload: LoginPayload = { identifier, password };
    const response = await api.post<TokenResponse>('/auth/login', payload);
    const authData = response.data;

    if (authData.access_token) {
      await storage.setAccessToken(authData.access_token);
    }
    if (authData.refresh_token) {
      await storage.setRefreshToken(authData.refresh_token);
    }
    if (authData.user) {
      await storage.setUser(authData.user);
    }

    return authData;
  },

  /**
   * Log the current user out.
   * Supabase mode: calls supabase.auth.signOut() + backend logout.
   * Legacy mode: calls backend logout only.
   * Local storage is always cleared regardless of API results.
   */
  async logout(): Promise<void> {
    try {
      const supabase = getSupabaseClient();
      if (supabase && config.USE_SUPABASE_AUTH) {
        await supabase.auth.signOut();
      }
      await api.post<SuccessResponse>('/auth/logout');
    } catch {
      // Backend/Supabase logout is best-effort
    } finally {
      await storage.clearAuth();
    }
  },

  /**
   * Retrieve the currently authenticated user's profile from the backend.
   * Checks email verification status as well.
   */
  async getMe(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },

  /**
   * Refresh the access token.
   *
   * Supabase mode: uses supabase.auth.refreshSession().
   * Legacy mode: calls POST /auth/refresh.
   *
   * Note: Supabase auto-refreshes tokens via onAuthStateChange, so this
   * is mainly for manual control or legacy mode.
   */
  async refreshToken(refreshToken: string): Promise<{ access_token: string; token_type: string }> {
    const supabase = getSupabaseClient();

    if (supabase && config.USE_SUPABASE_AUTH) {
      const { data, error } = await supabase.auth.refreshSession();

      if (error) {
        throw new Error(error.message);
      }

      if (!data.session) {
        throw new Error('No session returned from refresh');
      }

      await storage.setAccessToken(data.session.access_token);
      if (data.session.refresh_token) {
        await storage.setRefreshToken(data.session.refresh_token);
      }

      return {
        access_token: data.session.access_token,
        token_type: 'bearer',
      };
    }

    // Legacy mode
    const response = await api.post<{ access_token: string; token_type: string }>(
      '/auth/refresh',
      { refresh_token: refreshToken },
    );

    const { access_token } = response.data;
    await storage.setAccessToken(access_token);

    return response.data;
  },

  /**
   * Change the current user's password.
   *
   * Supabase mode: calls supabase.auth.updateUser() + backend change-password
   * to keep both systems in sync.
   *
   * Legacy mode: calls backend change-password only.
   */
  async changePassword(oldPassword: string, newPassword: string): Promise<SuccessResponse> {
    const supabase = getSupabaseClient();

    // Always call backend (it handles Supabase sync internally)
    const payload: ChangePasswordPayload = {
      old_password: oldPassword,
      new_password: newPassword,
    };
    const response = await api.post<SuccessResponse>('/auth/change-password', payload);

    // If Supabase is enabled, also update via SDK for immediate session sync
    if (supabase && config.USE_SUPABASE_AUTH) {
      try {
        await supabase.auth.updateUser({ password: newPassword });
      } catch {
        // Backend already handled it; SDK call is best-effort
      }
    }

    return response.data;
  },

  /**
   * Request a password reset email.
   *
   * Supabase mode: uses supabase.auth.resetPasswordForEmail() which sends
   * a magic link to the user's email. The deep link redirects to the app's
   * ResetPasswordScreen where they can set a new password.
   *
   * Legacy mode: calls backend POST /auth/forgot-password.
   */
  async forgotPassword(email: string): Promise<SuccessResponse> {
    const supabase = getSupabaseClient();

    if (supabase && config.USE_SUPABASE_AUTH) {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: 'iams://reset-password',
      });

      if (error) {
        throw new Error(error.message);
      }

      return {
        success: true,
        message: 'Password reset instructions sent to your email',
      };
    }

    // Legacy mode
    const payload: ForgotPasswordPayload = { email };
    const response = await api.post<SuccessResponse>('/auth/forgot-password', payload);
    return response.data;
  },

  /**
   * Complete password reset (Supabase mode only).
   * Called from ResetPasswordScreen after the user clicks the deep link.
   * The Supabase SDK automatically picks up the session from the deep link.
   */
  async resetPassword(newPassword: string): Promise<SuccessResponse> {
    const supabase = getSupabaseClient();

    if (!supabase) {
      throw new Error('Password reset requires Supabase Auth');
    }

    const { error } = await supabase.auth.updateUser({
      password: newPassword,
    });

    if (error) {
      throw new Error(error.message);
    }

    return {
      success: true,
      message: 'Password updated successfully',
    };
  },

  /**
   * Resend email verification.
   * Calls backend POST /auth/resend-verification which uses Supabase admin.
   */
  async resendVerification(email: string): Promise<SuccessResponse> {
    const response = await api.post<SuccessResponse>(
      '/auth/resend-verification',
      { email },
    );
    return response.data;
  },

  /**
   * Check the current user's email verification status.
   * Returns the user profile; caller should check user.email_verified.
   */
  async checkVerificationStatus(): Promise<User> {
    return this.getMe();
  },

  /**
   * Update the current user's profile.
   * Uses the users router (PATCH /users/{user_id}).
   */
  async updateProfile(userId: string, data: ProfileUpdatePayload): Promise<User> {
    const response = await api.patch<User>(`/users/${userId}`, data);
    const user = response.data;
    await storage.setUser(user);
    return user;
  },

  // ---------------------------------------------------------------------------
  // Local-only helpers (no network calls)
  // ---------------------------------------------------------------------------

  async getStoredUser(): Promise<User | null> {
    return storage.getUser();
  },

  async isAuthenticated(): Promise<boolean> {
    const supabase = getSupabaseClient();

    if (supabase && config.USE_SUPABASE_AUTH) {
      const { data } = await supabase.auth.getSession();
      return !!data.session;
    }

    const token = await storage.getAccessToken();
    return !!token;
  },
};
