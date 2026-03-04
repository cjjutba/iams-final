/**
 * Analytics Service
 *
 * Handles all analytics-related API calls:
 * - Faculty: class overview, heatmaps, rankings, at-risk students, anomalies, predictions
 * - Student: personal dashboard, per-subject breakdowns
 * - Admin: system metrics
 *
 * All endpoints are relative to the base URL configured in api.ts.
 * Backend router prefix: /analytics
 *
 * IMPORTANT: The backend returns response data directly from the
 * Pydantic response_model -- there is NO generic ApiResponse wrapper.
 *
 * @see backend/app/routers/analytics.py
 * @see backend/app/schemas/analytics.py
 */

import { api } from '../utils/api';
import type {
  ClassOverview,
  HeatmapEntry,
  StudentRanking,
  AtRiskStudent,
  AnomalyItem,
  AttendancePrediction,
  StudentAnalyticsDashboard,
  SubjectBreakdown,
  SystemMetrics,
} from '../types';

// ---------------------------------------------------------------------------
// Request parameter interfaces
// ---------------------------------------------------------------------------

/** Optional date range filters for class analytics */
interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const analyticsService = {
  // -------------------------------------------------------------------------
  // Faculty endpoints
  // -------------------------------------------------------------------------

  /**
   * Get overview analytics for a specific class/schedule.
   *
   * @param scheduleId - The schedule UUID
   * @param startDate - Optional ISO date string (YYYY-MM-DD)
   * @param endDate - Optional ISO date string (YYYY-MM-DD)
   * @returns Class overview with attendance rates, counts, etc.
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/class/{scheduleId}
   * Response: ClassOverviewResponse
   */
  async getClassOverview(
    scheduleId: string,
    startDate?: string,
    endDate?: string,
  ): Promise<ClassOverview> {
    const response = await api.get<ClassOverview>(
      `/analytics/class/${scheduleId}`,
      {
        params: {
          ...(startDate && { start_date: startDate }),
          ...(endDate && { end_date: endDate }),
        },
      },
    );
    return response.data;
  },

  /**
   * Get attendance heatmap data for a class.
   * Returns daily attendance counts suitable for heatmap visualization.
   *
   * @param scheduleId - The schedule UUID
   * @param startDate - Optional ISO date string (YYYY-MM-DD)
   * @param endDate - Optional ISO date string (YYYY-MM-DD)
   * @returns Array of heatmap entries (date + attendance rate)
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/class/{scheduleId}/heatmap
   * Response: List[HeatmapEntry]
   */
  async getClassHeatmap(
    scheduleId: string,
    startDate?: string,
    endDate?: string,
  ): Promise<HeatmapEntry[]> {
    const response = await api.get<HeatmapEntry[]>(
      `/analytics/class/${scheduleId}/heatmap`,
      {
        params: {
          ...(startDate && { start_date: startDate }),
          ...(endDate && { end_date: endDate }),
        },
      },
    );
    return response.data;
  },

  /**
   * Get student ranking for a class sorted by attendance rate.
   *
   * @param scheduleId - The schedule UUID
   * @returns Array of student rankings
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/class/{scheduleId}/ranking
   * Response: List[StudentRanking]
   */
  async getClassRanking(scheduleId: string): Promise<StudentRanking[]> {
    const response = await api.get<StudentRanking[]>(
      `/analytics/class/${scheduleId}/ranking`,
    );
    return response.data;
  },

  /**
   * Get students who are at risk of failing due to low attendance.
   *
   * @returns Array of at-risk students across all faculty schedules
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/at-risk
   * Response: List[AtRiskStudent]
   */
  async getAtRiskStudents(): Promise<AtRiskStudent[]> {
    const response = await api.get<AtRiskStudent[]>('/analytics/at-risk');
    return response.data;
  },

  /**
   * Get anomaly alerts (unusual attendance patterns).
   *
   * @returns Array of anomaly items
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/anomalies
   * Response: List[AnomalyItem]
   */
  async getAnomalies(): Promise<AnomalyItem[]> {
    const response = await api.get<AnomalyItem[]>('/analytics/anomalies');
    return response.data;
  },

  /**
   * Resolve (dismiss) an anomaly alert.
   *
   * @param anomalyId - The anomaly record UUID
   * @returns The updated anomaly item
   * @throws AxiosError (404 if not found, 403 if access denied)
   *
   * Backend: PATCH /analytics/anomalies/{anomalyId}/resolve
   * Response: AnomalyItem
   */
  async resolveAnomaly(anomalyId: string): Promise<AnomalyItem> {
    const response = await api.patch<AnomalyItem>(
      `/analytics/anomalies/${anomalyId}/resolve`,
    );
    return response.data;
  },

  /**
   * Get attendance predictions for a class for the coming week.
   *
   * @param scheduleId - The schedule UUID
   * @param weekStart - Optional start of the prediction week (YYYY-MM-DD)
   * @returns Array of attendance predictions
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/predictions/{scheduleId}
   * Response: List[AttendancePrediction]
   */
  async getPredictions(
    scheduleId: string,
    weekStart?: string,
  ): Promise<AttendancePrediction[]> {
    const response = await api.get<AttendancePrediction[]>(
      `/analytics/predictions/${scheduleId}`,
      {
        params: {
          ...(weekStart && { week_start: weekStart }),
        },
      },
    );
    return response.data;
  },

  // -------------------------------------------------------------------------
  // Student endpoints
  // -------------------------------------------------------------------------

  /**
   * Get the current student's analytics dashboard.
   * Includes overall attendance rate, streak, and summary stats.
   *
   * @returns Student analytics dashboard data
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/me/dashboard
   * Response: StudentAnalyticsDashboard
   */
  async getStudentDashboard(): Promise<StudentAnalyticsDashboard> {
    const response = await api.get<StudentAnalyticsDashboard>(
      '/analytics/me/dashboard',
    );
    return response.data;
  },

  /**
   * Get per-subject attendance breakdown for the current student.
   *
   * @returns Array of subject breakdowns with attendance rates
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/me/subjects
   * Response: List[SubjectBreakdown]
   */
  async getStudentSubjects(): Promise<SubjectBreakdown[]> {
    const response = await api.get<SubjectBreakdown[]>(
      '/analytics/me/subjects',
    );
    return response.data;
  },

  // -------------------------------------------------------------------------
  // Admin endpoints
  // -------------------------------------------------------------------------

  /**
   * Get system-wide metrics (admin only).
   *
   * @returns System metrics including user counts, attendance rates, etc.
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /analytics/system/metrics
   * Response: SystemMetrics
   */
  async getSystemMetrics(): Promise<SystemMetrics> {
    const response = await api.get<SystemMetrics>(
      '/analytics/system/metrics',
    );
    return response.data;
  },
};
