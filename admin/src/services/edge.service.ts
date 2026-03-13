import api from './api'

export const edgeService = {
  getStatus: () =>
    api.get('/edge/status').then(r => r.data),
}
