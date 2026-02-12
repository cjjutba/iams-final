/**
 * useToast Hook
 *
 * Hook to access toast notification functionality.
 *
 * @example
 * ```tsx
 * const { showSuccess, showError } = useToast();
 *
 * // Show success toast
 * showSuccess('Profile updated successfully');
 *
 * // Show error toast with title
 * showError('Invalid credentials', 'Login Failed');
 *
 * // Show custom toast
 * showToast({
 *   type: 'warning',
 *   message: 'Low battery detected',
 *   duration: 6000,
 * });
 * ```
 */

import { useContext } from 'react';
import { ToastContext } from '../contexts/ToastContext';

export const useToast = () => {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }

  return context;
};
