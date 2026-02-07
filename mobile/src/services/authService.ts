/**
 * Auth Service
 *
 * Handles all authentication-related API calls:
 * - Login (email / student ID + password)
 * - Student registration (verify ID then create account)
 * - Token refresh
 * - Logout (backend + local storage)
 * - User profile retrieval and update
 * - Password management
 *
 * All endpoints are relative to the base URL configured in api.ts.
 * Backend router prefix: /auth
 *
 * @see backend/app/routers/auth.py
 * @see backend/app/schemas/auth.py
 */

import { api } from '../utils/api';
import { storage } from '../utils/storage';
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
 * The register endpoint wraps the token response inside a `tokens` field
 * alongside `success`, `message`, and a top-level `user`.
 */
interface RegisterResponse {
  success: boolean;
  message: string;
  user: User;
  tokens: TokenResponse;
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
   * Verify that a student ID exists in the university database.
   * This is Step 1 of the student self-registration flow.
   *
   * The backend returns { valid, student_info, message } but the frontend
   * VerifyStudentIdResponse type expects { success, data: { valid, ... } }.
   * This method transforms the backend response to match the frontend type.
   *
   * @param studentId - The student ID to verify
   * @returns Verification result with student info if valid
   * @throws AxiosError on network or server errors
   *
   * Backend: POST /auth/verify-student-id
   * Backend response: { valid: bool, student_info?: { student_id, first_name, ... }, message: str }
   * Frontend type: { success: bool, data: { valid, first_name?, ... } }
   */
  async verifyStudentId(studentId: string): Promise<VerifyStudentIdResponse> {
    const payload: VerifyStudentIdPayload = { student_id: studentId };

    // Backend VerifyStudentIDResponse shape
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
      };
      message: string;
    }

    const response = await api.post<BackendVerifyResponse>(
      '/auth/verify-student-id',
      payload,
    );
    const backendData = response.data;

    // Transform to frontend expected shape
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
      },
    };
  },

  /**
   * Register a new student account.
   * This is Step 2 of the student self-registration flow.
   * After success the user is authenticated and tokens are stored locally.
   *
   * @param data - Registration payload matching backend RegisterRequest
   * @returns The created user and auth tokens
   * @throws AxiosError on validation or server errors
   *
   * Backend: POST /auth/register  (201 Created)
   * Response shape: RegisterResponse { success, message, user, tokens }
   */
  async register(data: RegisterPayload): Promise<RegisterResponse> {
    const response = await api.post<RegisterResponse>('/auth/register', data);
    const result = response.data;

    // Persist tokens from the nested tokens object
    if (result.tokens.access_token) {
      await storage.setAccessToken(result.tokens.access_token);
    }
    if (result.tokens.refresh_token) {
      await storage.setRefreshToken(result.tokens.refresh_token);
    }

    // Persist user (top-level user field has the same data as tokens.user)
    if (result.user) {
      await storage.setUser(result.user);
    }

    return result;
  },

  /**
   * Authenticate with email or student ID plus password.
   * On success, tokens and user profile are stored locally.
   *
   * @param identifier - Email address or student ID
   * @param password - Account password
   * @returns Token response including user profile
   * @throws AxiosError on invalid credentials or server errors
   *
   * Backend: POST /auth/login
   * Request body: { identifier, password } as JSON
   * Response shape: TokenResponse { access_token, refresh_token, token_type, user }
   */
  async login(identifier: string, password: string): Promise<TokenResponse> {
    const payload: LoginPayload = { identifier, password };
    const response = await api.post<TokenResponse>('/auth/login', payload);
    const authData = response.data;

    // Store tokens
    if (authData.access_token) {
      await storage.setAccessToken(authData.access_token);
    }
    if (authData.refresh_token) {
      await storage.setRefreshToken(authData.refresh_token);
    }

    // Store user
    if (authData.user) {
      await storage.setUser(authData.user);
    }

    return authData;
  },

  /**
   * Log the current user out.
   * Calls the backend logout endpoint (for future token blacklisting)
   * and clears all locally stored auth data regardless of the API result.
   *
   * @throws Never -- local storage is always cleared even if the API call fails.
   *
   * Backend: POST /auth/logout (requires auth)
   */
  async logout(): Promise<void> {
    try {
      await api.post<SuccessResponse>('/auth/logout');
    } catch {
      // Backend logout is best-effort; the important part is clearing
      // local state below.
    } finally {
      await storage.clearAuth();
    }
  },

  /**
   * Retrieve the currently authenticated user's profile from the backend.
   * Useful for verifying that the stored token is still valid.
   *
   * @returns The authenticated user's profile
   * @throws AxiosError if the token is invalid or expired
   *
   * Backend: GET /auth/me
   * Response shape: UserResponse (returned directly, NOT wrapped in ApiResponse)
   */
  async getMe(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },

  /**
   * Refresh the access token using a stored refresh token.
   *
   * Note: In most cases the response interceptor in api.ts handles
   * refresh automatically. This method is exposed for manual control.
   *
   * @param refreshToken - The refresh token string
   * @returns New access token and token type
   * @throws AxiosError if the refresh token is invalid or expired
   *
   * Backend: POST /auth/refresh
   * Response shape: { access_token, token_type }
   */
  async refreshToken(refreshToken: string): Promise<{ access_token: string; token_type: string }> {
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
   * @param oldPassword - The user's current password
   * @param newPassword - The desired new password (min 8 characters)
   * @returns Success confirmation
   * @throws AxiosError if the old password is incorrect or validation fails
   *
   * Backend: POST /auth/change-password
   * Request body: { old_password, new_password }
   */
  async changePassword(oldPassword: string, newPassword: string): Promise<SuccessResponse> {
    const payload: ChangePasswordPayload = {
      old_password: oldPassword,
      new_password: newPassword,
    };
    const response = await api.post<SuccessResponse>('/auth/change-password', payload);
    return response.data;
  },

  /**
   * Request a password reset email.
   *
   * @param email - The email associated with the account
   * @returns Success confirmation
   * @throws AxiosError on server errors
   *
   * Backend: POST /auth/forgot-password
   */
  async forgotPassword(email: string): Promise<SuccessResponse> {
    const payload: ForgotPasswordPayload = { email };
    const response = await api.post<SuccessResponse>('/auth/forgot-password', payload);
    return response.data;
  },

  /**
   * Update the current user's profile.
   *
   * This hits the users router (PATCH /users/{user_id}) because the
   * auth router does not have a profile update endpoint.
   *
   * @param userId - The current user's UUID
   * @param data - Fields to update (all optional)
   * @returns The updated user profile
   * @throws AxiosError on validation or permission errors
   *
   * Backend: PATCH /users/{user_id}
   * Response shape: UserResponse (returned directly)
   */
  async updateProfile(userId: string, data: ProfileUpdatePayload): Promise<User> {
    const response = await api.patch<User>(`/users/${userId}`, data);
    const user = response.data;

    // Keep local storage in sync
    await storage.setUser(user);

    return user;
  },

  // ---------------------------------------------------------------------------
  // Local-only helpers (no network calls)
  // ---------------------------------------------------------------------------

  /**
   * Retrieve the user profile from local secure storage.
   * Does not hit the network.
   *
   * @returns The stored user or null if not available
   */
  async getStoredUser(): Promise<User | null> {
    return storage.getUser();
  },

  /**
   * Check whether the user has a stored access token.
   * Does not validate the token against the backend.
   *
   * @returns true if an access token exists in storage
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await storage.getAccessToken();
    return !!token;
  },
};
