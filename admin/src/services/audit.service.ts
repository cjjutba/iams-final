import api from './api'

export const auditService = {
  getLogs: (params?: { skip?: number; limit?: number; action?: string; target_type?: string }) =>
    api.get('/audit/logs', { params }).then(r => r.data),
}
