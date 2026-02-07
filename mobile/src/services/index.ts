/**
 * Services - Central Export
 *
 * Export all service modules from a single location.
 */

export { authService } from './authService';
export { attendanceService } from './attendanceService';
export { scheduleService } from './scheduleService';
export { faceService } from './faceService';
export { websocketService } from './websocketService';
export { notificationService } from './notificationService';

// Re-export API client and error utilities for convenience
export { api, extractApiError } from '../utils/api';
export type { ApiError } from '../utils/api';
