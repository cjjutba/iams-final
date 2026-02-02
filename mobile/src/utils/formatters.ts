/**
 * Formatters - Date/Time Formatting Utilities
 *
 * Helper functions for formatting dates, times, and other values.
 * Uses date-fns for consistent date formatting.
 */

import { format, formatDistanceToNow, parseISO, isToday, isTomorrow, isYesterday } from 'date-fns';

/**
 * Format date using date-fns pattern
 */
export const formatDate = (date: string | Date, pattern: string = 'MMM dd, yyyy'): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return format(dateObj, pattern);
  } catch (error) {
    console.error('Failed to format date:', error);
    return '';
  }
};

/**
 * Format time from HH:MM:SS to 12-hour format with AM/PM
 */
export const formatTime = (time: string): string => {
  try {
    // Parse time string (HH:MM:SS or HH:MM)
    const [hours, minutes] = time.split(':').map(Number);

    const period = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const displayMinutes = minutes.toString().padStart(2, '0');

    return `${displayHours}:${displayMinutes} ${period}`;
  } catch (error) {
    console.error('Failed to format time:', error);
    return time;
  }
};

/**
 * Format date and time together
 */
export const formatDateTime = (datetime: string | Date): string => {
  try {
    const dateObj = typeof datetime === 'string' ? parseISO(datetime) : datetime;
    return format(dateObj, 'MMM dd, yyyy h:mm a');
  } catch (error) {
    console.error('Failed to format datetime:', error);
    return '';
  }
};

/**
 * Format relative time (e.g., "2 hours ago")
 */
export const formatTimeAgo = (date: string | Date): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return formatDistanceToNow(dateObj, { addSuffix: true });
  } catch (error) {
    console.error('Failed to format time ago:', error);
    return '';
  }
};

/**
 * Format date with relative context (Today, Yesterday, etc.)
 */
export const formatDateWithContext = (date: string | Date): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;

    if (isToday(dateObj)) {
      return 'Today';
    }
    if (isTomorrow(dateObj)) {
      return 'Tomorrow';
    }
    if (isYesterday(dateObj)) {
      return 'Yesterday';
    }

    return format(dateObj, 'MMM dd, yyyy');
  } catch (error) {
    console.error('Failed to format date with context:', error);
    return '';
  }
};

/**
 * Format percentage value
 */
export const formatPercentage = (value: number, decimals: number = 1): string => {
  try {
    return `${value.toFixed(decimals)}%`;
  } catch (error) {
    console.error('Failed to format percentage:', error);
    return '0%';
  }
};

/**
 * Format full name from first and last name
 */
export const formatName = (firstName: string, lastName: string): string => {
  return `${firstName} ${lastName}`.trim();
};

/**
 * Get day name from day of week number (0=Monday, 6=Sunday)
 */
export const getDayName = (dayOfWeek: number): string => {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  return days[dayOfWeek] || '';
};

/**
 * Get short day name (Mon, Tue, etc.)
 */
export const getShortDayName = (dayOfWeek: number): string => {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return days[dayOfWeek] || '';
};

/**
 * Format time range (e.g., "8:00 AM - 10:00 AM")
 */
export const formatTimeRange = (startTime: string, endTime: string): string => {
  return `${formatTime(startTime)} - ${formatTime(endTime)}`;
};

/**
 * Get initials from name
 */
export const getInitials = (firstName: string, lastName: string): string => {
  const firstInitial = firstName ? firstName.charAt(0).toUpperCase() : '';
  const lastInitial = lastName ? lastName.charAt(0).toUpperCase() : '';
  return firstInitial + lastInitial;
};
