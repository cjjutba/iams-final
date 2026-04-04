import api from './api'

export const edgeService = {
  getStatus: () =>
    api.get('/edge/status').then(r => r.data),
  getDevice: (id: string) =>
    api.get(`/edge/${id}`).then(r => r.data),
}
