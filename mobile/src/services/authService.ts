/**
 * Auth Service
 *
 * Handles all authentication-related API calls:
 * - Login, register, logout
 * - Student ID verification
 * - Token management
 * - User profile retrieval
 */

import { api } from '../utils/api';
import { storage } from '../utils/storage';
import type {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  VerifyStudentIdRequest,
  VerifyStudentIdResponse,
  User,
  ApiResponse,
  ChangePasswordRequest,
} from '../types';

export const authService = {
  /**
   * Verify student ID exists in university database
   */
  async verifyStudentId(data: VerifyStudentIdRequest): Promise<VerifyStudentIdResponse> {
    const response = await api.post<VerifyStudentIdResponse>(
      '/auth/verify-student-id',
      data
    );
    return response.data;
  },

  /**
   * Register new student account
   */
  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/register', data);
    const authData = response.data;

    // Store tokens and user
    if (authData.access_token && authData.refresh_token) {
      await storage.setAccessToken(authData.access_token);
      await storage.setRefreshToken(authData.refresh_token);
    }

    if (authData.user) {
      await storage.setUser(authData.user);
    }

    return authData;
  },

  /**
   * Login with email/student ID and password
   */
  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/login', data);
    const authData = response.data;

    // Store tokens and user
    if (authData.access_token && authData.refresh_token) {
      await storage.setAccessToken(authData.access_token);
      await storage.setRefreshToken(authData.refresh_token);
    }

    if (authData.user) {
      await storage.setUser(authData.user);
    }

    return authData;
  },

  /**
   * Logout - clear local storage
   */
  async logout(): Promise<void> {
    await storage.clearAuth();
  },

  /**
   * Get current user info from API
   */
  async getMe(): Promise<User> {
    const response = await api.get<ApiResponse<User>>('/auth/me');
    return response.data.data!;
  },

  /**
   * Get user from local storage
   */
  async getStoredUser(): Promise<User | null> {
    return await storage.getUser();
  },

  /**
   * Check if user is authenticated (has access token)
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await storage.getAccessToken();
    return !!token;
  },

  /**
   * Change password
   */
  async changePassword(data: ChangePasswordRequest): Promise<ApiResponse> {
    const response = await api.post<ApiResponse>('/auth/change-password', data);
    return response.data;
  },

  /**
   * Request password reset
   */
  async requestPasswordReset(email: string): Promise<ApiResponse> {
    const response = await api.post<ApiResponse>('/auth/forgot-password', { email });
    return response.data;
  },

  /**
   * Update user profile
   */
  async updateProfile(data: Partial<User>): Promise<User> {
    const response = await api.patch<ApiResponse<User>>('/auth/profile', data);
    const user = response.data.data!;

    // Update stored user
    await storage.setUser(user);

    return user;
  },
};
