import api from './api'

export type SessionEligibilityCode =
  | 'ALLOWED'
  | 'RUNNING'
  | 'WRONG_DAY'
  | 'TOO_EARLY'
  | 'AFTER_END'
  | 'ALREADY_RAN_TODAY'
  | 'NOT_OWNER'
  | 'INACTIVE_SCHEDULE'

export interface SessionEligibility {
  schedule_id: string
  allowed: boolean
  code: SessionEligibilityCode
  message: string
  // ISO datetimes for the schedule's natural window resolved against today.
  scheduled_start: string
  scheduled_end: string
  // The earliest moment a manual start is accepted (start_time - 10 min).
  available_at: string
  scheduled_day: number
  current_day: number
}

export const presenceService = {
  getStartEligibility: (scheduleId: string) =>
    api
      .get<SessionEligibility>(`/presence/sessions/${scheduleId}/eligibility`)
      .then(r => r.data),
}
