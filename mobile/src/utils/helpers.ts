/**
 * Helpers - Miscellaneous Helper Functions
 *
 * General utility functions that don't fit into other categories.
 */

import { AttendanceStatus } from '../types';
import { colors } from '../constants';

/**
 * Get color for attendance status
 */
export const getStatusColor = (status: AttendanceStatus): string => {
  const statusColors = {
    [AttendanceStatus.PRESENT]: colors.status.present.fg,
    [AttendanceStatus.LATE]: colors.status.late.fg,
    [AttendanceStatus.ABSENT]: colors.status.absent.fg,
    [AttendanceStatus.EARLY_LEAVE]: colors.status.early_leave.fg,
  };

  return statusColors[status] || colors.text.secondary;
};

/**
 * Get background color for attendance status
 */
export const getStatusBackgroundColor = (status: AttendanceStatus): string => {
  const statusBgColors = {
    [AttendanceStatus.PRESENT]: colors.status.present.bg,
    [AttendanceStatus.LATE]: colors.status.late.bg,
    [AttendanceStatus.ABSENT]: colors.status.absent.bg,
    [AttendanceStatus.EARLY_LEAVE]: colors.status.early_leave.bg,
  };

  return statusBgColors[status] || colors.muted;
};

/**
 * Get human-readable label for attendance status
 */
export const getStatusLabel = (status: AttendanceStatus): string => {
  const statusLabels = {
    [AttendanceStatus.PRESENT]: 'Present',
    [AttendanceStatus.LATE]: 'Late',
    [AttendanceStatus.ABSENT]: 'Absent',
    [AttendanceStatus.EARLY_LEAVE]: 'Early Leave',
  };

  return statusLabels[status] || 'Unknown';
};

/**
 * Promise-based delay (useful for testing/demos)
 */
export const sleep = (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

/**
 * Truncate text with ellipsis
 */
export const truncate = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + '...';
};

/**
 * Capitalize first letter of string
 */
export const capitalize = (text: string): string => {
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
};

/**
 * Check if time is within range
 */
export const isTimeInRange = (time: string, startTime: string, endTime: string): boolean => {
  try {
    const [hours, minutes] = time.split(':').map(Number);
    const [startHours, startMinutes] = startTime.split(':').map(Number);
    const [endHours, endMinutes] = endTime.split(':').map(Number);

    const timeMinutes = hours * 60 + minutes;
    const startMinutes = startHours * 60 + startMinutes;
    const endMinutes = endHours * 60 + endMinutes;

    return timeMinutes >= startMinutes && timeMinutes <= endMinutes;
  } catch (error) {
    return false;
  }
};

/**
 * Get current time in HH:MM:SS format
 */
export const getCurrentTime = (): string => {
  const now = new Date();
  const hours = now.getHours().toString().padStart(2, '0');
  const minutes = now.getMinutes().toString().padStart(2, '0');
  const seconds = now.getSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
};

/**
 * Get current date in YYYY-MM-DD format
 */
export const getCurrentDate = (): string => {
  const now = new Date();
  const year = now.getFullYear();
  const month = (now.getMonth() + 1).toString().padStart(2, '0');
  const day = now.getDate().toString().padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Handle API error and return user-friendly message
 */
export const getErrorMessage = (error: any): string => {
  if (error.response?.status === 401) {
    return 'Session expired. Please login again.';
  }
  if (error.response?.status === 403) {
    return 'You do not have permission to perform this action.';
  }
  if (error.response?.status === 404) {
    return 'Resource not found.';
  }
  if (error.response?.status === 422) {
    return error.response.data.detail || 'Validation error. Please check your input.';
  }
  if (error.response?.data?.error?.message) {
    return error.response.data.error.message;
  }
  if (!error.response) {
    return 'Network error. Please check your internet connection.';
  }
  return 'Something went wrong. Please try again.';
};
