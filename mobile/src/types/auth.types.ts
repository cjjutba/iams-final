/**
 * Authentication Types
 *
 * Type definitions for authentication, users, and authorization.
 * Mirrors backend API schemas from FastAPI.
 */

// User roles
export enum UserRole {
  STUDENT = 'student',
  FACULTY = 'faculty',
  ADMIN = 'admin',
}

// User interface (from GET /auth/me)
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  student_id?: string; // Only for students
  phone?: string;
  is_active: boolean;
  email_verified: boolean; // True after email confirmation (Supabase Auth)
  created_at: string;
  updated_at?: string;
}

// Login request (POST /auth/login)
export interface LoginRequest {
  email: string; // Can be email or student ID
  password: string;
}

// Register request (POST /auth/register)
export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  student_id?: string; // Required for students
  phone?: string;
}

// Verify student ID request (POST /auth/verify-student-id)
export interface VerifyStudentIdRequest {
  student_id: string;
}

// Verify student ID response
export interface VerifyStudentIdResponse {
  success: boolean;
  data: {
    valid: boolean;
    first_name?: string;
    last_name?: string;
    course?: string;
    year?: string;
    section?: string;
    email?: string;
  };
}

// Auth response (POST /auth/login or /auth/register)
export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in?: number;
  user?: User;
}

// Token refresh request (POST /auth/refresh)
export interface RefreshTokenRequest {
  refresh_token: string;
}

// Token refresh response
export interface RefreshTokenResponse {
  access_token: string;
  token_type: string;
}

// Password change request (POST /auth/change-password)
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

// Generic API response wrapper
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

// Paginated response
export interface PaginatedResponse<T = any> {
  success: boolean;
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}
