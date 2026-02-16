/**
 * useAuth Hook
 *
 * Provides access to authentication state and actions.
 * Wraps authStore for convenient component usage.
 * Includes email verification state for Supabase Auth mode.
 */

import { useAuthStore } from '../stores';

export const useAuth = () => {
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    emailVerificationPending,
    pendingVerificationEmail,
    loadUser,
    refreshUser,
    initializeAuthListener,
    login,
    register,
    logout,
    verifyStudentId,
    changePassword,
    updateProfile,
    forgotPassword,
    resendVerification,
    checkVerificationStatus,
    clearError,
    clearVerificationPending,
  } = useAuthStore();

  return {
    // State
    user,
    isAuthenticated,
    isLoading,
    error,
    emailVerificationPending,
    pendingVerificationEmail,

    // Actions
    loadUser,
    refreshUser,
    initializeAuthListener,
    login,
    register,
    logout,
    verifyStudentId,
    changePassword,
    updateProfile,
    forgotPassword,
    resendVerification,
    checkVerificationStatus,
    clearError,
    clearVerificationPending,

    // Computed
    isStudent: user?.role === 'student',
    isFaculty: user?.role === 'faculty' || user?.role === 'admin',
    fullName: user ? `${user.first_name} ${user.last_name}` : null,
    isEmailVerified: user?.email_verified ?? false,
  };
};
