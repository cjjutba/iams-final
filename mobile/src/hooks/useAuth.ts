/**
 * useAuth Hook
 *
 * Provides access to authentication state and actions.
 * Wraps authStore for convenient component usage.
 */

import { useAuthStore } from '../stores';

export const useAuth = () => {
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    loadUser,
    login,
    register,
    logout,
    verifyStudentId,
    changePassword,
    updateProfile,
    forgotPassword,
    clearError,
  } = useAuthStore();

  return {
    // State
    user,
    isAuthenticated,
    isLoading,
    error,

    // Actions
    loadUser,
    login,
    register,
    logout,
    verifyStudentId,
    changePassword,
    updateProfile,
    forgotPassword,
    clearError,

    // Computed
    isStudent: user?.role === 'student',
    isFaculty: user?.role === 'faculty' || user?.role === 'admin',
    fullName: user ? `${user.first_name} ${user.last_name}` : null,
  };
};
