/**
 * Services - Central Export
 *
 * Export all service modules from a single location.
 */

export { authService } from './authService';
export { attendanceService } from './attendanceService';
export { analyticsService } from './analyticsService';
export { scheduleService } from './scheduleService';
export { sessionService } from './sessionService';
export { faceService } from './faceService';
export { websocketService } from './websocketService';
export { notificationService } from './notificationService';
export { getSupabaseClient, supabase } from './supabase';

// Re-export API client and error utilities for convenience
export { api, extractApiError } from '../utils/api';
export type { ApiError } from '../utils/api';
